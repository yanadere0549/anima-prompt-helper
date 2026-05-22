/**
 * situation_presets.js — SituationPresetStore + applySituationPreset helper
 *
 * Schema: { version, presets: [{ id, label, category, count_override,
 *   general_tags, natural_language, notes, tier }] }
 *
 * Situation presets fan out to multiple Composer fields:
 *   - general_tags        → addTagToField(node, "general", tag)
 *   - natural_language    → appended (with newline if existing) to
 *                           the "natural_language" field
 *   - count_override      → overwrites "count" if non-null/non-empty
 */

import { addTagToField, getFieldWidget } from "./composer.js";

let _presetsById = {};
let _sortedPresets = [];
let _categories = [];
const _listeners = [];

function _sortInPlace() {
  _sortedPresets.sort((a, b) => {
    const catDiff = (a.category || "zzz").localeCompare(b.category || "zzz");
    if (catDiff !== 0) return catDiff;
    // user presets float to the top inside each category
    const userDiff = (b.user ? 1 : 0) - (a.user ? 1 : 0);
    if (userDiff !== 0) return userDiff;
    const tierDiff = (b.tier || 0) - (a.tier || 0);
    if (tierDiff !== 0) return tierDiff;
    return (a.label || "").localeCompare(b.label || "");
  });
  _categories = [];
  const seen = new Set();
  for (const p of _sortedPresets) {
    const c = p.category || "uncategorized";
    if (!seen.has(c)) {
      seen.add(c);
      _categories.push(c);
    }
  }
}

/**
 * Initialize the store with raw data from the API.
 * Presets are sorted by category alphabetical, then user-first, then tier
 * desc, then label asc.
 *
 * @param {Object} data
 */
function init(data) {
  _presetsById = {};
  _sortedPresets = [];
  _categories = [];

  if (!data || !Array.isArray(data.presets)) {
    console.warn("[AnimaPromptHelper] SituationPresetStore.init: invalid data");
    _notify();
    return;
  }

  for (const preset of data.presets) {
    if (!preset || typeof preset.id !== "string") continue;
    _presetsById[preset.id] = preset;
  }

  _sortedPresets = data.presets.slice();
  _sortInPlace();
  _notify();
}

/** Sorted copy of all presets. */
function getAll() {
  return _sortedPresets.slice();
}

/** Preset by id, or null. */
function getById(id) {
  return _presetsById[id] || null;
}

/** Unique sorted list of category identifiers. */
function getCategories() {
  return _categories.slice();
}

/** Presets in a given category. */
function getByCategory(category) {
  return _sortedPresets.filter((p) => (p.category || "uncategorized") === category);
}

/**
 * Save (create or update) a user situation preset via the backend.
 * Refreshes the store in-place from the response.
 *
 * @param {Object} preset
 * @returns {Promise<{ok: true, preset: Object} | {ok: false, error: string}>}
 */
async function saveUserPreset(preset) {
  try {
    const resp = await fetch("/anima_prompt_helper/user_situation_presets", {
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
      const idx = _sortedPresets.findIndex((p) => p.id === saved.id);
      if (idx >= 0) {
        _sortedPresets[idx] = saved;
      } else {
        _sortedPresets.push(saved);
      }
      _sortInPlace();
      _notify();
    }
    return { ok: true, preset: saved };
  } catch (err) {
    console.warn("[AnimaPromptHelper] SituationPresetStore.saveUserPreset error:", err);
    return { ok: false, error: "network_error" };
  }
}

/**
 * Delete a user situation preset.
 * @param {string} id
 * @returns {Promise<{ok: true} | {ok: false, error: string}>}
 */
async function deleteUserPreset(id) {
  if (!id) return { ok: false, error: "invalid_id" };
  try {
    const resp = await fetch(
      `/anima_prompt_helper/user_situation_presets/${encodeURIComponent(id)}`,
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
    _sortInPlace();
    _notify();
    return { ok: true };
  } catch (err) {
    console.warn("[AnimaPromptHelper] SituationPresetStore.deleteUserPreset error:", err);
    return { ok: false, error: "network_error" };
  }
}

/**
 * Subscribe to mutation events.
 * @param {Function} fn
 * @returns {Function} unsubscribe
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
    try { fn(); } catch (_e) { /* swallow */ }
  }
}

/**
 * Snapshot a Composer node's "situation"-relevant fields for the quick-save
 * action. Reads count, general, natural_language.
 *
 * @param {Object} node
 * @returns {{count_override: string|null, general_tags: string[], natural_language: string}}
 */
export function snapshotSituationFromComposer(node) {
  const result = { count_override: null, general_tags: [], natural_language: "" };
  if (!node || !Array.isArray(node.widgets)) return result;
  const countW = node.widgets.find((w) => w.name === "count");
  const generalW = node.widgets.find((w) => w.name === "general");
  const nlW = node.widgets.find((w) => w.name === "natural_language");

  if (countW && typeof countW.value === "string") {
    const v = countW.value.trim();
    if (v) result.count_override = v;
  }
  if (generalW && typeof generalW.value === "string") {
    result.general_tags = generalW.value.split(",")
      .map((t) => t.trim()).filter((t) => t.length > 0);
  }
  if (nlW && typeof nlW.value === "string") {
    result.natural_language = nlW.value.trim();
  }
  return result;
}

export const SituationPresetStore = {
  init, getAll, getById, getCategories, getByCategory,
  saveUserPreset, deleteUserPreset, subscribe,
};

/**
 * Apply a situation preset to an AnimaPromptComposer node.
 *
 * - general_tags: appended to the "general" field (dedup handled by addTagToField).
 * - natural_language: appended to the "natural_language" field — separated by a
 *   space from any existing text. If the field already contains the same
 *   sentence we skip to avoid duplication.
 * - count_override: overwrites the "count" field iff non-empty.
 *
 * @param {Object} node
 * @param {Object} preset
 * @param {Function} [onRefresh]
 */
export function applySituationPreset(node, preset, onRefresh) {
  if (!node || !preset) return;

  // General tags
  const generals = Array.isArray(preset.general_tags) ? preset.general_tags : [];
  for (const tag of generals) {
    if (tag && typeof tag === "string") {
      addTagToField(node, "general", tag);
    }
  }

  // Natural language
  const nl = typeof preset.natural_language === "string"
    ? preset.natural_language.trim()
    : "";
  if (nl) {
    const w = getFieldWidget(node, "natural_language");
    if (w) {
      const current = typeof w.value === "string" ? w.value.trim() : "";
      let newVal;
      if (!current) {
        newVal = nl;
      } else if (current.toLowerCase().includes(nl.toLowerCase())) {
        newVal = current;
      } else {
        newVal = current + " " + nl;
      }
      _writeWidget(node, w, newVal);
    }
  }

  // Count override
  const countOverride = typeof preset.count_override === "string"
    ? preset.count_override.trim()
    : "";
  if (countOverride) {
    const w = getFieldWidget(node, "count");
    if (w) {
      _writeWidget(node, w, countOverride);
    }
  }

  if (node.animaUiState) {
    node.animaUiState.lastSituationId = preset.id;
  }

  if (typeof onRefresh === "function") {
    onRefresh();
  }
}

function _writeWidget(node, widget, value) {
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
  } catch (_e) {
    // ignore
  }
}
