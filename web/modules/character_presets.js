/**
 * character_presets.js — CharacterPresetStore singleton + applyPreset helper
 *
 * Schema: { version, presets: [{ id, label, character, series,
 *   essential_general_tags, recommended_artists, notes, tier }] }
 */

import { addTagToField } from "./composer.js";

// Module-scope state
let _presetsById = {};
let _sortedPresets = [];

/**
 * Initialize the store with raw data from the API.
 * Presets are sorted by tier descending, then label ascending.
 *
 * @param {Object} data - Response from GET /anima_prompt_helper/character_presets
 */
function init(data) {
  _presetsById = {};
  _sortedPresets = [];

  if (!data || !Array.isArray(data.presets)) {
    console.warn("[AnimaPromptHelper] CharacterPresetStore.init: invalid data");
    return;
  }

  for (const preset of data.presets) {
    _presetsById[preset.id] = preset;
  }

  _sortedPresets = data.presets.slice().sort((a, b) => {
    const tierDiff = (b.tier || 0) - (a.tier || 0);
    if (tierDiff !== 0) return tierDiff;
    return (a.label || "").localeCompare(b.label || "");
  });
}

/**
 * Returns a sorted copy of all presets.
 * @returns {Array}
 */
function getAll() {
  return _sortedPresets.slice();
}

/**
 * Returns a preset by id, or null if not found.
 * @param {string} id
 * @returns {Object|null}
 */
function getById(id) {
  return _presetsById[id] || null;
}

export const CharacterPresetStore = { init, getAll, getById };

/**
 * Apply a character preset to a node.
 *
 * - Overwrites the character and series field widgets directly.
 * - Appends essential_general_tags to the general field (dedup handled by addTagToField).
 * - Appends recommended_artists to the artist field (@ prefix preserved).
 * - Triggers preview refresh by firing an input event on character widget element.
 * - Records lastPresetId in node.animaUiState.
 *
 * @param {Object} node   - LiteGraph node instance
 * @param {Object} preset - Preset object from CharacterPresetStore
 * @param {Function} [onRefresh] - Optional callback to refresh preview after apply
 */
export function applyPreset(node, preset, onRefresh) {
  if (!node || !preset) return;

  // Overwrite character and series fields directly
  _setField(node, "character", preset.character || "");
  _setField(node, "series", preset.series || "");

  // Append essential_general_tags (addTagToField handles dedup)
  const generalTags = Array.isArray(preset.essential_general_tags)
    ? preset.essential_general_tags
    : [];
  for (const tag of generalTags) {
    if (tag && typeof tag === "string") {
      addTagToField(node, "general", tag);
    }
  }

  // Append recommended_artists to artist field (@ prefix preserved)
  const artists = Array.isArray(preset.recommended_artists)
    ? preset.recommended_artists
    : [];
  for (const artist of artists) {
    if (artist && typeof artist === "string") {
      addTagToField(node, "artist", artist);
    }
  }

  // Store last-applied preset id in animaUiState
  if (node.animaUiState) {
    node.animaUiState.lastPresetId = preset.id;
  }

  // Trigger refresh
  if (typeof onRefresh === "function") {
    onRefresh();
  }
}

/**
 * Internal helper: overwrite a field widget value and fire input event.
 * @param {Object} node
 * @param {string} fieldName
 * @param {string} value
 */
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
