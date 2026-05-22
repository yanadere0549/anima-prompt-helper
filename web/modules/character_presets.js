/**
 * character_presets.js — CharacterPresetStore singleton + applyPreset helper
 *
 * Schema: { version, presets: [{ id, label, character, series,
 *   essential_general_tags, recommended_artists, notes, tier, user }] }
 *
 * The ``user`` flag distinguishes user-saved presets from builtin ones.
 * Only user presets are editable / deletable via the panel UI.
 */

import { addTagToField } from "./composer.js";

// Module-scope state
let _presetsById = {};
let _sortedPresets = [];
// Callbacks invoked after any mutation that changes the preset list.
const _listeners = [];

/**
 * Initialize the store with raw data from the API.
 * Presets are sorted by user-flag (user first), then tier descending,
 * then label ascending so user creations float to the top.
 *
 * @param {Object} data - Response from GET /anima_prompt_helper/character_presets
 */
function init(data) {
  _presetsById = {};
  _sortedPresets = [];

  if (!data || !Array.isArray(data.presets)) {
    console.warn("[AnimaPromptHelper] CharacterPresetStore.init: invalid data");
    _notify();
    return;
  }

  for (const preset of data.presets) {
    if (!preset || typeof preset.id !== "string") continue;
    _presetsById[preset.id] = preset;
  }

  _sortedPresets = data.presets.slice().sort((a, b) => {
    const userDiff = (b.user ? 1 : 0) - (a.user ? 1 : 0);
    if (userDiff !== 0) return userDiff;
    const tierDiff = (b.tier || 0) - (a.tier || 0);
    if (tierDiff !== 0) return tierDiff;
    return (a.label || "").localeCompare(b.label || "");
  });

  _notify();
}

/** Returns a sorted copy of all presets. */
function getAll() {
  return _sortedPresets.slice();
}

/** Returns a preset by id, or null if not found. */
function getById(id) {
  return _presetsById[id] || null;
}

/**
 * Save (create or update) a user preset via the backend.
 * The store is refreshed in-place from the server response.
 *
 * @param {Object} preset - { id, label, character, series, essential_general_tags, recommended_artists, notes, tier }
 * @returns {Promise<{ok: true, preset: Object} | {ok: false, error: string}>}
 */
async function saveUserPreset(preset) {
  try {
    const resp = await fetch("/anima_prompt_helper/user_character_presets", {
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
        _sortedPresets.unshift(saved);
      }
      // Re-sort to keep ordering invariant
      _sortedPresets.sort((a, b) => {
        const userDiff = (b.user ? 1 : 0) - (a.user ? 1 : 0);
        if (userDiff !== 0) return userDiff;
        const tierDiff = (b.tier || 0) - (a.tier || 0);
        if (tierDiff !== 0) return tierDiff;
        return (a.label || "").localeCompare(b.label || "");
      });
      _notify();
    }
    return { ok: true, preset: saved };
  } catch (err) {
    console.warn("[AnimaPromptHelper] saveUserPreset error:", err);
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
      `/anima_prompt_helper/user_character_presets/${encodeURIComponent(id)}`,
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
    console.warn("[AnimaPromptHelper] deleteUserPreset error:", err);
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

export const CharacterPresetStore = {
  init, getAll, getById, saveUserPreset, deleteUserPreset, subscribe,
};

/**
 * Apply a character preset to a node.
 *
 * - Overwrites the character and series field widgets directly.
 * - Appends essential_general_tags to the general field (dedup via addTagToField).
 * - Appends recommended_artists to the artist field.
 * - Records lastPresetId in node.animaUiState.
 *
 * @param {Object} node   - LiteGraph node instance
 * @param {Object} preset - Preset object from CharacterPresetStore
 * @param {Function} [onRefresh] - Optional callback to refresh preview after apply
 */
export function applyPreset(node, preset, onRefresh) {
  if (!node || !preset) return;

  _setField(node, "character", preset.character || "");
  _setField(node, "series", preset.series || "");

  const generalTags = Array.isArray(preset.essential_general_tags)
    ? preset.essential_general_tags
    : [];
  for (const tag of generalTags) {
    if (tag && typeof tag === "string") {
      addTagToField(node, "general", tag);
    }
  }

  const artists = Array.isArray(preset.recommended_artists)
    ? preset.recommended_artists
    : [];
  for (const artist of artists) {
    if (artist && typeof artist === "string") {
      addTagToField(node, "artist", artist);
    }
  }

  if (node.animaUiState) {
    node.animaUiState.lastPresetId = preset.id;
  }

  if (typeof onRefresh === "function") {
    onRefresh();
  }
}

/**
 * Read a Composer node's character/series/general/artist field values.
 * Used by the "Save current as preset" quick action.
 *
 * @param {Object} node
 * @returns {{character: string, series: string, general: string[], artist: string[]}}
 */
export function snapshotComposerFields(node) {
  const result = { character: "", series: "", general: [], artist: [] };
  if (!node || !Array.isArray(node.widgets)) return result;
  const charW = node.widgets.find((w) => w.name === "character");
  const seriesW = node.widgets.find((w) => w.name === "series");
  const generalW = node.widgets.find((w) => w.name === "general");
  const artistW = node.widgets.find((w) => w.name === "artist");

  if (charW && typeof charW.value === "string") result.character = charW.value.trim();
  if (seriesW && typeof seriesW.value === "string") result.series = seriesW.value.trim();
  if (generalW && typeof generalW.value === "string") {
    result.general = generalW.value.split(",")
      .map((t) => t.trim()).filter((t) => t.length > 0);
  }
  if (artistW && typeof artistW.value === "string") {
    result.artist = artistW.value.split(",")
      .map((t) => t.trim()).filter((t) => t.length > 0);
  }
  return result;
}

function _setField(node, fieldName, value) {
  if (!node || !Array.isArray(node.widgets)) return;
  const widget = node.widgets.find((w) => w.name === fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] applyPreset: widget not found:", fieldName);
    return;
  }

  widget.value = value;

  const inputEl = widget.element || widget.inputEl;
  if (inputEl) {
    inputEl.value = value;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }

  try {
    if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
      node.graph.setDirtyCanvas(true, true);
    }
  } catch (e) {
    // ignore
  }
}
