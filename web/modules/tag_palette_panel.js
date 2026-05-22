/**
 * tag_palette_panel.js — DOM panel injection for AnimaTagPalette nodes (v0.5.0)
 *
 * Builds the tag palette panel for AnimaTagPalette.
 * Shows only the 26 non-Composer tabs (hair_color and below).
 * Provides:
 *   - 対象 Composer dropdown (同一グラフ内 AnimaPromptComposer を列挙)
 *   - 挿入先フィールド dropdown (TARGET_FIELD_OPTIONS)
 *   - タブ切替時に挿入先を自動更新 (CATEGORY_DEFAULT_TARGET)
 *   - 「Composerへ挿入」ボタン
 *   - タグクリック時に tags_buffer widget を更新
 *   - Subcategory dropdown (タブ下、サーチ上)
 *   - Random button (🎲) — 現在のカテゴリ+サブカテゴリからランダムタグ追加
 *   - ★ お気に入りタブ / 🕒 履歴タブ (特殊タブ)
 *   - タグボタンホバー時に ★ / − / + ボタン表示
 */

import { PaletteStore } from "./palette.js";
import {
  addTagToField,
  toggleTagInField,
  removeTagFromField,
  adjustTagWeight,
  parseWeightedTag,
} from "./composer.js";
import { CharacterPresetStore, applyPreset } from "./character_presets.js";
import {
  attachPersistence,
  getSelectedTab,
  setSelectedTab,
  getSearchQuery,
  setSearchQuery,
  getFavorites,
  toggleFavorite,
  isFavorite,
  getHistory,
  addToHistory,
  clearHistory,
  getSelectedSubcategory,
  setSelectedSubcategory,
} from "./persist.js";
import {
  COMPOSER_ONLY_TABS,
  CATEGORY_DEFAULT_TARGET,
  TARGET_FIELD_OPTIONS,
} from "./category_target_map.js";

// ---------------------------------------------------------------------------
// Special tabs (Favorites / History) — not in PaletteStore categories
// ---------------------------------------------------------------------------
const SPECIAL_TABS = [
  { id: "__favorites__", label: "★ Favorites" },
  { id: "__history__",   label: "🕒 History"   },
];

// ---------------------------------------------------------------------------
// Module-scope caches (set by the main entry point via setTagPaletteCaches)
// ---------------------------------------------------------------------------
let _paletteCache = null;
let _specCache    = null;

/**
 * Called by the main extension to pass down the shared caches.
 * @param {Object|null} paletteCache
 * @param {Object|null} specCache
 */
