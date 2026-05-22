/**
 * artist_suggest.js — autocomplete dropdown for the AnimaPromptComposer
 * "artist" field.
 *
 * Loads a trimmed [{t: "@tag", c: postCount}, ...] list from the backend
 * once at startup, then on every keystroke in the artist textarea:
 *   1. extracts the "current token" (text between the previous comma/newline
 *      and the caret),
 *   2. substring-matches it against the artist tags (case-insensitive,
 *      ignoring a leading "@"),
 *   3. shows up to 20 matches as a floating dropdown anchored below the
 *      textarea, ordered by postCount descending.
 *
 * Selection replaces the current token with the chosen tag and appends
 * ", " when there is no further input after the caret.
 */

import { getFieldWidget } from "./composer.js";

const MAX_SUGGESTIONS = 20;
const ATTACH_RETRY_MAX = 30;
const ATTACH_RETRY_INTERVAL_MS = 100;

let _artists = null;

/**
 * Stores the loaded artist index. Called once at extension setup.
 * @param {Array<{t: string, c: number}>|null} arr
 */
export function setArtistList(arr) {
  _artists = Array.isArray(arr) ? arr : null;
}

/**
 * Returns true if the artist index has been populated.
 * @returns {boolean}
 */
export function hasArtistList() {
  return Array.isArray(_artists) && _artists.length > 0;
}

/**
 * Attaches the autocomplete behaviour to the artist textarea of a node.
 * Polls briefly for the textarea element because ComfyUI sometimes creates
 * the DOM widget asynchronously after onNodeCreated fires.
 *
 * @param {Object} node - LiteGraph node instance for AnimaPromptComposer
 */
export function attachArtistSuggest(node) {
  if (!node || !hasArtistList()) return;
  const widget = getFieldWidget(node, "artist");
  if (!widget) return;

  let attempts = 0;
  const tryAttach = () => {
    const el = widget.element || widget.inputEl;
    if (el && el.tagName) {
      bindAutocomplete(el);
      return;
    }
    attempts++;
    if (attempts < ATTACH_RETRY_MAX) {
      setTimeout(tryAttach, ATTACH_RETRY_INTERVAL_MS);
    }
  };
  tryAttach();
}

/**
 * Normalises a tag or query for case-insensitive substring matching.
 * Strips a leading "@" so queries with or without it behave the same.
 *
 * @param {string} s
 * @returns {string}
 */
function normalize(s) {
  return (s || "").toLowerCase().replace(/^@/, "");
}

/**
 * Identifies the comma-delimited token surrounding the caret in a multiline
 * value. Boundaries are "," and "\n". Returns positions for both the raw
 * span and the inner trimmed span so the caller can replace just the
 * meaningful text and preserve surrounding whitespace.
 *
 * @param {string} value
 * @param {number} caret
 * @returns {{start: number, end: number, trimmedStart: number, trimmedEnd: number, text: string}}
 */
function getCurrentToken(value, caret) {
  let start = caret;
  while (start > 0 && value[start - 1] !== "," && value[start - 1] !== "\n") {
    start--;
  }
  let end = caret;
  while (end < value.length && value[end] !== "," && value[end] !== "\n") {
    end++;
  }
  const raw = value.slice(start, end);
  const leadingMatch = raw.match(/^\s*/);
  const trailingMatch = raw.match(/\s*$/);
  const leading = leadingMatch ? leadingMatch[0].length : 0;
  const trailing = trailingMatch ? trailingMatch[0].length : 0;
  const innerLen = Math.max(0, raw.length - leading - trailing);
  return {
    start,
    end,
    trimmedStart: start + leading,
    trimmedEnd: start + leading + innerLen,
    text: raw.slice(leading, leading + innerLen),
  };
}

/**
 * Substring-matches a normalised query against the artist index.
 * Stops once MAX_SUGGESTIONS are found. The artist index is already sorted
 * by postCount descending, so the first matches are also the most popular.
 *
 * @param {string} query
 * @returns {Array<{t: string, c: number}>}
 */
function findMatches(query) {
  const q = normalize(query);
  if (!q) return [];
  const results = [];
  const list = _artists;
  for (let i = 0; i < list.length; i++) {
    const tagNorm = normalize(list[i].t);
    if (tagNorm.indexOf(q) >= 0) {
      results.push(list[i]);
      if (results.length >= MAX_SUGGESTIONS) break;
    }
  }
  return results;
}

/**
 * Formats a post count for display ("18658" -> "18k", "899" -> "899").
 * @param {number} n
 * @returns {string}
 */
