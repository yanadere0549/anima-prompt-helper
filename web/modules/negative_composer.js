/**
 * negative_composer.js — JS-side prompt field operations for AnimaNegativePromptComposer
 *
 * Mirrors composer.js but targets the six negative-prompt fields.
 * join_negative_fields() logic is replicated here for live preview.
 */

/** Canonical order matching Python NEGATIVE_CANONICAL_ORDER */
export const NEGATIVE_FIELD_NAMES = [
  "quality_negative",
  "score_negative",
  "style_negative",
  "content_negative",
  "meta_negative",
  "extra_negative",
];

/** Preset names available on the negative_preset widget */
export const NEGATIVE_PRESETS = [
  "none",
  "anima_base_default",
  "ooo_anima_default",
  "custom",
];

/** Human-readable labels for the field selector dropdown */
export const NEGATIVE_FIELD_LABELS = {
  quality_negative: "Quality",
  score_negative: "Score",
  style_negative: "Style",
  content_negative: "Content",
  meta_negative: "Meta",
  extra_negative: "Extra",
};

/**
 * Finds and returns the widget object on a node by name.
 * @param {Object} node - LiteGraph node instance
 * @param {string} fieldName
 * @returns {Object|null}
 */
export function getNegativeFieldWidget(node, fieldName) {
  if (!node || !Array.isArray(node.widgets)) return null;
  return node.widgets.find((w) => w.name === fieldName) || null;
}

/**
 * Adds a tag to a negative field widget, deduplicating by lowercase comparison.
 * Fires an 'input' event on the underlying element to mark the graph dirty.
 *
 * @param {Object} node
 * @param {string} fieldName - one of NEGATIVE_FIELD_NAMES
 * @param {string} tag
 */
export function addTagToNegativeField(node, fieldName, tag) {
  const widget = getNegativeFieldWidget(node, fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] addTagToNegativeField: widget not found:", fieldName);
    return;
  }

  const current = (typeof widget.value === "string") ? widget.value : "";
  const parts = current.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const tagNorm = tag.trim().toLowerCase();
  const alreadyPresent = parts.some((p) => p.toLowerCase() === tagNorm);
  if (alreadyPresent) return;

  parts.push(tag.trim());
  const newVal = parts.join(", ");

  widget.value = newVal;

  // Update the underlying DOM element if it exists
  const inputEl = widget.element || widget.inputEl;
  if (inputEl) {
    inputEl.value = newVal;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // Mark canvas dirty
  try {
    if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
      node.graph.setDirtyCanvas(true, true);
    }
  } catch (e) {
    // ignore
  }
}

/**
 * Tokenizes a comma-separated field value: split by comma, trim, drop empty.
 * @param {string} val
 * @returns {string[]}
 */
function tokenize(val) {
  if (!val || typeof val !== "string") return [];
  return val.split(",").map((t) => t.trim()).filter((t) => t.length > 0);
}

/**
 * Assembles the negative preview string, mirroring Python join_negative_fields().
 *
 * Rules:
 * 1. If negative_preset === "anima_base_default", return
 *    spec.model_presets.anima_base.default_negative verbatim.
 * 2. If negative_preset === "ooo_anima_default", return
 *    spec.model_presets.ooo_anima.default_negative verbatim.
 * 3. Otherwise (none / custom): join the 6 fields in NEGATIVE_CANONICAL_ORDER,
 *    tokenize/strip/rejoin each field, concatenate with ", ".
 *
 * @param {Object} node
 * @param {Object|null} spec - specCache from main module
 * @returns {string}
 */
export function assembleNegativePreview(node, spec) {
  const presetWidget = getNegativeFieldWidget(node, "negative_preset");
  const negativePreset = presetWidget ? (presetWidget.value || "none") : "none";

  // Preset overrides: return the model default string directly
  if (negativePreset === "anima_base_default") {
    if (spec && spec.model_presets && spec.model_presets.anima_base) {
      return spec.model_presets.anima_base.default_negative || "";
    }
    return "worst quality, low quality, score_1, score_2, score_3, artist name";
  }

  if (negativePreset === "ooo_anima_default") {
    if (spec && spec.model_presets && spec.model_presets.ooo_anima) {
      return spec.model_presets.ooo_anima.default_negative || "";
    }
    return "worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic";
  }

  // "none" or "custom": join the 6 fields in canonical order
  const fieldParts = [];
  for (const fieldName of NEGATIVE_FIELD_NAMES) {
    const w = getNegativeFieldWidget(node, fieldName);
    const val = w ? (w.value || "") : "";
    const tokens = tokenize(val);
    if (tokens.length > 0) {
      fieldParts.push(tokens.join(", "));
    }
  }

  return fieldParts.join(", ");
}
