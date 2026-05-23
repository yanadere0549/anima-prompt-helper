/**
 * prompt_classifier.js — split a raw prompt string into AnimaPromptComposer fields.
 *
 * Strategy:
 *   1. Tokenize on commas (we keep weighted syntax intact, e.g. ``(foo:1.2)``).
 *   2. Build a tag → composer field lookup from the palette + a few hardcoded
 *      rules (``@artist`` → ``artist``, ``rating: safe`` → ``rating``, etc).
 *   3. Walk the tokens once, dropping each into its bucket; anything we can't
 *      identify goes into ``general``.
 *
 * The classifier is intentionally lenient — it never throws and always
 * returns the full input partitioned into the 9 composer buckets.
 */

import { CATEGORY_DEFAULT_TARGET } from "./category_target_map.js";

/**
 * The 9 composer buckets, in the order the Composer assembles them.
 * Exported so callers can iterate consistently.
 * @type {string[]}
 */
export const COMPOSER_FIELDS = [
  "quality",
  "year",
  "rating",
  "count",
  "character",
  "series",
  "artist",
  "general",
  "natural_language",
];

// Tokens that are valid ``rating`` widget values for AnimaPromptComposer.
// The widget is a combo, not a multiline string, so we never push more than
// one value into it.
const _RATING_VALUES = new Set(["safe", "sensitive", "nsfw", "explicit"]);

// Tags that strongly hint a token belongs in the ``count`` field. The palette
// also lists count tags, but we keep a small whitelist so files with a
// degraded palette still classify correctly.
const _COUNT_PATTERNS = [
  /^\d+(girl|boy|other|girls|boys|others)s?$/i,
  /^(solo|multiple girls|multiple boys|group)$/i,
];

// Year-flag tokens (e.g. ``newest``, ``year 2025``).
const _YEAR_PATTERNS = [
  /^year\s*\d{4}$/i,
  /^newest$|^recent$|^old(?:est)?$|^mid$/i,
];

// Quality tokens that should land in ``quality`` even if absent from palette.
const _QUALITY_TOKENS = new Set([
  "masterpiece",
  "best quality",
  "high quality",
  "absurdres",
  "highres",
  "ultra-detailed",
  "score_9",
  "score_8",
  "score_7",
  "score_6",
  "score_8_up",
  "score_9_up",
  "score_7_up",
]);

/**
 * Strip optional weight syntax from a token: ``(foo:1.2)`` → ``foo``.
 * Leaves bare tokens unchanged. Returns the trimmed bare tag.
 *
 * @param {string} token
 * @returns {string}
 */
function _bareTag(token) {
  const m = String(token || "").trim().match(/^\((.+):(\d+(?:\.\d+)?)\)$/);
  if (m) return m[1].trim();
  return String(token || "").trim();
}

/**
 * Build a lookup map ``{ lowerCaseBareTag: composerField }`` from palette data.
 *
 * Preconditions:
 *   - ``palette`` is the response from /anima_prompt_helper/palette
 *     (may be null / malformed — we degrade gracefully).
 * Postconditions:
 *   - Returns ``Map<string, string>`` keyed by lower-case bare tag.
 *   - Categories listed in ``CATEGORY_DEFAULT_TARGET`` map to their composer
 *     field. Categories without a mapping default to ``general``.
 *
 * @param {Object|null} palette
 * @returns {Map<string, string>}
 */
export function buildTagToFieldMap(palette) {
  /** @type {Map<string, string>} */
  const map = new Map();
  if (!palette || !Array.isArray(palette.categories)) return map;
  for (const cat of palette.categories) {
    if (!cat || !Array.isArray(cat.tags)) continue;
    const field = CATEGORY_DEFAULT_TARGET[cat.id] || "general";
    for (const t of cat.tags) {
      if (t && typeof t.tag === "string" && t.tag.trim()) {
        map.set(t.tag.trim().toLowerCase(), field);
      }
      if (t && Array.isArray(t.aliases)) {
        for (const alias of t.aliases) {
          if (typeof alias === "string" && alias.trim()) {
            // Don't clobber an existing primary mapping with an alias.
            const key = alias.trim().toLowerCase();
            if (!map.has(key)) map.set(key, field);
          }
        }
      }
    }
  }
  return map;
}

