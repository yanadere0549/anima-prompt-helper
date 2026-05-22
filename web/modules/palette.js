/**
 * palette.js — PaletteStore singleton
 *
 * Manages the tag palette data fetched from the backend.
 * Provides methods to render tab strips and tag button grids.
 */

// Module-scope state
let _categoriesById = {};
let _orderedCategories = [];

/**
 * Initialize the store with raw palette data from the API.
 * @param {Object} paletteData - Response from GET /anima_prompt_helper/palette
 */
function init(paletteData) {
  _categoriesById = {};
  _orderedCategories = [];

  if (!paletteData || !Array.isArray(paletteData.categories)) {
    console.warn("[AnimaPromptHelper] PaletteStore.init: invalid palette data");
    return;
  }

  for (const cat of paletteData.categories) {
    _categoriesById[cat.id] = cat;
  }

  // Preserve the order from the data (already in canonical order from backend)
  _orderedCategories = paletteData.categories.slice();
}

/**
 * Returns sorted array of categories.
 * @returns {Array<{id, label, tags}>}
 */
function getCategories() {
  return _orderedCategories.slice();
}

/**
 * Returns unique subcategory ids in the order they first appear in the category's tags.
 * Tags with missing/empty subcategory are excluded.
 *
 * Preconditions:
 *   - categoryId is a known category id (otherwise returns []).
 * Postconditions:
 *   - Returns string[] of unique subcategory values, preserving first-appearance order.
 *
 * @param {string} categoryId
 * @returns {string[]}
 */
function getSubcategories(categoryId) {
  const cat = _categoriesById[categoryId];
  if (!cat || !Array.isArray(cat.tags)) return [];
  const seen = new Set();
  const result = [];
  for (const t of cat.tags) {
    const sub = (t.subcategory || "").trim();
    if (!sub || seen.has(sub)) continue;
    seen.add(sub);
    result.push(sub);
  }
  return result;
}

/**
 * Returns tags for a category filtered by a search query and optional subcategory.
 * Subcategory filter is applied first, then search match.
 * Case-insensitive substring match against tag, display (if present), or any alias.
 * Sorted by count desc (used as tier proxy), then alphabetically.
 *
 * Preconditions:
 *   - categoryId is a known category id (otherwise returns []).
 * Postconditions:
 *   - If subcategoryId is provided (non-empty), only tags with matching subcategory are returned.
 *   - If subcategoryId is undefined/null/empty, all tags in the category are candidates (backward compatible).
 *
 * @param {string} categoryId
 * @param {string} query
 * @param {string} [subcategoryId] - optional; if provided, only tags with matching subcategory are returned
 * @returns {Array<Object>}
 */
function getTagsFiltered(categoryId, query, subcategoryId) {
  const cat = _categoriesById[categoryId];
  if (!cat || !Array.isArray(cat.tags)) return [];

  const q = (query || "").trim().toLowerCase();

  let tags = cat.tags;
  if (subcategoryId) {
    tags = tags.filter((t) => (t.subcategory || "") === subcategoryId);
  }
  if (q) {
    tags = tags.filter((t) => {
      if (t.tag && t.tag.toLowerCase().includes(q)) return true;
      if (t.display && t.display.toLowerCase().includes(q)) return true;
      if (Array.isArray(t.aliases)) {
        for (const alias of t.aliases) {
          if (alias.toLowerCase().includes(q)) return true;
        }
      }
      return false;
    });
  }

  // Sort by count desc, then alpha
  return tags.slice().sort((a, b) => {
    const countDiff = (b.count || 0) - (a.count || 0);
    if (countDiff !== 0) return countDiff;
    return (a.tag || "").localeCompare(b.tag || "");
  });
}

/**
 * Returns a single random tag from a category (optionally filtered by subcategory).
 * Uses tier as weight when useTierWeight=true (tier 5 → weight 5, default 1).
 * Tags without tier or with tier <= 0 get weight 1.
 *
 * Preconditions:
 *   - categoryId is known. subcategoryId optional.
 * Postconditions:
 *   - Returns a tag object {tag, display, tier, aliases, notes, subcategory} or null if no candidates.
 *
 * @param {string} categoryId
 * @param {string|null} [subcategoryId]
 * @param {boolean} [useTierWeight=true]
 * @returns {Object|null}
 */
function getRandomTag(categoryId, subcategoryId, useTierWeight = true) {
  const cat = _categoriesById[categoryId];
  if (!cat || !Array.isArray(cat.tags)) return null;
  let tags = cat.tags;
  if (subcategoryId) {
    tags = tags.filter((t) => (t.subcategory || "") === subcategoryId);
  }
  if (tags.length === 0) return null;

  if (!useTierWeight) {
    return tags[Math.floor(Math.random() * tags.length)];
  }

  // Cumulative weight selection (tier value used as weight; falls back to 1)
  let totalWeight = 0;
  const weights = tags.map((t) => {
    const w = typeof t.tier === "number" && t.tier > 0 ? t.tier : 1;
    totalWeight += w;
    return w;
  });
  let r = Math.random() * totalWeight;
  for (let i = 0; i < tags.length; i++) {
    r -= weights[i];
    if (r <= 0) return tags[i];
  }
  return tags[tags.length - 1];
}

