/**
 * negative_panel.js — DOM panel injection for AnimaNegativePromptComposer nodes
 *
 * Builds and wires the palette panel inside a LiteGraph node.
 * Counterpart to panel.js; reuses PaletteStore but targets negative fields.
 */

import { PaletteStore } from "./palette.js";
import {
  NEGATIVE_FIELD_NAMES,
  NEGATIVE_FIELD_LABELS,
  addTagToNegativeField,
  assembleNegativePreview,
} from "./negative_composer.js";

// References to module-scope caches (set via setNegativeCaches)
let _paletteCache = null;
let _specCache = null;

/**
 * Called by the main extension to pass down the shared caches.
 * @param {Object|null} paletteCache
 * @param {Object|null} specCache
 */
export function setNegativeCaches(paletteCache, specCache) {
  _paletteCache = paletteCache;
  _specCache = specCache;
}

/**
 * Debounce utility (used internally).
 * @param {Function} fn
 * @param {number} ms
 * @returns {Function}
 */
function debounce(fn, ms) {
  let t = null;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
}

/**
 * Render inline validation badges on the badge bar.
 * Checks LONG_PROMPT (> 3000 chars) and EMPTY_PROMPT.
 *
 * @param {HTMLElement} badgeBar
 * @param {string} assembled
 */
function renderNegativeBadges(badgeBar, assembled) {
  while (badgeBar.firstChild) badgeBar.removeChild(badgeBar.firstChild);

  const frag = document.createDocumentFragment();
  const len = assembled.length;

  /**
   * Build an accessible badge with a visually-hidden severity prefix and an icon.
   * @param {string} sev - "error"|"warning"|"info"
   * @param {string} icon - visible icon prefix
   * @param {string} label - visible label text
   * @param {string} tip - tooltip text
   * @returns {HTMLElement}
   */
  function makeBadge(sev, icon, label, tip) {
    const span = document.createElement("span");
    span.className = "aph-badge aph-sev-" + sev;
    span.title = tip;
    const srSpan = document.createElement("span");
    srSpan.className = "sr-only";
    srSpan.textContent = sev + ": ";
    span.appendChild(srSpan);
    span.appendChild(document.createTextNode(icon + label));
    return span;
  }

  if (len === 0) {
    frag.appendChild(makeBadge("info", "i ", "EMPTY_PROMPT", "All negative fields are empty."));
  } else if (len > 3000) {
    frag.appendChild(makeBadge("warning", "! ", "LONG_PROMPT", "Assembled negative prompt exceeds 3000 characters."));
  }

  // Always show char count
  const lenSpan = document.createElement("span");
  lenSpan.className = "aph-badge aph-sev-info aph-len-badge";
  lenSpan.textContent = len + " chars";
  frag.appendChild(lenSpan);

  badgeBar.appendChild(frag);
}

/**
 * Default palette category to pre-select for the negative panel.
 * "style" covers effects/artifacts which are most useful as negatives.
 */
const DEFAULT_NEGATIVE_TAB = "style";

/**
 * Injects the negative palette panel DOM widget into the given node.
 * @param {Object} node - LiteGraph node instance
 */