/**
 * Build a lookup map ``{ characterTag: presetId }`` from the character preset
 * store. Used to nudge canonical character tokens into the ``character``
 * field, since the global palette only covers a tiny curated subset of
 * Danbooru characters.
 *
 * @param {Array<Object>|null} presets - merged character presets
 * @returns {Map<string, string>}
 */
export function buildCharacterTagMap(presets) {
  /** @type {Map<string, string>} */
  const map = new Map();
  if (!Array.isArray(presets)) return map;
  for (const p of presets) {
    if (!p || typeof p !== "object") continue;
    const character = typeof p.character === "string" ? p.character : "";
    if (!character) continue;
    for (const tok of character.split(",")) {
      const t = tok.trim().toLowerCase();
      if (t) map.set(t, p.id || character);
    }
    const series = typeof p.series === "string" ? p.series : "";
    if (series) {
      for (const tok of series.split(",")) {
        const t = tok.trim().toLowerCase();
        // Series tags should land in the ``series`` field. We override any
        // earlier mapping (e.g. from "character") because preset metadata
        // is more reliable than overlap accidents.
        if (t) map.set(t, "series");
      }
    }
  }
  return map;
}

/**
 * Classify a single token into a composer field.
 *
 * @param {string} token - the raw token (may include weight syntax)
 * @param {Map<string, string>} paletteMap - from ``buildTagToFieldMap``
 * @param {Map<string, string>} characterMap - from ``buildCharacterTagMap``
 * @returns {string} one of COMPOSER_FIELDS
 */
export function classifyToken(token, paletteMap, characterMap) {
  const bare = _bareTag(token);
  if (!bare) return "general";
  const low = bare.toLowerCase();

  // Artist: ``@something`` overrides everything else.
  if (bare.startsWith("@")) return "artist";

  // Hard rating values: the rating widget only accepts one of four strings.
  if (_RATING_VALUES.has(low)) return "rating";

  // Quality whitelist
  if (_QUALITY_TOKENS.has(low)) return "quality";

  // Count heuristics
  for (const re of _COUNT_PATTERNS) {
    if (re.test(low)) return "count";
  }

  // Year heuristics
  for (const re of _YEAR_PATTERNS) {
    if (re.test(low)) return "year";
  }

  // Character preset map
  if (characterMap && characterMap.has(low)) {
    return characterMap.get(low);
  }

  // Palette lookup
  if (paletteMap && paletteMap.has(low)) {
    return paletteMap.get(low);
  }

  return "general";
}

/**
 * Tokenize a prompt string, preserving weight syntax and trimming.
 *
 * The "natural language" portion of the prompt (everything after the first
 * ``". "`` sequence that joins the comma block to the NL block in Anima's
 * canonical layout) is treated as a single token tagged for ``natural_language``.
 *
 * @param {string} text
 * @returns {{tokens: string[], naturalLanguage: string}}
 */
