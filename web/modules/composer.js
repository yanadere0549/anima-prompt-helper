/**
 * composer.js — JS-side prompt field operations
 *
 * Handles tag deduplication and field widget writes.
 * assemblePreview is retained for JS/Python parity testing via run_js_compose.mjs.
 */

// Hardcoded fallback canonical order (used by assemblePreview if specCache is null)
const FALLBACK_CANONICAL_ORDER = [
  "quality", "year", "rating", "count",
  "character", "series", "artist", "general", "natural_language",
];

/**
 * Parses a tag that may be wrapped in (tag:weight) syntax.
 * Returns { tag, weight } where weight is a number (1.0 if not weighted).
 *
 * Preconditions:
 *   - tagStr is a string.
 * Postconditions:
 *   - Returns {tag: string, weight: number}.
 *   - If tagStr is "(foo:1.2)" → {tag: "foo", weight: 1.2}.
 *   - If tagStr is "foo" → {tag: "foo", weight: 1.0}.
 *   - Malformed input returns {tag: tagStr.trim(), weight: 1.0}.
 *
 * @param {string} tagStr
 * @returns {{tag: string, weight: number}}
 */
export function parseWeightedTag(tagStr) {
  const s = (tagStr || "").trim();
  // Match (...:N.N) where ... is anything not containing : or )
  const m = s.match(/^\((.+):(\d+(?:\.\d+)?)\)$/);
  if (m) {
    const w = parseFloat(m[2]);
    if (!isNaN(w)) {
      return { tag: m[1].trim(), weight: w };
    }
  }
  return { tag: s, weight: 1.0 };
}

/**
 * Formats a tag with weight as (tag:weight) if weight != 1.0, otherwise as the bare tag.
 * Weight is rounded to 2 decimal places.
 *
 * Preconditions:
 *   - tag is a non-empty trimmable string.
 *   - weight is a positive number.
 * Postconditions:
 *   - Returns "(tag:W)" if weight != 1.0 (rounded to 2 decimals, dropping trailing zeros).
 *   - Returns the bare tag if weight is 1.0.
 *
 * @param {string} tag
 * @param {number} weight
 * @returns {string}
 */
export function formatWeightedTag(tag, weight) {
  const t = (tag || "").trim();
  if (!t) return "";
  const w = Math.round(weight * 100) / 100;
  if (Math.abs(w - 1.0) < 0.005) return t;
  // Strip trailing zero (1.20 → 1.2)
  const wStr = w.toString();
  return `(${t}:${wStr})`;
}

/**
 * Adjusts the weight of a tag within a field by delta (e.g. +0.1, -0.1).
 * If the tag exists without weight, it is replaced with (tag:1.0 + delta).
 * If the tag exists with weight, the weight is incremented by delta.
 * If the tag does not exist, it is appended as (tag:1.0 + delta).
 * Weight is clamped to [0.1, 2.0] and rounded to 2 decimals.
 *
 * Preconditions:
 *   - node has a widget named fieldName (else no-op + warn).
 *   - tag is a trimmable string.
 *   - delta is a number.
 * Postconditions:
 *   - Returns the new weight as a number, or null on no-op.
 *
 * @param {Object} node
 * @param {string} fieldName
 * @param {string} tag (without weight syntax)
 * @param {number} delta
 * @returns {number|null}
 */
export function adjustTagWeight(node, fieldName, tag, delta) {
  const widget = getFieldWidget(node, fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] adjustTagWeight: widget not found:", fieldName);
    return null;
  }
  const trimmed = (tag || "").trim();
  if (!trimmed) return null;

  const current = (typeof widget.value === "string") ? widget.value : "";
  const parts = current.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const tagNorm = trimmed.toLowerCase();
  const matchIdx = parts.findIndex((p) => {
    const parsed = parseWeightedTag(p);
    return parsed.tag.toLowerCase() === tagNorm;
  });

  let newWeight;
  if (matchIdx >= 0) {
    const parsed = parseWeightedTag(parts[matchIdx]);
    newWeight = parsed.weight + delta;
  } else {
    newWeight = 1.0 + delta;
  }
  // Clamp [0.1, 2.0] and round to 2 decimals
  newWeight = Math.max(0.1, Math.min(2.0, Math.round(newWeight * 100) / 100));

  const newToken = formatWeightedTag(trimmed, newWeight);
  if (matchIdx >= 0) {
    parts[matchIdx] = newToken;
  } else {
    parts.push(newToken);
  }
  _writeFieldValue(widget, node, parts.join(", "));
  return newWeight;
}

/**
 * Removes a tag from a field, matching with or without weight syntax.
 * Case-insensitive match on the bare tag part.
 *
 * Preconditions:
 *   - node has a widget named fieldName (else no-op + warn).
 *   - tag is a trimmable string (bare tag, without weight syntax).
 * Postconditions:
 *   - Returns true if the tag was found and removed, false otherwise.
 *   - Field widget value no longer contains the matched token.
 *
 * @param {Object} node
 * @param {string} fieldName
 * @param {string} tag - bare tag (without weight)
 * @returns {boolean} true if removed, false if not found
 */
export function removeTagFromField(node, fieldName, tag) {
  const widget = getFieldWidget(node, fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] removeTagFromField: widget not found:", fieldName);
    return false;
  }
  const trimmed = (tag || "").trim();
  if (!trimmed) return false;

  const current = (typeof widget.value === "string") ? widget.value : "";
  const parts = current.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const tagNorm = trimmed.toLowerCase();
  const idx = parts.findIndex((p) => {
    const parsed = parseWeightedTag(p);
    return parsed.tag.toLowerCase() === tagNorm;
  });
  if (idx < 0) return false;

  parts.splice(idx, 1);
  _writeFieldValue(widget, node, parts.join(", "));
  return true;
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
 * Assembles the preview string, mirroring Python join_fields exactly.
 * Retained for JS/Python parity testing (run_js_compose.mjs).
 *
 * @param {Object} node
 * @param {Object|null} spec
 * @returns {string}
 */