export function setTagPaletteCaches(paletteCache, specCache) {
  _paletteCache = paletteCache;
  _specCache    = specCache;
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

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
 * Collects all AnimaPromptComposer nodes in the same graph.
 * @param {Object} graph - LiteGraph graph instance
 * @returns {Object[]} array of composer nodes
 */
function getComposerNodes(graph) {
  if (!graph || !Array.isArray(graph._nodes)) return [];
  return graph._nodes.filter(
    (n) => n && n.type === "AnimaPromptComposer"
  );
}

// ---------------------------------------------------------------------------
// tags_buffer helpers
// ---------------------------------------------------------------------------

/**
 * Toggle a tag in the AnimaTagPalette node's ``tags_buffer`` widget.
 * Behaves like ``toggleTagInField``: if the tag is already present
 * (case-insensitive), remove it; otherwise append it. Returns one of
 * ``"added"``, ``"removed"``, or ``"noop"`` so callers can keep their
 * Composer-side mutation in sync with the buffer's state.
 *
 * Preconditions:
 *   - paletteNode has a widget named "tags_buffer".
 *   - tag is a non-empty string.
 * Postconditions:
 *   - tags_buffer widget value is updated and DOM input is notified.
 *
 * @param {Object} paletteNode
 * @param {string} tag
 * @returns {"added"|"removed"|"noop"}
 */
function toggleTagInBuffer(paletteNode, tag) {
  if (!paletteNode || !Array.isArray(paletteNode.widgets)) return "noop";
  const widget = paletteNode.widgets.find((w) => w.name === "tags_buffer");
  if (!widget) {
    console.warn("[AnimaTagPalette] toggleTagInBuffer: tags_buffer widget not found");
    return "noop";
  }

  const trimmed = (tag || "").trim();
  if (!trimmed) return "noop";

  const current = typeof widget.value === "string" ? widget.value : "";
  const parts = current
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

  const tagNorm = trimmed.toLowerCase();
  const idx = parts.findIndex((p) => {
    const { tag: bare } = parseWeightedTag(p);
    return bare.toLowerCase() === tagNorm;
  });

  let action;
  if (idx >= 0) {
    parts.splice(idx, 1);
    action = "removed";
  } else {
    parts.push(trimmed);
    action = "added";
  }

  const newVal = parts.join(", ");
  widget.value = newVal;

  const inputEl = widget.element || widget.inputEl;
  if (inputEl) {
    inputEl.value = newVal;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }

  try {
    if (
      paletteNode.graph &&
      typeof paletteNode.graph.setDirtyCanvas === "function"
    ) {
      paletteNode.graph.setDirtyCanvas(true, true);
    }
  } catch (_e) {
    // ignore
  }
  return action;
}

/**
 * Removes a tag from the AnimaTagPalette node's ``tags_buffer`` widget.
 * Comparison is case-insensitive and strip weighted syntax.
 *
 * Preconditions:
 *   - paletteNode has a widget named "tags_buffer".
 *   - tag is a non-empty string.
 * Postconditions:
 *   - tags_buffer widget value has the tag removed (if present).
 *
 * @param {Object} paletteNode
 * @param {string} tag
 */
function removeTagFromBuffer(paletteNode, tag) {
  if (!paletteNode || !Array.isArray(paletteNode.widgets)) return;
  const widget = paletteNode.widgets.find((w) => w.name === "tags_buffer");
  if (!widget) return;
  const trimmed = (tag || "").trim();
  if (!trimmed) return;
  const current = typeof widget.value === "string" ? widget.value : "";
  const parts = current
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
  const tagNorm = trimmed.toLowerCase();
  const idx = parts.findIndex((p) => {
    const { tag: bare } = parseWeightedTag(p);
    return bare.toLowerCase() === tagNorm;
  });
  if (idx < 0) return;
  parts.splice(idx, 1);
  const newVal = parts.join(", ");
  widget.value = newVal;
  const inputEl = widget.element || widget.inputEl;
  if (inputEl) {
    inputEl.value = newVal;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }
  try {
    if (paletteNode.graph && typeof paletteNode.graph.setDirtyCanvas === "function") {
      paletteNode.graph.setDirtyCanvas(true, true);
    }
  } catch (_e) {}
}

// ---------------------------------------------------------------------------
// Main panel injector
// ---------------------------------------------------------------------------

/**
 * Injects the tag palette panel DOM widget into the given AnimaTagPalette node.
 *
 * Preconditions:
 *   - ``node`` is a valid LiteGraph node of type AnimaTagPalette.
 * Postconditions:
 *   - A DOM widget is attached to ``node`` rendering category tabs,
 *     subcategory dropdown, random button, favorites/history special tabs,
 *     and tag buttons with hover actions.
 *
 * @param {Object} node - LiteGraph node instance
 */
export function injectTagPalettePanel(node) {
  attachPersistence(node);

  // --- Hide tags_buffer widget UI ---
  const bufWidget = Array.isArray(node.widgets)
    ? node.widgets.find((w) => w.name === "tags_buffer")
    : null;
  if (bufWidget) {
    bufWidget.computeSize = () => [0, -4];
    bufWidget.hidden = true;
    if (bufWidget.element instanceof HTMLElement) {
      bufWidget.element.style.display = "none";
    }
    if (bufWidget.inputEl instanceof HTMLElement) {
      bufWidget.inputEl.style.display = "none";
    }
  }

  // -------------------------------------------------------------------------
  // Build DOM structure
  // -------------------------------------------------------------------------
  const panelEl = document.createElement("div");
  panelEl.className = "aph-panel aph-tag-palette-panel";

  // --- Panel header ---
  const headerEl = document.createElement("div");
  headerEl.className = "aph-header";
  const headerIcon = document.createElement("img");
  headerIcon.className = "aph-header-icon";
  headerIcon.src = "/extensions/anima-prompt-helper/assets/icon.svg";
  headerIcon.setAttribute("alt", "");
  const headerTitle = document.createElement("span");
  headerTitle.className = "aph-header-title";
  headerTitle.textContent = "Anima Tag Palette";
  headerEl.appendChild(headerIcon);
  headerEl.appendChild(headerTitle);

  // --- Character preset dropdown ---
  const presetSelect = document.createElement("select");
  presetSelect.className = "aph-preset-select";
  presetSelect.setAttribute("aria-label", "Character preset");
  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = "-- Character preset --";
  presetSelect.appendChild(defaultOpt);
  const allPresets = CharacterPresetStore ? CharacterPresetStore.getAll() : [];
  if (allPresets.length === 0) {
    presetSelect.disabled = true;
    const unavailableOpt = document.createElement("option");
    unavailableOpt.value = "";
    unavailableOpt.textContent = "presets unavailable";
    presetSelect.appendChild(unavailableOpt);
  } else {
    for (const preset of allPresets) {
      const opt = document.createElement("option");
      opt.value = preset.id;
      opt.textContent = preset.label || preset.id;
      presetSelect.appendChild(opt);
    }
  }

  // --- Controls row: Composer selector + Field selector + Insert button ---
  const controlsEl = document.createElement("div");
  controlsEl.className = "aph-tag-palette-controls";

  const composerSelect = document.createElement("select");
  composerSelect.className = "aph-palette-composer-select";
  composerSelect.setAttribute("aria-label", "対象 AnimaPromptComposer");

  const composerDefaultOpt = document.createElement("option");
  composerDefaultOpt.value = "";
  composerDefaultOpt.textContent = "-- 対象 Composer --";
  composerSelect.appendChild(composerDefaultOpt);

  const fieldSelect = document.createElement("select");
  fieldSelect.className = "aph-palette-field-select";
  fieldSelect.setAttribute("aria-label", "挿入先フィールド");

  for (const fieldName of TARGET_FIELD_OPTIONS) {
    const opt = document.createElement("option");
    opt.value = fieldName;
    opt.textContent = fieldName;
    fieldSelect.appendChild(opt);
  }

  const insertBtn = document.createElement("button");
  insertBtn.className = "aph-palette-insert-btn";
  insertBtn.textContent = "Composerへ挿入";
  insertBtn.setAttribute("aria-label", "選択中タグをComposerへ挿入");

  controlsEl.appendChild(composerSelect);
  controlsEl.appendChild(fieldSelect);
  controlsEl.appendChild(insertBtn);

  // Warning label
  const insertWarnEl = document.createElement("p");
  insertWarnEl.className = "aph-tag-palette-warn";
  insertWarnEl.style.display = "none";

  // --- Tab strip ---
  const tabStrip = document.createElement("div");
  tabStrip.className = "aph-tab-strip";

  // --- Subcategory row: select + random button ---
  const subcatRowEl = document.createElement("div");
  subcatRowEl.className = "aph-subcat-row";

  const subcategorySelect = document.createElement("select");
  subcategorySelect.className = "aph-subcategory-select";
  subcategorySelect.setAttribute("aria-label", "サブカテゴリ");

  const randomBtn = document.createElement("button");
  randomBtn.className = "aph-random-btn";
  randomBtn.textContent = "🎲";
  randomBtn.title = "ランダムタグを追加";
  randomBtn.setAttribute("aria-label", "ランダムタグを追加");

  subcatRowEl.appendChild(subcategorySelect);
  subcatRowEl.appendChild(randomBtn);

  // --- Search ---
  const searchInput = document.createElement("input");
  searchInput.type = "search";
  searchInput.className = "aph-search";
  searchInput.placeholder = "Search tags…";
  searchInput.setAttribute("aria-label", "Search tags");

  // --- Tag grid ---
  const tagGrid = document.createElement("div");
  tagGrid.className = "aph-tag-grid";
  tagGrid.setAttribute("role", "tabpanel");

  // -------------------------------------------------------------------------
  // Assemble panel in specified DOM order
  // -------------------------------------------------------------------------
  panelEl.appendChild(headerEl);
  panelEl.appendChild(presetSelect);
  panelEl.appendChild(controlsEl);
  panelEl.appendChild(insertWarnEl);
  panelEl.appendChild(tabStrip);
  panelEl.appendChild(subcatRowEl);
  panelEl.appendChild(searchInput);
  panelEl.appendChild(tagGrid);

  // -------------------------------------------------------------------------
  // Register DOM widget
  // -------------------------------------------------------------------------
  const MIN_PANEL_HEIGHT = 360;
  const _panelWidget = node.addDOMWidget(
    "anima_tag_palette_panel",
    "div",
    panelEl,
    { serialize: false }
  );
  if (_panelWidget) {
    _panelWidget.computeSize = function (width) {
      const h = Math.max(panelEl.scrollHeight || 480, MIN_PANEL_HEIGHT);
      return [width, h + 16];
    };
  }

  // --- Initial node size ---
  node.size = [
    Math.max(node.size[0], 680),
    Math.max(node.size[1], 480),
  ];

  requestAnimationFrame(() => {
    const h = Math.max(panelEl.scrollHeight || 480, MIN_PANEL_HEIGHT);
    const targetH = h + 60;
    if (node.size[1] < targetH) {
      node.size[1] = targetH;
      node.graph && node.graph.setDirtyCanvas(true, true);
    }
  });

  // --- Auto-resize ---
  let _resizing = false;
  const _resizeObs = new ResizeObserver(() => {
    if (!node.graph || _resizing) return;
    _resizing = true;
    requestAnimationFrame(() => {
      const h = Math.max(panelEl.scrollHeight || 480, MIN_PANEL_HEIGHT);
      const targetH = h + 60;
      if (node.size[1] < targetH - 8) {
        node.size[1] = targetH;
        node.graph.setDirtyCanvas(true, true);
      }
      _resizing = false;
    });
  });
  _resizeObs.observe(panelEl);

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let currentCategoryId = null;
  const timers = [];

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  /** Repopulate the Composer dropdown, auto-select if only one exists. */
  function refreshComposerList() {
    while (composerSelect.options.length > 1) {
      composerSelect.remove(1);
    }
    const composers = getComposerNodes(node.graph);
    for (const cn of composers) {
      const opt = document.createElement("option");
      opt.value = String(cn.id);
      opt.textContent =
        cn.title || cn.properties?.title || ("Composer #" + cn.id);
      composerSelect.appendChild(opt);
    }
    if (composers.length === 1) {
      composerSelect.value = String(composers[0].id);
    }
  }

  /**
   * Refresh the subcategory dropdown for the current category.
   * Preserves saved subcategory selection when available.
   *
   * Preconditions:
   *   - currentCategoryId is set to a non-special category id.
   * Postconditions:
   *   - subcategorySelect contains "-- All --" + subcategories for the current category.
   *   - subcategorySelect.value is set to saved subcategory or "" (All).
   */
  function refreshSubcategoryDropdown() {
    while (subcategorySelect.firstChild) {
      subcategorySelect.removeChild(subcategorySelect.firstChild);
    }
    const allOpt = document.createElement("option");
    allOpt.value = "";
    allOpt.textContent = "-- All --";
    subcategorySelect.appendChild(allOpt);

    const subcats = PaletteStore.getSubcategories(currentCategoryId);
    for (const sc of subcats) {
      const opt = document.createElement("option");
      opt.value = sc;
      opt.textContent = sc;
      subcategorySelect.appendChild(opt);
    }

    // Restore saved subcategory if it exists for this category
    const saved = getSelectedSubcategory(node);
    if (saved && subcats.includes(saved)) {
      subcategorySelect.value = saved;
    } else {
      subcategorySelect.value = "";
    }
  }

  // -------------------------------------------------------------------------
  // applyToTarget — core operation dispatcher
  // -------------------------------------------------------------------------

  /**
   * Applies an operation (toggle/remove/weight) to the buffer and the target Composer field.
   *
   * Preconditions:
   *   - op is "toggle" | "remove" | "weight".
   *   - If op === "weight", delta must be a number.
   * Postconditions:
   *   - tags_buffer is updated (toggle/remove only).
   *   - If a Composer + field are selected and not linked, the Composer widget is updated.
   *
   * @param {string} tagStr
   * @param {"toggle"|"remove"|"weight"} op
   * @param {number} [delta]
   */
  function applyToTarget(tagStr, op, delta) {
    // Update buffer (weight changes are not reflected in buffer)
    if (op === "toggle") toggleTagInBuffer(node, tagStr);
    if (op === "remove") removeTagFromBuffer(node, tagStr);

    const composerNodeId = parseInt(composerSelect.value, 10);
    const targetField = fieldSelect.value;
    if (!composerNodeId || !targetField || !node.graph) return;

    const composers = getComposerNodes(node.graph);
    const targetComposer = composers.find((c) => c.id === composerNodeId);
    if (!targetComposer) return;

    const inputSlot = targetComposer.inputs
      ? targetComposer.inputs.find((ii) => ii.name === targetField)
      : null;
    const isLinked = !!(inputSlot && inputSlot.link != null);
    const w = targetComposer.widgets
      ? targetComposer.widgets.find((ww) => ww.name === targetField)
      : null;

    if (isLinked) {
      insertWarnEl.textContent =
        `「${targetField}」は接続済みなのでwidget書き込みをスキップしました。`;
      insertWarnEl.style.display = "";
      return;
    }
    if (!w) return;

    if (op === "toggle") toggleTagInField(targetComposer, targetField, tagStr);
    else if (op === "remove") removeTagFromField(targetComposer, targetField, tagStr);
    else if (op === "weight") adjustTagWeight(targetComposer, targetField, tagStr, delta);
  }

  // -------------------------------------------------------------------------
  // Tag button event handlers
  // -------------------------------------------------------------------------

  /**
   * Handles click on a tag button or its child action elements.
   *
   * Preconditions:
   *   - tagStr is the raw tag string (data-tag attribute).
   * Postconditions:
   *   - If action === "fav": favorite is toggled; span text/title updated.
   *   - If action === "w-minus"/"w-plus": weight adjusted by ±0.1.
   *   - Otherwise: tag is toggled in buffer/Composer + added to history.
   *
   * @param {Event} e
   * @param {string} tagStr
   */
  function handleTagBtnClick(e, tagStr) {
    const action = e.target?.dataset?.action;
    if (action === "fav") {
      const added = toggleFavorite(node, tagStr);
      const favSpan = e.target;
      favSpan.textContent = added ? "★" : "☆";
      favSpan.title = added ? "お気に入り解除" : "お気に入り追加";
      favSpan.dataset.active = added ? "true" : "false";
      return;
    }
    if (action === "w-minus" || action === "w-plus") {
      const delta = action === "w-plus" ? 0.1 : -0.1;
      applyToTarget(tagStr, "weight", delta);
      return;
    }
    // Default: toggle
    applyToTarget(tagStr, "toggle");
    addToHistory(node, tagStr);
  }

  /**
   * Handles right-click on a tag button (removes tag from buffer/Composer).
   *
   * @param {Event} e
   * @param {string} tagStr
   */
  function handleTagBtnRightClick(e, tagStr) {
    e.preventDefault();
    applyToTarget(tagStr, "remove");
  }

  // -------------------------------------------------------------------------
  // enhanceTagButtons — post-process tag buttons after renderTagButtons
  // -------------------------------------------------------------------------

  /**
   * Wraps each .aph-tag-btn's text in a label span and adds ★ / − / + action spans.
   * Replaces the original click listener (set by PaletteStore.renderTagButtons)
   * with the unified handleTagBtnClick.
   *
   * Preconditions:
   *   - tagGrid contains .aph-tag-btn elements with data-tag attributes.
   * Postconditions:
   *   - Each button has .aph-tag-label, .aph-tag-fav, .aph-tag-w-minus, .aph-tag-w-plus.
   *   - Buttons respond to click/contextmenu/keydown.
   */
  function enhanceTagButtons() {
    const btns = tagGrid.querySelectorAll(".aph-tag-btn");
    btns.forEach((btn) => {
      const tagStr = btn.dataset.tag;
      if (!tagStr) return;

      // Wrap original text in a label span (only once)
      if (!btn.querySelector(".aph-tag-label")) {
        const labelText = btn.textContent;
        while (btn.firstChild) btn.removeChild(btn.firstChild);
        const labelSpan = document.createElement("span");
        labelSpan.className = "aph-tag-label";
        labelSpan.textContent = labelText;
        btn.appendChild(labelSpan);
      }

      // Add favorite indicator span
      const favSpan = document.createElement("span");
      favSpan.className = "aph-tag-fav";
      const faved = isFavorite(node, tagStr);
      favSpan.textContent = faved ? "★" : "☆";
      favSpan.title = faved ? "お気に入り解除" : "お気に入り追加";
      favSpan.dataset.action = "fav";
      favSpan.dataset.active = faved ? "true" : "false";
      btn.appendChild(favSpan);

      // Add weight − / + buttons
      const wMinus = document.createElement("span");
      wMinus.className = "aph-tag-w-minus";
      wMinus.textContent = "−";
      wMinus.title = "重みを下げる (-0.1)";
      wMinus.dataset.action = "w-minus";
      btn.appendChild(wMinus);

      const wPlus = document.createElement("span");
      wPlus.className = "aph-tag-w-plus";
      wPlus.textContent = "+";
      wPlus.title = "重みを上げる (+0.1)";
      wPlus.dataset.action = "w-plus";
      btn.appendChild(wPlus);

      // Replace the button node to strip the original click listener
      const newBtn = btn.cloneNode(true);
      btn.replaceWith(newBtn);

      // Re-attach event handlers
      newBtn.addEventListener("click", (e) => handleTagBtnClick(e, tagStr));
      newBtn.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        handleTagBtnRightClick(e, tagStr);
      });
      newBtn.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handleTagBtnClick({ target: newBtn, currentTarget: newBtn }, tagStr);
        }
      });
    });
  }

  // -------------------------------------------------------------------------
  // renderSpecialGrid — Favorites / History
  // -------------------------------------------------------------------------

  /**
   * Renders a special grid (Favorites or History) with tag buttons.
   *
   * Preconditions:
   *   - container is an empty (or will be cleared) DOM element.
   *   - tags is an array of strings.
   * Postconditions:
   *   - container shows tag buttons or an empty-state message.
   *
   * @param {HTMLElement} container
   * @param {string[]} tags
   */
  function renderSpecialGrid(container, tags) {
    while (container.firstChild) container.removeChild(container.firstChild);
    if (tags.length === 0) {
      const msg = document.createElement("p");
      msg.className = "aph-no-tags";
      msg.textContent = currentCategoryId === "__favorites__"
        ? "お気に入りはまだありません。タグの ★ ボタンで追加できます。"
        : "履歴はまだありません。";
      container.appendChild(msg);
      return;
    }
    const frag = document.createDocumentFragment();
    for (const t of tags) {
      const btn = document.createElement("button");
      btn.className = "aph-tag-btn";
      btn.dataset.tag = t;
      btn.textContent = t;
      btn.type = "button";
      frag.appendChild(btn);
    }
    container.appendChild(frag);
  }

  // -------------------------------------------------------------------------
  // renderGrid
  // -------------------------------------------------------------------------

  /**
   * Renders the tag grid for the current category, search query, and subcategory.
   *
   * Preconditions:
   *   - currentCategoryId is set.
   * Postconditions:
   *   - tagGrid is populated with tag buttons (enhanced with action spans).
   */
  function renderGrid() {
    // Special tabs
    if (currentCategoryId === "__favorites__") {
      renderSpecialGrid(tagGrid, getFavorites(node));
      enhanceTagButtons();
      return;
    }
    if (currentCategoryId === "__history__") {
      renderSpecialGrid(tagGrid, getHistory(node));
      enhanceTagButtons();
      return;
    }

    if (!_paletteCache) {
      while (tagGrid.firstChild) tagGrid.removeChild(tagGrid.firstChild);
      const msg = document.createElement("p");
      msg.className = "aph-load-error";
      msg.textContent =
        "Palette failed to load. Check the console for details.";
      tagGrid.appendChild(msg);
      return;
    }

    const query = searchInput.value || "";
    const subcatId = subcategorySelect.value || null;
    // onAdd is replaced by enhanceTagButtons; no-op here
    PaletteStore.renderTagButtons(
      tagGrid,
      currentCategoryId,
      query,
      () => {},
      subcatId
    );

    enhanceTagButtons();
  }

  // -------------------------------------------------------------------------
  // selectCategory
  // -------------------------------------------------------------------------

  /**
   * Selects a category tab, updates subcategory dropdown visibility, and re-renders the grid.
   *
   * Preconditions:
   *   - catId is either a special tab id or a valid palette category id.
   * Postconditions:
   *   - currentCategoryId === catId.
   *   - subcategorySelect is hidden for special tabs.
   *   - randomBtn is disabled for special tabs.
   *   - tagGrid is re-rendered.
   *
   * @param {string} catId
   */
  function selectCategory(catId) {
    currentCategoryId = catId;
    setSelectedTab(node, catId);

    const isSpecial = catId === "__favorites__" || catId === "__history__";
    subcatRowEl.style.display = isSpecial ? "none" : "";
    randomBtn.disabled = isSpecial;

    if (!isSpecial) {
      const defaultTarget = CATEGORY_DEFAULT_TARGET[catId] ?? "general";
      if (TARGET_FIELD_OPTIONS.includes(defaultTarget)) {
        fieldSelect.value = defaultTarget;
      }
      // Refresh subcategory dropdown (restores saved selection or resets to "All")
      refreshSubcategoryDropdown();
    }

    const activeBtn = tabStrip.querySelector(".aph-tab-btn.aph-tab-active");
    if (activeBtn) {
      if (!activeBtn.id) {
        activeBtn.id =
          "aph-tp-tab-" + catId.replace(/[^a-z0-9_-]/gi, "_");
      }
      tagGrid.setAttribute("aria-labelledby", activeBtn.id);
    }

    renderGrid();
  }

  // -------------------------------------------------------------------------
  // Random button handler
  // -------------------------------------------------------------------------
  randomBtn.addEventListener("click", () => {
    if (!currentCategoryId || currentCategoryId.startsWith("__")) return;
    const subcatId = subcategorySelect.value || undefined;
    const tagObj = PaletteStore.getRandomTag(currentCategoryId, subcatId, true);
    if (!tagObj || !tagObj.tag) return;
    const tagStr = tagObj.tag;
    // Add to buffer and history
    toggleTagInBuffer(node, tagStr);
    addToHistory(node, tagStr);
    // Mirror to Composer field
    applyToTarget(tagStr, "toggle");
  });

  // -------------------------------------------------------------------------
  // Insert button handler
  // -------------------------------------------------------------------------
  insertBtn.addEventListener("click", () => {
    const composerNodeId = parseInt(composerSelect.value, 10);
    const targetField = fieldSelect.value;

    if (!composerNodeId) {
      insertWarnEl.textContent = "対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      return;
    }
    if (!targetField) {
      insertWarnEl.textContent = "挿入先フィールドを選択してください。";
      insertWarnEl.style.display = "";
      return;
    }

    const composers = getComposerNodes(node.graph);
    const targetComposer = composers.find((c) => c.id === composerNodeId);
    if (!targetComposer) {
      insertWarnEl.textContent =
        "指定した Composer がグラフ上に見つかりません。";
      insertWarnEl.style.display = "";
      return;
    }

    const inputSlot = targetComposer.inputs
      ? targetComposer.inputs.find((ii) => ii.name === targetField)
      : null;
    const isLinked = !!(inputSlot && inputSlot.link != null);
    const w = targetComposer.widgets
      ? targetComposer.widgets.find((ww) => ww.name === targetField)
      : null;
    if (isLinked) {
      insertWarnEl.textContent =
        `「${targetField}」は接続済みです。tags_bufferの値が出力経由で反映されるため、widgetへの書き込みはスキップしました。`;
      insertWarnEl.style.display = "";
      return;
    }
    if (!w) {
      insertWarnEl.textContent =
        "選択フィールドは接続済みのため widget が存在しません（接続経路を使用してください）。";
      insertWarnEl.style.display = "";
      return;
    }

    const bufferWidget = node.widgets
      ? node.widgets.find((ww) => ww.name === "tags_buffer")
      : null;
    const bufferVal = bufferWidget ? bufferWidget.value || "" : "";

    if (!bufferVal.trim()) {
      insertWarnEl.textContent = "tags_buffer が空です。";
      insertWarnEl.style.display = "";
      return;
    }

    const tokens = bufferVal
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    for (const tok of tokens) {
      addTagToField(targetComposer, targetField, tok);
    }

    insertWarnEl.style.display = "none";
  });

  // --- Preset change handler ---
  presetSelect.addEventListener("change", () => {
    const selectedId = presetSelect.value;
    if (!selectedId) return;
    const preset = CharacterPresetStore ? CharacterPresetStore.getById(selectedId) : null;
    if (!preset) return;
    const composerNodeId = parseInt(composerSelect.value, 10);
    if (!composerNodeId || !node.graph) {
      insertWarnEl.textContent = "対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      presetSelect.value = "";
      return;
    }
    const composers = getComposerNodes(node.graph);
    const targetComposer = composers.find((c) => c.id === composerNodeId);
    if (!targetComposer) {
      insertWarnEl.textContent = "指定した Composer がグラフ上に見つかりません。";
      insertWarnEl.style.display = "";
      presetSelect.value = "";
      return;
    }
    applyPreset(targetComposer, preset);
    insertWarnEl.style.display = "none";
    presetSelect.value = "";
    presetSelect.focus();
  });

  // Hide warning on any interaction
  composerSelect.addEventListener("change", () => {
    insertWarnEl.style.display = "none";
  });
  fieldSelect.addEventListener("change", () => {
    insertWarnEl.style.display = "none";
  });

  // Subcategory change handler
  subcategorySelect.addEventListener("change", () => {
    const val = subcategorySelect.value || null;
    setSelectedSubcategory(node, val);
    renderGrid();
  });

  // -------------------------------------------------------------------------
  // initPanel
  // -------------------------------------------------------------------------

  /**
   * Initializes the palette panel: tab strip, category selection, and initial grid render.
   *
   * Preconditions:
   *   - _paletteCache is set (or null for error state).
   * Postconditions:
   *   - Tab strip rendered with SPECIAL_TABS + filtered palette categories.
   *   - Initial category and search query restored from persisted state.
   */
  function initPanel() {
    refreshComposerList();

    if (!_paletteCache) {
      renderGrid();
      return;
    }

    PaletteStore.init(_paletteCache);

    // Build category list: special tabs first, then non-Composer palette categories
    const allCategories = PaletteStore.getCategories();
    const palCategories = allCategories.filter(
      (c) => !COMPOSER_ONLY_TABS.includes(c.id)
    );
    const allTabs = [...SPECIAL_TABS, ...palCategories];

    // Restore or default to first non-special category
    const savedTab = getSelectedTab(node);
    const firstPalCat = palCategories.length > 0 ? palCategories[0].id : null;
    // Check if saved tab is valid (special or palette)
    const savedIsValid = savedTab && allTabs.some((c) => c.id === savedTab);
    currentCategoryId = savedIsValid ? savedTab : (firstPalCat || SPECIAL_TABS[0].id);

    // Restore search query
    searchInput.value = getSearchQuery(node) || "";

    // Render tab strip with all tabs
    PaletteStore.renderTabStrip(
      tabStrip,
      currentCategoryId,
      (catId) => {
        selectCategory(catId);
      },
      allTabs
    );

    // Set initial field dropdown value (only for non-special tabs)
    const isSpecial = currentCategoryId === "__favorites__" || currentCategoryId === "__history__";
    if (!isSpecial && currentCategoryId) {
      const defaultTarget =
        CATEGORY_DEFAULT_TARGET[currentCategoryId] ?? "general";
      if (TARGET_FIELD_OPTIONS.includes(defaultTarget)) {
        fieldSelect.value = defaultTarget;
      }
    }

    // Set up subcategory row visibility
    subcatRowEl.style.display = isSpecial ? "none" : "";
    randomBtn.disabled = isSpecial;
    if (!isSpecial) {
      refreshSubcategoryDropdown();
    }

    // aria-labelledby
    const activeBtn = tabStrip.querySelector(".aph-tab-btn.aph-tab-active");
    if (activeBtn && currentCategoryId) {
      if (!activeBtn.id) {
        activeBtn.id =
          "aph-tp-tab-" + currentCategoryId.replace(/[^a-z0-9_-]/gi, "_");
      }
      tagGrid.setAttribute("aria-labelledby", activeBtn.id);
    }

    renderGrid();
  }

  initPanel();

  // -------------------------------------------------------------------------
  // Search (debounced 400 ms)
  // -------------------------------------------------------------------------
  const debouncedSearch = debounce(() => {
    setSearchQuery(node, searchInput.value);
    renderGrid();
  }, 400);

  searchInput.addEventListener("input", debouncedSearch);

  const onSearchKeydown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      searchInput.value = "";
      setSearchQuery(node, "");
      renderGrid();
    }
  };
  searchInput.addEventListener("keydown", onSearchKeydown);

  // -------------------------------------------------------------------------
  // Periodic Composer list refresh (1 s)
  // -------------------------------------------------------------------------
  const composerRefreshTimer = setInterval(() => {
    refreshComposerList();
  }, 1000);
  timers.push(composerRefreshTimer);

  // -------------------------------------------------------------------------
  // Cleanup on node removal
  // -------------------------------------------------------------------------
  const origOnRemoved =
    typeof node.onRemoved === "function" ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    _resizeObs.disconnect();
    for (const t of timers) clearInterval(t);
    searchInput.removeEventListener("input", debouncedSearch);
    searchInput.removeEventListener("keydown", onSearchKeydown);
    if (origOnRemoved) origOnRemoved();
  };

  node._aphTpInitPanel = initPanel;
}