export function tokenizePrompt(text) {
  const s = String(text || "");
  if (!s.trim()) return { tokens: [], naturalLanguage: "" };

  // Detect ``" .... ". sentence."`` split — Anima emits a single ``. `` between
  // the comma block and the NL block. We use a lookahead for a capital letter
  // or for a long span (>= 20 chars without commas) as the NL heuristic.
  let commaBlock = s;
  let nl = "";
  const splitIdx = s.search(/\.\s+(?=[A-Z(])/);
  if (splitIdx >= 0) {
    const candidateTail = s.slice(splitIdx + 1).trim();
    // Only treat as NL if the tail has > 1 sentence-like fragment AND
    // contains relatively few commas (lots of commas suggests it's just
    // more tags, not natural language).
    const commaCount = (candidateTail.match(/,/g) || []).length;
    const wordCount = candidateTail.split(/\s+/).length;
    if (wordCount > 5 && commaCount < wordCount / 2) {
      commaBlock = s.slice(0, splitIdx);
      nl = candidateTail;
    }
  }

  // Split on commas, but allow weighted tokens ``(foo, bar:1.2)`` to slip
  // through by counting parens.
  const tokens = [];
  let depth = 0;
  let buf = "";
  for (const ch of commaBlock) {
    if (ch === "(") depth++;
    else if (ch === ")") depth = Math.max(0, depth - 1);
    if (ch === "," && depth === 0) {
      const t = buf.trim();
      if (t) tokens.push(t);
      buf = "";
    } else {
      buf += ch;
    }
  }
  const last = buf.trim();
  if (last) tokens.push(last);

  return { tokens, naturalLanguage: nl };
}

/**
 * Classify a full prompt string into 9 composer field buckets.
 *
 * Preconditions:
 *   - ``text`` is a string (possibly empty).
 *   - ``paletteMap``/``characterMap`` are Maps (possibly empty).
 *   - ``preExtractedFields`` is the optional ``anima_fields`` dict returned by
 *     the backend when the source image already had AnimaPromptComposer
 *     widget values. When present, we trust it for the rating/year/quality
 *     buckets but still re-classify the comma-separated general block so the
 *     UI can offer per-token toggles.
 *
 * Postconditions:
 *   - Returns ``{ buckets: { field: string[] }, unknown: string[] }`` where
 *     each bucket holds the tokens that fell into it (in source order, with
 *     duplicates removed). ``unknown`` mirrors ``buckets.general`` for callers
 *     that want to highlight "uncategorized" tokens separately.
 *
 * @param {string} text
 * @param {Map<string, string>} paletteMap
 * @param {Map<string, string>} characterMap
 * @param {Object|null} [preExtractedFields]
 * @returns {{buckets: Object<string, string[]>, unknown: string[]}}
 */
export function classifyPrompt(text, paletteMap, characterMap, preExtractedFields) {
  /** @type {Object<string, string[]>} */
  const buckets = {};
  for (const f of COMPOSER_FIELDS) buckets[f] = [];

  // Seen tracks normalized tokens already added to any bucket so we dedupe.
  const seen = new Set();

  const pushUnique = (field, token) => {
    const key = _bareTag(token).toLowerCase();
    if (!key || seen.has(key)) return;
    seen.add(key);
    buckets[field].push(token.trim());
  };

  // Honor backend-extracted Anima fields first — they're the source of truth
  // for the original layout and let us skip heuristics for "rating" which
  // is a combo widget that won't accept anything outside the allowed set.
  if (preExtractedFields && typeof preExtractedFields === "object") {
    for (const f of COMPOSER_FIELDS) {
      const v = preExtractedFields[f];
      if (typeof v !== "string" || !v.trim()) continue;
      if (f === "natural_language" || f === "rating") {
        // These behave as single-value fields — store the trimmed string verbatim.
        pushUnique(f, v.trim());
        continue;
      }
      // The other comma-separated fields are exploded into individual tokens
      // so the user can toggle each one in the UI.
      const { tokens } = tokenizePrompt(v);
      for (const t of tokens) {
        pushUnique(f, t);
      }
    }
    return { buckets, unknown: buckets.general.slice() };
  }

  // No pre-extracted fields — classify each token individually.
  const { tokens, naturalLanguage } = tokenizePrompt(text);
  for (const tok of tokens) {
    const field = classifyToken(tok, paletteMap, characterMap);
    pushUnique(field, tok);
  }
  if (naturalLanguage) {
    pushUnique("natural_language", naturalLanguage);
  }

  return { buckets, unknown: buckets.general.slice() };
}
