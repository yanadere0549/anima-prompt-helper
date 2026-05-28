/**
 * situation_pools.js — SituationPoolStore singleton + fetch helper
 *
 * Schema: { version, pools: [{ id, label, tags: string[], notes, user }] }
 *
 * The built-in entry (id "default_danbooru_situations", user: false) is the
 * default situation pool shipped in data/situation_pool_default.json and served
 * by the backend. User pools (user: true) are editable / deletable and stored
 * locally in data/user_situation_pools.json via the API.
 */

export const DEFAULT_POOL_ID = "default_danbooru_situations";

/**
 * Parse a comma/newline-separated pool string into a de-duplicated tag array
 * (case-insensitive). Mirrors python/situation_pool.py::parse_pool.
 * @param {string} raw
 * @returns {string[]}
 */
export function parsePoolString(raw) {
  if (typeof raw !== "string" || !raw.trim()) return [];
  const out = [];
  const seen = new Set();
  for (const chunk of raw.replace(/\n/g, ",").split(",")) {
    const t = chunk.trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

/** Deterministic PRNG (mulberry32) seeded by a 32-bit integer. */
function _mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Deterministically pick ``count`` distinct tags from ``tags`` using ``seed``.
 * Reproducible: same tags + count + seed always yields the same result. Used
 * both for the panel preview and the queue-time ``picked`` population, so the
 * preview matches what is recorded in image metadata.
 *
 * Precondition: tags is an array of strings; count >= 0; seed is a uint32.
 * Postcondition: returns an array of length min(count, tags.length) with no
 *   duplicates, drawn in deterministic order for the given seed.
 *
 * @param {string[]} tags
 * @param {number} count
 * @param {number} seed
 * @returns {string[]}
 */
export function seededPickTags(tags, count, seed) {
  if (!Array.isArray(tags) || !tags.length || count <= 0) return [];
  const pool = tags.slice();
  const rng = _mulberry32((seed >>> 0) || 0);
  const k = Math.min(count, pool.length);
  const out = [];
  for (let i = 0; i < k; i++) {
    const j = i + Math.floor(rng() * (pool.length - i));
    const tmp = pool[i];
    pool[i] = pool[j];
    pool[j] = tmp;
    out.push(pool[i]);
  }
  return out;
}

let _poolsById = {};
let _sortedPools = [];
const _listeners = [];

/**
 * Fetch the merged pool list (builtin + user) from the backend.
 * @returns {Promise<Object|null>} {version, pools} or null on failure
 */
export async function fetchSituationPools() {
  try {
    const resp = await fetch("/anima_prompt_helper/situation_pools");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] situation_pools fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] situation_pools fetch error:", err);
    return null;
  }
}

/** Initialize the store from the API response. Builtin sorts first. */
function init(data) {
  _poolsById = {};
  _sortedPools = [];
  if (!data || !Array.isArray(data.pools)) {
    console.warn("[AnimaPromptHelper] SituationPoolStore.init: invalid data");
    _notify();
    return;
  }
  for (const pool of data.pools) {
    if (!pool || typeof pool.id !== "string") continue;
    if (!Array.isArray(pool.tags)) pool.tags = [];
    _poolsById[pool.id] = pool;
  }
  _sortedPools = data.pools.slice().sort(_sortFn);
  _notify();
}

function _sortFn(a, b) {
  // Builtin first, then user pools alphabetically by label.
  const userDiff = (a.user ? 1 : 0) - (b.user ? 1 : 0);
  if (userDiff !== 0) return userDiff;
  return (a.label || "").localeCompare(b.label || "");
}

/** Returns a sorted copy of all pools (builtin + user). */
function getAll() {
  return _sortedPools.slice();
}

/** Returns a pool by id, or null. */
function getById(id) {
  return _poolsById[id] || null;
}

/**
 * Save (create or update) a user pool via the backend.
 * @param {{id: string, label: string, tags: string[], notes?: string}} pool
 * @returns {Promise<{ok: true, pool: Object} | {ok: false, error: string}>}
 */
async function saveUserPool(pool) {
  try {
    const resp = await fetch("/anima_prompt_helper/user_situation_pools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pool }),
    });
    if (!resp.ok) {
      let err = "save_failed";
      try {
        const data = await resp.json();
        if (data && data.error) err = data.error;
      } catch (_) { /* ignore */ }
      return { ok: false, error: err };
    }
    const data = await resp.json();
    const saved = data && data.pool ? data.pool : null;
    if (saved && typeof saved.id === "string") {
      _poolsById[saved.id] = saved;
      const idx = _sortedPools.findIndex((p) => p.id === saved.id);
      if (idx >= 0) _sortedPools[idx] = saved;
      else _sortedPools.push(saved);
      _sortedPools.sort(_sortFn);
      _notify();
    }
    return { ok: true, pool: saved };
  } catch (err) {
    console.warn("[AnimaPromptHelper] SituationPoolStore.saveUserPool error:", err);
    return { ok: false, error: "network_error" };
  }
}

/**
 * Delete a user pool by id via the backend.
 * @param {string} id
 * @returns {Promise<{ok: true} | {ok: false, error: string}>}
 */
async function deleteUserPool(id) {
  if (!id) return { ok: false, error: "invalid_id" };
  try {
    const resp = await fetch(
      `/anima_prompt_helper/user_situation_pools/${encodeURIComponent(id)}`,
      { method: "DELETE" }
    );
    if (!resp.ok) {
      let err = "delete_failed";
      try {
        const data = await resp.json();
        if (data && data.error) err = data.error;
      } catch (_) { /* ignore */ }
      return { ok: false, error: err };
    }
    if (_poolsById[id]) delete _poolsById[id];
    _sortedPools = _sortedPools.filter((p) => p.id !== id);
    _notify();
    return { ok: true };
  } catch (err) {
    console.warn("[AnimaPromptHelper] SituationPoolStore.deleteUserPool error:", err);
    return { ok: false, error: "network_error" };
  }
}

function subscribe(fn) {
  if (typeof fn !== "function") return () => {};
  _listeners.push(fn);
  return () => {
    const i = _listeners.indexOf(fn);
    if (i >= 0) _listeners.splice(i, 1);
  };
}

function _notify() {
  for (const fn of _listeners) {
    try { fn(); } catch (_) { /* swallow */ }
  }
}

export const SituationPoolStore = {
  init, getAll, getById, saveUserPool, deleteUserPool, subscribe,
};