export function injectNegativePalettePanel(node) {
  // --- Build DOM structure ---
  const panelEl = document.createElement("div");
  panelEl.className = "aph-panel aph-negative-panel";

  // --- Panel header: icon + title ---
  const headerEl = document.createElement("div");
  headerEl.className = "aph-header";
  const headerIcon = document.createElement("img");
  headerIcon.className = "aph-header-icon";
  headerIcon.src = "/extensions/anima-prompt-helper/assets/icon.svg";
  headerIcon.setAttribute("alt", "");
  const headerTitle = document.createElement("span");
  headerTitle.className = "aph-header-title";
  headerTitle.textContent = "Anima Negative Prompt Composer";
  headerEl.appendChild(headerIcon);
  headerEl.appendChild(headerTitle);

  // --- Tab strip ---
  const tabStrip = document.createElement("div");
  tabStrip.className = "aph-tab-strip";

  // --- Search input ---
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.className = "aph-search";
  searchInput.placeholder = "Search tags…";
  searchInput.setAttribute("aria-label", "Search tags");

  // --- Tag grid ---
  const tagGrid = document.createElement("div");
  tagGrid.className = "aph-tag-grid";
  tagGrid.setAttribute("role", "tabpanel");

  // --- Target field dropdown ---
  const targetFieldLabel = document.createElement("label");
  targetFieldLabel.className = "aph-target-field-label";
  targetFieldLabel.textContent = "Add tags to:";

  const targetFieldSelect = document.createElement("select");
  targetFieldSelect.className = "aph-target-field";
  targetFieldSelect.setAttribute("aria-label", "Apply tags to which negative field");

  for (const fieldName of NEGATIVE_FIELD_NAMES) {
    const opt = document.createElement("option");
    opt.value = fieldName;
    opt.textContent = NEGATIVE_FIELD_LABELS[fieldName] || fieldName;
    targetFieldSelect.appendChild(opt);
  }
  // Default to style_negative (index 2)
  targetFieldSelect.value = "style_negative";

  const fieldRow = document.createElement("div");
  fieldRow.className = "aph-field-row";
  fieldRow.appendChild(targetFieldLabel);
  fieldRow.appendChild(targetFieldSelect);

  // --- Preview textarea ---
  const previewTextarea = document.createElement("textarea");
  previewTextarea.className = "aph-preview aph-negative-preview";
  previewTextarea.readOnly = true;
  previewTextarea.rows = 3;
  previewTextarea.placeholder = "Assembled negative prompt preview…";
  previewTextarea.setAttribute("aria-label", "Assembled prompt preview");
  previewTextarea.setAttribute("aria-readonly", "true");

  // --- Badge bar ---
  const badgeBar = document.createElement("div");
  badgeBar.className = "aph-badges";
  badgeBar.setAttribute("role", "status");
  badgeBar.setAttribute("aria-live", "polite");

  panelEl.appendChild(headerEl);
  panelEl.appendChild(tabStrip);
  panelEl.appendChild(searchInput);
  panelEl.appendChild(tagGrid);
  panelEl.appendChild(fieldRow);
  panelEl.appendChild(previewTextarea);
  panelEl.appendChild(badgeBar);

  // --- Register as a DOM widget ---
  // Some ComfyUI builds ignore options.computeSize, so we assign the
  // computeSize callback directly on the returned widget object as well.
  const _panelWidget = node.addDOMWidget(
    "anima_negative_palette_panel",
    "div",
    panelEl,
    { serialize: false },
  );
  if (_panelWidget) {
    _panelWidget.computeSize = function (width) {
      const h = panelEl.scrollHeight || 500;
      return [width, h + 16];
    };
  }

  // --- Set initial node size ---
  node.size = [
    Math.max(node.size[0], 680),
    Math.max(node.size[1], 500),
  ];

  // --- Force an initial size sync once the DOM has laid out. ---
  requestAnimationFrame(() => {
    const h = panelEl.scrollHeight || 500;
    const targetH = h + 60;
    if (node.size[1] < targetH) {
      node.size[1] = targetH;
      node.graph && node.graph.setDirtyCanvas(true, true);
    }
  });

  // --- Auto-resize node when panel content changes ---
  // _resizing flag + requestAnimationFrame guard prevents a feedback loop:
  // size write → setDirtyCanvas → computeSize → DOM relayout → ResizeObserver
  // re-fires.  The 8px hysteresis check is kept as a secondary guard.
  let _resizing = false;
  const _resizeObs = new ResizeObserver(() => {
    if (!node.graph || _resizing) return;
    _resizing = true;
    requestAnimationFrame(() => {
      const h = panelEl.scrollHeight || 500;
      const targetH = h + 60;
      if (node.size[1] < targetH - 8) {
        node.size[1] = targetH;
        node.graph.setDirtyCanvas(true, true);
      }
      _resizing = false;
    });
  });
  _resizeObs.observe(panelEl);

  // --- State ---
  let currentCategoryId = null;
  const timers = [];

  // --- Helper: get the currently selected target field ---
  function getTargetField() {
    return targetFieldSelect.value || "style_negative";
  }

  // --- Helper: render the tag grid ---
  function renderGrid() {
    if (!_paletteCache) {
      while (tagGrid.firstChild) tagGrid.removeChild(tagGrid.firstChild);
      const msg = document.createElement("p");
      msg.className = "aph-load-error";
      msg.textContent = "Palette failed to load. Check the console for details.";
      tagGrid.appendChild(msg);
      return;
    }

    const query = searchInput.value || "";
    PaletteStore.renderTagButtons(tagGrid, currentCategoryId, query, (tag) => {
      addTagToNegativeField(node, getTargetField(), tag);
      refreshPreview();
    });
  }

  // --- Helper: refresh preview textarea and badges ---
  function refreshPreview() {
    try {
      const assembled = assembleNegativePreview(node, _specCache);
      previewTextarea.value = assembled;
      renderNegativeBadges(badgeBar, assembled);
    } catch (err) {
      console.warn("[AnimaPromptHelper] refreshNegativePreview error:", err);
    }
  }

  // --- Tab selection ---
  function selectCategory(catId) {
    currentCategoryId = catId;
    // Update aria-labelledby on the tabpanel to point at the active tab button
    const activeBtn = tabStrip.querySelector(".aph-tab-btn.aph-tab-active");
    if (activeBtn) {
      if (!activeBtn.id) {
        activeBtn.id = "aph-neg-tab-" + catId.replace(/[^a-z0-9_-]/gi, "_");
      }
      tagGrid.setAttribute("aria-labelledby", activeBtn.id);
    }
    renderGrid();
  }

  // --- Initialize palette panel ---
  function initPanel() {
    if (!_paletteCache) {
      renderGrid();
      refreshPreview();
      return;
    }

    PaletteStore.init(_paletteCache);
    const categories = PaletteStore.getCategories();

    // Pre-select DEFAULT_NEGATIVE_TAB if available, otherwise first category
    const defaultCat = categories.find((c) => c.id === DEFAULT_NEGATIVE_TAB);
    const firstCat = categories.length > 0 ? categories[0].id : null;
    currentCategoryId = defaultCat ? defaultCat.id : firstCat;

    // Render tab strip
    PaletteStore.renderTabStrip(tabStrip, currentCategoryId, (catId) => {
      selectCategory(catId);
    });

    // Set initial aria-labelledby on tabpanel
    const activeBtn = tabStrip.querySelector(".aph-tab-btn.aph-tab-active");
    if (activeBtn && currentCategoryId) {
      if (!activeBtn.id) {
        activeBtn.id = "aph-neg-tab-" + currentCategoryId.replace(/[^a-z0-9_-]/gi, "_");
      }
      tagGrid.setAttribute("aria-labelledby", activeBtn.id);
    }

    renderGrid();
    refreshPreview();
  }

  // Run init (may be deferred if caches not ready yet)
  initPanel();

  // --- Search input (debounced 400 ms) ---
  const debouncedSearch = debounce(() => {
    renderGrid();
  }, 400);

  searchInput.addEventListener("input", debouncedSearch);

  // Esc clears the search input when focused
  const onSearchKeydown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      searchInput.value = "";
      renderGrid();
    }
  };
  searchInput.addEventListener("keydown", onSearchKeydown);

  // --- Poll for widget changes (refreshes preview when user types in a field) ---
  const pollTimer = setInterval(() => {
    refreshPreview();
  }, 500);
  timers.push(pollTimer);

  // --- Cleanup on node removal ---
  const origOnRemoved = typeof node.onRemoved === "function" ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    _resizeObs.disconnect();
    for (const t of timers) clearInterval(t);
    searchInput.removeEventListener("input", debouncedSearch);
    searchInput.removeEventListener("keydown", onSearchKeydown);
    if (origOnRemoved) origOnRemoved();
  };

  // Expose initPanel so the main module can re-call after caches arrive
  node._aphNegInitPanel = initPanel;
}
