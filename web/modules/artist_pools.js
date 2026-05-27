/**
 * artist_pools.js — ArtistPoolStore singleton + fetch helper
 *
 * Schema: { version, pools: [{ id, label, tags: string[], notes, user }] }
 *
 * The built-in entry (id "default_highscore", user: false) is the high-score
 * pool shipped in data/artist_pool_default.json and served by the backend.
 * User pools (user: true) are editable / deletable and stored locally in
 * data/user_artist_pools.json via the API.
 */

export const DEFAULT_POOL_ID = "default_highscore";

let _poolsById = {};
let _sortedPools = [];
const _listeners = [];

/**
 * Fetch the merged pool list (builtin + user) from the backend.
 * @returns {Promise<Object|null>} {version, pools} or null on failure
 */
export async function fetchArtistPools() {
  try {
    const resp = await fetch("/anima_prompt_helper/artist_pools");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] artist_pools fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] artist_pools fetch error:", err);
    return null;
  }
}

/** Initialize the store from the API response. Builtin sorts first. */
function init(data) {
  _poolsById = {};
  _sortedPools = [];
  if (!data || !Array.isArray(data.pools)) {
    console.warn("[AnimaPromptHelper] ArtistPoolStore.init: invalid data");
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
    const resp = await fetch("/anima_prompt_helper/user_artist_pools", {
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
    console.warn("[AnimaPromptHelper] ArtistPoolStore.saveUserPool error:", err);
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
      `/anima_prompt_helper/user_artist_pools/${encodeURIComponent(id)}`,
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
    console.warn("[AnimaPromptHelper] ArtistPoolStore.deleteUserPool error:", err);
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

export const ArtistPoolStore = {
  init, getAll, getById, saveUserPool, deleteUserPool, subscribe,
};