export function assemblePreview(node, spec) {
  const canonicalOrder = (spec && Array.isArray(spec.canonical_order))
    ? spec.canonical_order
    : FALLBACK_CANONICAL_ORDER;

  const presetWidget = getFieldWidget(node, "prefix_preset");
  const prefixPreset = presetWidget ? presetWidget.value : "none";

  let presetQuality = "";
  let presetYear = "";
  let presetRating = "";
  let presetExtra = "";
  if (prefixPreset === "ooo_anima_default" && spec && spec.model_presets && spec.model_presets.ooo_anima) {
    const p = spec.model_presets.ooo_anima;
    presetQuality = p.default_prefix_quality || "";
    presetYear = p.default_prefix_year || "";
    presetRating = p.default_rating || "";
    presetExtra = (p.default_extra || "").trim();
  }

  const fieldParts = [];
  const mainFields = canonicalOrder.filter((f) => f !== "natural_language");

  for (const fieldName of mainFields) {
    let val;
    if (prefixPreset === "ooo_anima_default") {
      if (fieldName === "quality") {
        val = presetQuality;
      } else if (fieldName === "year") {
        val = presetYear;
      } else if (fieldName === "rating") {
        val = presetRating;
      } else {
        const w = getFieldWidget(node, fieldName);
        val = w ? (w.value || "") : "";
      }
    } else {
      const w = getFieldWidget(node, fieldName);
      val = w ? (w.value || "") : "";
    }

    const tokens = tokenize(val);
    if (tokens.length > 0) {
      fieldParts.push(tokens.join(", "));
    }

    if (fieldName === "rating" && presetExtra) {
      fieldParts.push(presetExtra);
    }
  }

  let assembled = fieldParts.join(", ");

  const nlWidget = getFieldWidget(node, "natural_language");
  const nlVal = nlWidget ? ((nlWidget.value || "").trim()) : "";
  if (nlVal) {
    assembled = assembled ? assembled + ". " + nlVal : nlVal;
  }

  return assembled;
}

/**
 * Finds and returns the widget object on a node by name.
 * @param {Object} node - LiteGraph node instance
 * @param {string} fieldName
 * @returns {Object|null}
 */
export function getFieldWidget(node, fieldName) {
  if (!node || !Array.isArray(node.widgets)) return null;
  return node.widgets.find((w) => w.name === fieldName) || null;
}

/**
 * Adds a tag to a field widget, deduplicating by lowercase comparison.
 * Fires an 'input' event on the underlying element to mark the graph dirty.
 *
 * @param {Object} node
 * @param {string} fieldName
 * @param {string} tag
 */
export function addTagToField(node, fieldName, tag) {
  const widget = getFieldWidget(node, fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] addTagToField: widget not found:", fieldName);
    return;
  }

  const current = (typeof widget.value === "string") ? widget.value : "";
  const parts = current.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const tagNorm = tag.trim().toLowerCase();
  // Match against the bare tag (ignoring weight) for deduplication
  const alreadyPresent = parts.some((p) => {
    const parsed = parseWeightedTag(p);
    return parsed.tag.toLowerCase() === tagNorm;
  });
  if (alreadyPresent) return;

  parts.push(tag.trim());
  const newVal = parts.join(", ");

  _writeFieldValue(widget, node, newVal);
}

/**
 * Toggle a tag in a field widget: removes it if already present (case-insensitive),
 * otherwise appends it. Returns the resulting action so callers can update UI state
 * (e.g. toggle an "active" CSS class on the clicked button).
 *
 * Preconditions:
 *   - ``node`` has a widget named ``fieldName`` (otherwise the call is a no-op + warn).
 *   - ``tag`` is a non-empty trimmed-or-trimmable string.
 *
 * Postconditions:
 *   - Field widget value contains ``tag`` exactly once (if added) or not at all (if removed).
 *   - Returns one of ``"added"``, ``"removed"``, or ``"noop"``.
 *
 * @param {Object} node
 * @param {string} fieldName
 * @param {string} tag
 * @returns {"added"|"removed"|"noop"}
 */
export function toggleTagInField(node, fieldName, tag) {
  const widget = getFieldWidget(node, fieldName);
  if (!widget) {
    console.warn("[AnimaPromptHelper] toggleTagInField: widget not found:", fieldName);
    return "noop";
  }

  const trimmed = (tag || "").trim();
  if (!trimmed) return "noop";

  const current = (typeof widget.value === "string") ? widget.value : "";
  const parts = current.split(",").map((t) => t.trim()).filter((t) => t.length > 0);

  const tagNorm = trimmed.toLowerCase();
  // Match against the bare tag (ignoring weight) so weighted tags can be toggled
  const idx = parts.findIndex((p) => {
    const parsed = parseWeightedTag(p);
    return parsed.tag.toLowerCase() === tagNorm;
  });

  let action;
  if (idx >= 0) {
    parts.splice(idx, 1);
    action = "removed";
  } else {
    parts.push(trimmed);
    action = "added";
  }

  _writeFieldValue(widget, node, parts.join(", "));
  return action;
}

/**
 * Internal helper: writes a value into a widget, syncs the DOM element if present,
 * and marks the graph canvas dirty.
 */
function _writeFieldValue(widget, node, newVal) {
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

