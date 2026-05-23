/**
 * prefix_presets.js — PrefixPresetStore singleton
 *
 * Schema: { version, presets: [{ id, label, quality, year, rating, extra,
 *                                notes, tier, user }] }
 *
 * The ``user`` flag distinguishes user-saved presets from the builtin
 * ``ooo_anima_default`` entry (which is served by the backend from
 * anima_spec.json). Only user presets are editable / deletable.
 */

// Module-scope state
let _presetsById = {};
let _sortedPresets = [];
const _listeners = [];

/**
 * Initialize the store with raw data from the API.
 * Builtin presets sort first (so ``ooo_anima_default`` stays near the top);
 * user presets follow, ordered by tier desc then label asc.
 *
 * @param {Object} data - Response from GET /anima_prompt_helper/prefix_presets
 */
function init(data) {
  _presetsById = {};
  _sortedPresets = [];

  if (!data || !Array.isArray(data.presets)) {
    console.warn("[AnimaPromptHelper] PrefixPresetStore.init: invalid data");
    _notify();
    return;
  }

  for (const preset of data.presets) {
    if (!preset || typeof preset.id !== "string") continue;
    _presetsById[preset.id] = preset;
  }

  _sortedPresets = data.presets.slice().sort(_sortFn);
  _notify();
}

function _sortFn(a, b) {
  // Builtin first (user === false sorts before user === true).
  const userDiff = (a.user ? 1 : 0) - (b.user ? 1 : 0);
  if (userDiff !== 0) return userDiff;
  const tierDiff = (b.tier || 0) - (a.tier || 0);
  if (tierDiff !== 0) return tierDiff;
  return (a.label || "").localeCompare(b.label || "");
}

/** Returns a sorted copy of all presets (builtin + user). */
function getAll() {
  return _sortedPresets.slice();
}

/** Returns a preset by id, or null if not found. */
function getById(id) {
  return _presetsById[id] || null;
}

/**
 * Save (create or update) a user preset via the backend.
 *
 * @param {Object} preset - { id, label, quality, year, rating, extra, notes, tier }
 * @returns {Promise<{ok: true, preset: Object} | {ok: false, error: string}>}
 */
async function saveUserPreset(preset) {
  try {
    const resp = await fetch("/anima_prompt_helper/user_prefix_presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset }),
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
    const saved = data && data.preset ? data.preset : null;
    if (saved && typeof saved.id === "string") {
      _presetsById[saved.id] = saved;
      const existingIdx = _sortedPresets.findIndex((p) => p.id === saved.id);
      if (existingIdx >= 0) {
        _sortedPresets[existingIdx] = saved;
      } else {
        _sortedPresets.push(saved);
      }
      _sortedPresets.sort(_sortFn);
      _notify();
    }
    return { ok: true, preset: saved };
  } catch (err) {
    console.warn("[AnimaPromptHelper] PrefixPresetStore.saveUserPreset error:", err);
    return { ok: false, error: "network_error" };
  }
}

/**
 * Delete a user preset by id via the backend.
 * @param {string} id
 * @returns {Promise<{ok: true} | {ok: false, error: string}>}
 */
async function deleteUserPreset(id) {
  if (!id) return { ok: false, error: "invalid_id" };
  try {
    const resp = await fetch(
      `/anima_prompt_helper/user_prefix_presets/${encodeURIComponent(id)}`,
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
    if (_presetsById[id]) delete _presetsById[id];
    _sortedPresets = _sortedPresets.filter((p) => p.id !== id);
    _notify();
    return { ok: true };
  } catch (err) {
    console.warn("[AnimaPromptHelper] PrefixPresetStore.deleteUserPreset error:", err);
    return { ok: false, error: "network_error" };
  }
}

/**
 * Subscribe to mutation events. Listeners are called with no args.
 * Returns an unsubscribe function.
 * @param {Function} fn
 */
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
    try { fn(); } catch (e) { /* swallow */ }
  }
}