function formatCount(n) {
  if (!Number.isFinite(n)) return "";
  if (n >= 10000) return Math.round(n / 1000) + "k";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

/**
 * Converts a raw artist tag from search.json into the form expected by
 * downstream image-generation prompts: underscores become spaces, and both
 * parentheses are backslash-escaped so they are read as literal characters
 * rather than weight-emphasis syntax.
 *
 *   "@bee_(deadflow)" -> "@bee \\(deadflow\\)"
 *   "@chouzuki_maryou" -> "@chouzuki maryou"
 *   "@dairi" -> "@dairi"
 *
 * @param {string} raw
 * @returns {string}
 */
export function formatArtistTagForInsert(raw) {
  if (!raw) return "";
  return raw
    .replace(/_/g, " ")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}

/**
 * Wires up event listeners on the given textarea and creates a single
 * floating dropdown element appended to document.body. Idempotent —
 * re-binding the same element is a no-op.
 *
 * @param {HTMLElement} textarea
 */
function bindAutocomplete(textarea) {
  if (textarea.dataset.aphArtistSuggest === "1") return;
  textarea.dataset.aphArtistSuggest = "1";

  const dropdown = document.createElement("div");
  dropdown.className = "aph-artist-suggest";
  dropdown.style.display = "none";
  document.body.appendChild(dropdown);

  let activeIdx = -1;
  let currentMatches = [];
  let visible = false;
  let rafId = null;

  function positionDropdown() {
    const rect = textarea.getBoundingClientRect();
    dropdown.style.left = rect.left + "px";
    dropdown.style.top = (rect.bottom + 2) + "px";
    const width = Math.max(rect.width, 240);
    dropdown.style.width = width + "px";
  }

  function startRepositionLoop() {
    if (rafId !== null) return;
    const tick = () => {
      if (!visible) {
        rafId = null;
        return;
      }
      positionDropdown();
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
  }

  function show() {
    dropdown.style.display = "block";
    visible = true;
    startRepositionLoop();
  }

  function hide() {
    dropdown.style.display = "none";
    visible = false;
    activeIdx = -1;
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  function updateActiveStyles() {
    const children = dropdown.children;
    for (let i = 0; i < children.length; i++) {
      children[i].classList.toggle("active", i === activeIdx);
    }
    if (activeIdx >= 0 && children[activeIdx]) {
      const el = children[activeIdx];
      const top = el.offsetTop;
      const bottom = top + el.offsetHeight;
      if (top < dropdown.scrollTop) {
        dropdown.scrollTop = top;
      } else if (bottom > dropdown.scrollTop + dropdown.clientHeight) {
        dropdown.scrollTop = bottom - dropdown.clientHeight;
      }
    }
  }

  function render() {
    dropdown.innerHTML = "";
    if (!currentMatches.length) {
      hide();
      return;
    }
    currentMatches.forEach((m, idx) => {
      const item = document.createElement("div");
      item.className = "aph-artist-suggest-item";
      if (idx === activeIdx) item.classList.add("active");

      const tagSpan = document.createElement("span");
      tagSpan.className = "aph-artist-suggest-tag";
      tagSpan.textContent = formatArtistTagForInsert(m.t);

      const countSpan = document.createElement("span");
      countSpan.className = "aph-artist-suggest-count";
      countSpan.textContent = formatCount(m.c);

      item.appendChild(tagSpan);
      item.appendChild(countSpan);

      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        select(idx);
      });
      item.addEventListener("mouseenter", () => {
        activeIdx = idx;
        updateActiveStyles();
      });
      dropdown.appendChild(item);
    });
    positionDropdown();
    show();
  }

  function select(idx) {
    if (idx < 0 || idx >= currentMatches.length) return;
    const tag = formatArtistTagForInsert(currentMatches[idx].t);
    const tok = getCurrentToken(textarea.value, textarea.selectionStart);
    const before = textarea.value.slice(0, tok.trimmedStart);
    const after = textarea.value.slice(tok.trimmedEnd);
    const restHasContent = after.trim().length > 0;

    let insertion = tag;
    let newAfter = after;
    if (!restHasContent) {
      insertion = tag + ", ";
      newAfter = "";
    }
    const newValue = before + insertion + newAfter;
    textarea.value = newValue;
    const newCaret = (before + insertion).length;
    textarea.setSelectionRange(newCaret, newCaret);
    textarea.focus();
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    hide();
  }

  function refresh() {
    const tok = getCurrentToken(textarea.value, textarea.selectionStart);
    const q = tok.text;
    if (!q || q.length < 1) {
      hide();
      return;
    }
    currentMatches = findMatches(q);
    activeIdx = currentMatches.length > 0 ? 0 : -1;
    render();
  }

  textarea.addEventListener("input", refresh);
  textarea.addEventListener("click", refresh);
  textarea.addEventListener("keyup", (e) => {
    if (
      e.key === "ArrowLeft" ||
      e.key === "ArrowRight" ||
      e.key === "Home" ||
      e.key === "End"
    ) {
      refresh();
    }
  });
  textarea.addEventListener("keydown", (e) => {
    if (!visible) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIdx = (activeIdx + 1) % currentMatches.length;
      updateActiveStyles();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIdx =
        (activeIdx - 1 + currentMatches.length) % currentMatches.length;
      updateActiveStyles();
    } else if (e.key === "Enter" || e.key === "Tab") {
      if (activeIdx >= 0) {
        e.preventDefault();
        select(activeIdx);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      hide();
    }
  });
  textarea.addEventListener("blur", () => {
    setTimeout(hide, 150);
  });
}