/**
 * Clears container and renders one <button> per category.
 * Clicking a button calls onSelect(categoryId).
 * The active category button gets the aph-tab-active class.
 * Supports Arrow Left/Right keyboard navigation within the tab strip.
 *
 * @param {HTMLElement} container
 * @param {string} activeCategoryId
 * @param {Function} onSelect
 * @param {Array<{id: string, label: string}>|null} [overrideCats] - optional
 *   pre-filtered category list; if omitted, all categories are used.
 */
function renderTabStrip(container, activeCategoryId, onSelect, overrideCats) {
  while (container.firstChild) container.removeChild(container.firstChild);

  // ARIA: tab list role and label
  container.setAttribute("role", "tablist");
  container.setAttribute("aria-label", "Tag categories");

  const cats = overrideCats != null ? overrideCats : getCategories();
  for (const cat of cats) {
    const isActive = cat.id === activeCategoryId;
    const btn = document.createElement("button");
    btn.className = "aph-tab-btn" + (isActive ? " aph-tab-active" : "");
    btn.textContent = cat.label || cat.id;
    btn.dataset.catId = cat.id;
    // ARIA tab attributes
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", isActive ? "true" : "false");
    btn.setAttribute("tabindex", isActive ? "0" : "-1");
    btn.addEventListener("click", () => {
      // Update active state
      const siblings = container.querySelectorAll(".aph-tab-btn");
      siblings.forEach((s) => {
        s.classList.remove("aph-tab-active");
        s.setAttribute("aria-selected", "false");
        s.setAttribute("tabindex", "-1");
      });
      btn.classList.add("aph-tab-active");
      btn.setAttribute("aria-selected", "true");
      btn.setAttribute("tabindex", "0");
      btn.focus();
      onSelect(cat.id);
    });
    container.appendChild(btn);
  }

  // Arrow keyboard navigation for the tab strip. Supports both horizontal
  // (Left/Right) and vertical (Up/Down) layouts so the same strip works
  // whether it is rendered as a row or a sidebar.
  container.addEventListener("keydown", (e) => {
    const forward = e.key === "ArrowRight" || e.key === "ArrowDown";
    const backward = e.key === "ArrowLeft" || e.key === "ArrowUp";
    if (!forward && !backward) return;
    const tabs = Array.from(container.querySelectorAll(".aph-tab-btn"));
    const idx = tabs.indexOf(document.activeElement);
    if (idx === -1) return;
    e.preventDefault();
    const next = forward
      ? (idx + 1) % tabs.length
      : (idx - 1 + tabs.length) % tabs.length;
    tabs[next].focus();
  });
}

/**
 * Clears container and renders one <button class="aph-tag-btn"> per matching tag.
 * Uses a document fragment for performance with 100+ buttons.
 * Clicking a button calls onAdd(tag).
 * Each button has a data-tag attribute set to the tag value for external identification.
 *
 * Preconditions:
 *   - container is a valid HTMLElement. onAdd is a function.
 * Postconditions:
 *   - container is repopulated with buttons for matching tags, each with data-tag set.
 *   - If no tags match, a "no tags" message paragraph is shown instead.
 *
 * @param {HTMLElement} container
 * @param {string} categoryId
 * @param {string} query
 * @param {Function} onAdd
 * @param {string} [subcategoryId] - optional; if provided, only tags with matching subcategory are rendered
 */
function renderTagButtons(container, categoryId, query, onAdd, subcategoryId) {
  while (container.firstChild) container.removeChild(container.firstChild);

  const tags = getTagsFiltered(categoryId, query, subcategoryId);

  if (tags.length === 0) {
    const msg = document.createElement("p");
    msg.className = "aph-no-tags";
    msg.textContent = query ? "No tags match your search." : "No tags in this category.";
    container.appendChild(msg);
    return;
  }

  const frag = document.createDocumentFragment();
  for (const t of tags) {
    const btn = document.createElement("button");
    btn.className = "aph-tag-btn";
    btn.textContent = t.tag;
    btn.dataset.tag = t.tag;
    // ARIA: describe the action for screen readers
    btn.setAttribute("aria-label", "Add tag: " + t.tag);
    if (t.count) {
      btn.title = String(t.count);
    }
    btn.addEventListener("click", () => onAdd(t.tag));
    // Keyboard: Enter/Space activate (button default handles Space; guard Enter)
    btn.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onAdd(t.tag);
      }
    });
    frag.appendChild(btn);
  }
  container.appendChild(frag);
}

export const PaletteStore = {
  init,
  getCategories,
  getSubcategories,
  getTagsFiltered,
  getRandomTag,
  renderTabStrip,
  renderTagButtons,
};