export const PrefixPresetStore = {
  init, getAll, getById, saveUserPreset, deleteUserPreset, subscribe,
};

/**
 * Wire the "新規作成 / 編集" button widgets onto a composer node, just below
 * the existing ``prefix_preset`` combo widget. Also subscribes to store
 * mutations so the combo's option list refreshes after a save/delete.
 *
 * Imports openPrefixPresetEditor lazily to avoid a circular dependency with
 * preset_editor.js.
 *
 * @param {Object} node - the AnimaPromptComposer LiteGraph node instance
 */
export function attachPrefixPresetUI(node) {
  if (!node || typeof node.addWidget !== "function") return;
  if (node._aphPrefixUiAttached) return;
  node._aphPrefixUiAttached = true;

  // Async-import so this module stays loadable in node-only test environments.
  const editorImport = import("./preset_editor.js");

  node.addWidget("button", "💾 prefix preset 新規作成 (現状から)", null, async () => {
    const ed = await editorImport;
    ed.openPrefixPresetEditor({ mode: "create", sourceComposerNode: node });
  });

  node.addWidget("button", "✎ 選択中の prefix preset を編集", null, async () => {
    const w = node.widgets.find((x) => x.name === "prefix_preset");
    if (!w) return;
    const id = w.value;
    if (!id || id === "none" || id === "custom") {
      alert("「none」「custom」は編集対象ではありません。「💾 新規作成」をご利用ください。");
      return;
    }
    const preset = getById(id);
    if (!preset) {
      alert(`プリセット「${id}」が見つかりません。`);
      return;
    }
    if (!preset.user) {
      alert(
        `「${preset.label}」は組み込みプリセットなので編集できません。\n`
        + `「💾 新規作成」で複製してから編集してください。`
      );
      return;
    }
    const ed = await editorImport;
    ed.openPrefixPresetEditor({ mode: "edit", preset });
  });

  // Re-sync combo options whenever the store mutates (create / update / delete).
  const unsubscribe = subscribe(() => _refreshPrefixPresetCombo(node));

  // Initial sync in case user presets are already loaded.
  _refreshPrefixPresetCombo(node);

  // Cleanup on node removal.
  const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    try { unsubscribe(); } catch (_) { /* ignore */ }
    if (origOnRemoved) origOnRemoved();
  };
}

function _refreshPrefixPresetCombo(node) {
  if (!node || !Array.isArray(node.widgets)) return;
  const w = node.widgets.find((x) => x.name === "prefix_preset");
  if (!w) return;
  // LiteGraph combo widgets expose their dropdown options via either
  // ``options.values`` (array) or ``options.values`` (function). We only
  // know how to mutate the array form.
  const allPresets = getAll();
  const userIds = allPresets.filter((p) => p.user).map((p) => p.id);
  const values = ["none", "ooo_anima_default", "custom", ...userIds];
  if (w.options) {
    w.options.values = values;
  } else {
    w.options = { values };
  }
  if (!values.includes(w.value)) {
    w.value = "none";
  }
  try {
    if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
      node.graph.setDirtyCanvas(true, true);
    }
  } catch (_) { /* ignore */ }
}

/**
 * Snapshot the composer's current quality / year / rating fields, so the
 * "save current as preset" quick action can pre-fill the editor.
 * Returns rating verbatim — caller is responsible for validation.
 *
 * @param {Object} node
 * @returns {{quality: string, year: string, rating: string, extra: string}}
 */
export function snapshotPrefixFromComposer(node) {
  const result = { quality: "", year: "", rating: "safe", extra: "" };
  if (!node || !Array.isArray(node.widgets)) return result;
  const q = node.widgets.find((w) => w.name === "quality");
  const y = node.widgets.find((w) => w.name === "year");
  const r = node.widgets.find((w) => w.name === "rating");
  if (q && typeof q.value === "string") result.quality = q.value.trim();
  if (y && typeof y.value === "string") result.year = y.value.trim();
  if (r && typeof r.value === "string") result.rating = r.value.trim() || "safe";
  return result;
}
