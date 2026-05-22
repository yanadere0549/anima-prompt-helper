/**
 * tag_palette_panel.js — DOM panel injection for AnimaTagPalette nodes (v0.5.0)
 *
 * Builds the tag palette panel for AnimaTagPalette.
 * Shows only the 26 non-Composer tabs (hair_color and below).
 * Provides:
 *   - 対象 Composer dropdown (同一グラフ内 AnimaPromptComposer を列挙)
 *   - 挿入先フィールドは選択中カテゴリから自動決定 (CATEGORY_DEFAULT_TARGET)
 *   - 「Composerへ挿入」ボタン
 *   - タグクリック時に tags_buffer widget を更新
 *   - カテゴリタブを左サイドバーの縦タブとして表示
 *   - Subcategory dropdown (右カラム上部、サーチ上)
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
import { SituationPresetStore, applySituationPreset } from "./situation_presets.js";
import {
  openPresetEditor,
  quickSaveFromComposer,
  openSituationPresetEditor,
  quickSaveSituationFromComposer,
} from "./preset_editor.js";
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
  { id: "__favorites__", label: "★ Favorites\nお気に入り" },
  { id: "__history__",   label: "🕒 History\n履歴"       },
];

// ---------------------------------------------------------------------------
// Japanese translations for palette category labels (vertical tab UI).
// Backend returns English labels (e.g. "Hair Color"); we append a Japanese
// translation on a second line so users can recognize categories at a glance.
// ---------------------------------------------------------------------------
const TAG_CATEGORY_LABEL_JA = {
  quality:          "品質",
  year:             "年代",
  rating:           "レーティング",
  count:            "人数",
  hair_color:       "髪色",
  hair_length:      "髪の長さ",
  hair_style:       "髪型",
  eye_color:        "瞳の色",
  expression:       "表情",
  pose:             "ポーズ",
  composition:      "構図 / アングル",
  clothing:         "服装",
  location:         "場所 / 背景",
  lighting:         "照明",
  style:            "画風 / 画材",
  effects:          "エフェクト",
  artist:           "絵師",
  natural_language: "自然言語テンプレ",
  accessory:        "装飾品",
  weapon:           "武器 / 装備",
  food:             "食べ物 / 飲み物",
  animal:           "動物 / 生き物",
  situation:        "状況 / 行動",
  camera:           "カメラ / ショット",
  color_tone:       "色調 / パレット",
  weather_atmos:    "天候 / 雰囲気",
  season:           "季節",
  architecture:     "建築 / 建物",
  magic_fantasy:    "魔法 / ファンタジー",
  accessory_floral: "花 / 植物",
};

/**
 * Returns the tab label for a palette category, appending a Japanese
 * translation on a new line when one is registered.
 *
 * Example: { id: "hair_color", label: "Hair Color" } → "Hair Color\n髪色"
 *
 * @param {{id: string, label?: string}} cat
 * @returns {string}
 */
function _formatCategoryTabLabel(cat) {
  const base = cat.label || cat.id;
  const ja = TAG_CATEGORY_LABEL_JA[cat.id];
  return ja ? base + "\n" + ja : base;
}

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

const _CATEGORY_LABELS = {
  daily: "🏠 Daily",
  nature: "🌿 Nature",
  weather: "🌧 Weather",
  season: "🍂 Season",
  urban: "🌆 Urban",
  fantasy: "🐉 Fantasy",
  scifi: "🚀 Sci-Fi",
  studio: "🎬 Studio",
  battle: "⚔ Battle",
};

function _categoryLabel(cat) {
  return _CATEGORY_LABELS[cat] || cat || "Other";
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

  // --- Character preset row: dropdown + action buttons ---
  const presetRowEl = document.createElement("div");
  presetRowEl.className = "aph-preset-row";

  const presetSelect = document.createElement("select");
  presetSelect.className = "aph-preset-select";
  presetSelect.setAttribute("aria-label", "Character preset");

  /**
   * Rebuild the preset dropdown from the current CharacterPresetStore state.
   * Splits user (★) and builtin presets into two <optgroup> sections.
   */
  function rebuildPresetOptions() {
    while (presetSelect.firstChild) presetSelect.removeChild(presetSelect.firstChild);
    const defaultOpt = document.createElement("option");
    defaultOpt.value = "";
    defaultOpt.textContent = "-- Character preset --";
    presetSelect.appendChild(defaultOpt);

    const presets = CharacterPresetStore ? CharacterPresetStore.getAll() : [];
    if (presets.length === 0) {
      presetSelect.disabled = true;
      const unavailableOpt = document.createElement("option");
      unavailableOpt.value = "";
      unavailableOpt.textContent = "presets unavailable";
      presetSelect.appendChild(unavailableOpt);
      return;
    }
    presetSelect.disabled = false;
    const userPresets = presets.filter((p) => p.user);
    const builtinPresets = presets.filter((p) => !p.user);
    if (userPresets.length > 0) {
      const userGroup = document.createElement("optgroup");
      userGroup.label = "★ My Presets";
      for (const p of userPresets) {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = "★ " + (p.label || p.id);
        userGroup.appendChild(opt);
      }
      presetSelect.appendChild(userGroup);
    }
    if (builtinPresets.length > 0) {
      const biGroup = document.createElement("optgroup");
      biGroup.label = "Builtin";
      for (const p of builtinPresets) {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.label || p.id;
        biGroup.appendChild(opt);
      }
      presetSelect.appendChild(biGroup);
    }
  }

  rebuildPresetOptions();

  // Action buttons
  const newPresetBtn = document.createElement("button");
  newPresetBtn.type = "button";
  newPresetBtn.className = "aph-preset-action-btn";
  newPresetBtn.title = "新規プリセット作成";
  newPresetBtn.setAttribute("aria-label", "新規プリセット作成");
  newPresetBtn.textContent = "+";

  const saveCurrentBtn = document.createElement("button");
  saveCurrentBtn.type = "button";
  saveCurrentBtn.className = "aph-preset-action-btn";
  saveCurrentBtn.title = "対象Composerの現在の値をプリセットとして保存";
  saveCurrentBtn.setAttribute("aria-label", "現在の値を保存");
  saveCurrentBtn.textContent = "📷";

  const editPresetBtn = document.createElement("button");
  editPresetBtn.type = "button";
  editPresetBtn.className = "aph-preset-action-btn";
  editPresetBtn.title = "選択中プリセットを編集 (★ユーザープリセットのみ)";
  editPresetBtn.setAttribute("aria-label", "プリセット編集");
  editPresetBtn.textContent = "✎";
  editPresetBtn.disabled = true;

  presetRowEl.appendChild(presetSelect);
  presetRowEl.appendChild(newPresetBtn);
  presetRowEl.appendChild(saveCurrentBtn);
  presetRowEl.appendChild(editPresetBtn);

  // --- Situation preset row ---
  const situationRowEl = document.createElement("div");
  situationRowEl.className = "aph-preset-row";

  const situationSelect = document.createElement("select");
  situationSelect.className = "aph-preset-select aph-situation-select";
  situationSelect.setAttribute("aria-label", "Situation preset");

  function rebuildSituationOptions() {
    while (situationSelect.firstChild) {
      situationSelect.removeChild(situationSelect.firstChild);
    }
    const defaultOpt = document.createElement("option");
    defaultOpt.value = "";
    defaultOpt.textContent = "-- Situation preset --";
    situationSelect.appendChild(defaultOpt);

    const cats = SituationPresetStore ? SituationPresetStore.getCategories() : [];
    if (cats.length === 0) {
      situationSelect.disabled = true;
      const unavailableOpt = document.createElement("option");
      unavailableOpt.value = "";
      unavailableOpt.textContent = "situation presets unavailable";
      situationSelect.appendChild(unavailableOpt);
      return;
    }
    situationSelect.disabled = false;
    for (const cat of cats) {
      const group = document.createElement("optgroup");
      group.label = _categoryLabel(cat);
      for (const p of SituationPresetStore.getByCategory(cat)) {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = (p.user ? "★ " : "") + (p.label || p.id);
        group.appendChild(opt);
      }
      situationSelect.appendChild(group);
    }
  }

  rebuildSituationOptions();

  // Situation action buttons (mirror character preset row)
  const newSituationBtn = document.createElement("button");
  newSituationBtn.type = "button";
  newSituationBtn.className = "aph-preset-action-btn";
  newSituationBtn.title = "新規シチュエーション作成";
  newSituationBtn.setAttribute("aria-label", "新規シチュエーション作成");
  newSituationBtn.textContent = "+";

  const saveCurrentSituationBtn = document.createElement("button");
  saveCurrentSituationBtn.type = "button";
  saveCurrentSituationBtn.className = "aph-preset-action-btn";
  saveCurrentSituationBtn.title =
    "対象Composerの現在の値をシチュエーションプリセットとして保存";
  saveCurrentSituationBtn.setAttribute("aria-label", "現在の値をシチュエーション保存");
  saveCurrentSituationBtn.textContent = "📷";

  const editSituationBtn = document.createElement("button");
  editSituationBtn.type = "button";
  editSituationBtn.className = "aph-preset-action-btn";
  editSituationBtn.title = "選択中シチュエーションを編集 (★ユーザープリセットのみ)";
  editSituationBtn.setAttribute("aria-label", "シチュエーション編集");
  editSituationBtn.textContent = "✎";
  editSituationBtn.disabled = true;

  situationRowEl.appendChild(situationSelect);
  situationRowEl.appendChild(newSituationBtn);
  situationRowEl.appendChild(saveCurrentSituationBtn);
  situationRowEl.appendChild(editSituationBtn);

  // --- Controls row: Composer selector + Insert button ---
  // 挿入先フィールドは選択中カテゴリから CATEGORY_DEFAULT_TARGET で自動決定する
  // (UI 上のドロップダウンは廃止)
  const controlsEl = document.createElement("div");
  controlsEl.className = "aph-tag-palette-controls";

  const composerSelect = document.createElement("select");
  composerSelect.className = "aph-palette-composer-select";
  composerSelect.setAttribute("aria-label", "対象 AnimaPromptComposer");

  const composerDefaultOpt = document.createElement("option");
  composerDefaultOpt.value = "";
  composerDefaultOpt.textContent = "-- 対象 Composer --";
  composerSelect.appendChild(composerDefaultOpt);

  let currentTargetField = "general";

  const insertBtn = document.createElement("button");
  insertBtn.className = "aph-palette-insert-btn";
  insertBtn.textContent = "Composerへ挿入";
  insertBtn.setAttribute("aria-label", "選択中タグをComposerへ挿入");

  controlsEl.appendChild(composerSelect);
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
  // 2-column body: left = vertical tab strip, right = subcat + search + grid
  const bodyEl = document.createElement("div");
  bodyEl.className = "aph-tag-palette-body";

  // Mark the tab strip as vertical sidebar mode
  tabStrip.classList.add("aph-tab-strip--vertical");

  const rightColEl = document.createElement("div");
  rightColEl.className = "aph-tag-palette-right-col";
  rightColEl.appendChild(subcatRowEl);
  rightColEl.appendChild(searchInput);
  rightColEl.appendChild(tagGrid);

  bodyEl.appendChild(tabStrip);
  bodyEl.appendChild(rightColEl);

  panelEl.appendChild(headerEl);
  panelEl.appendChild(presetRowEl);
  panelEl.appendChild(situationRowEl);
  panelEl.appendChild(controlsEl);
  panelEl.appendChild(insertWarnEl);
  panelEl.appendChild(bodyEl);

  // -------------------------------------------------------------------------
  // Register DOM widget
  // -------------------------------------------------------------------------
  const MIN_PANEL_HEIGHT = 380;
  const MIN_NODE_WIDTH = 680;
  const MIN_NODE_HEIGHT = 480;
  // Minimum height the right column needs without flex-growth:
  //   subcategory row (30) + search (30) + tag grid min-height (140) = 200.
  const BODY_MIN_HEIGHT = 200;

  /**
   * Compute the panel's intrinsic content height — the height it would need
   * *if the body did not flex-grow*. We sum the fixed-height header / preset
   * / controls rows and add a fixed body minimum.
   *
   * panelEl.scrollHeight is intentionally NOT used here: with
   * `.aph-tag-palette-panel { height: 100% }` and `.aph-tag-palette-body {
   * flex: 1 1 auto }` the panel tracks the widget container's height, so
   * scrollHeight feeds back into computeSize and the widget grows on every
   * tick. This measurement is a function of the static rows only, so it
   * stays stable regardless of how tall the container becomes.
   *
   * @returns {number} required panel height in CSS pixels (excludes the
   *   widget container's own padding, which is added by the caller)
   */
  function intrinsicPanelHeight() {
    const fixedRows = [headerEl, presetRowEl, situationRowEl, controlsEl];
    let nonBody = 0;
    for (const row of fixedRows) {
      // Fall back to 30 px before the row has laid out (initial measure).
      nonBody += row.offsetHeight || 30;
    }
    if (insertWarnEl.style.display !== "none") {
      nonBody += insertWarnEl.offsetHeight || 30;
    }
    const gaps = 6 * 5;     // five 6 px gaps between flex-column children
    const padding = 16;     // 8 px top + 8 px bottom panel padding
    return Math.max(nonBody + BODY_MIN_HEIGHT + gaps + padding, MIN_PANEL_HEIGHT);
  }

  // Vertical space we ask computeSize to leave around the DOM widget so
  // LiteGraph does NOT keep auto-growing the node. Static testing showed
  // 30 was the threshold (chrome = 30 + 16 = 46), but live drag-resize
  // triggers feedback at that value — once the node is stretched it stays
  // stretched and slowly inflates further. 60 gives chrome ~76 (≈ title
  // 30 + 46 px under the panel), which removes the feedback completely at
  // the cost of a slightly thicker bottom margin.
  const NODE_CHROME_HEIGHT = 60;

  const _panelWidget = node.addDOMWidget(
    "anima_tag_palette_panel",
    "div",
    panelEl,
    { serialize: false }
  );
  if (_panelWidget) {
    _panelWidget.computeSize = function (width) {
      // Floor at the intrinsic content height so the body's right column min
      // is always satisfied. Otherwise, track the node's height — when the
      // user (or a saved workflow) makes the node taller than the minimum,
      // grow the widget so the panel fills the node instead of leaving a
      // dead band of widget background beneath it.
      const intrinsic = intrinsicPanelHeight();
      const nodeBased = (node.size && node.size[1]) - NODE_CHROME_HEIGHT;
      const h = Math.max(intrinsic, nodeBased || 0);
      return [width, h];
    };
    // Workaround for the new Vue node inspector: WidgetLegacy.vue mounts when
    // a node is clicked and runs `widgetInstance.width = container.clientWidth`
    // against the inspector's narrow column (~164 px). That mutation
    // propagates back to DomWidgets.vue (`posWidget.width ?? posNode.width`)
    // and shrinks the in-canvas panel. Make `width` writes a no-op so the
    // DOM widget always falls back to the node's width.
    Object.defineProperty(_panelWidget, "width", {
      get() { return undefined; },
      set(_v) { /* swallow inspector-driven writes */ },
      configurable: true,
    });
  }

  /**
   * Enforce the panel's minimum size on the node. Called on init, after
   * configure (workflow load), and during resize so a saved workflow with a
   * small node — or a user drag-shrinking the node — cannot squash the panel
   * below the width its controls need.
   */
  function enforceMinNodeSize() {
    let changed = false;
    if (node.size[0] < MIN_NODE_WIDTH) {
      node.size[0] = MIN_NODE_WIDTH;
      changed = true;
    }
    if (node.size[1] < MIN_NODE_HEIGHT) {
      node.size[1] = MIN_NODE_HEIGHT;
      changed = true;
    }
    if (changed && node.graph) {
      node.graph.setDirtyCanvas(true, true);
    }
  }

  // --- Initial node size ---
  enforceMinNodeSize();

  // Re-apply the minimum after onConfigure has restored a saved (possibly
  // smaller) size. attachPersistence() has already wrapped onConfigure, so we
  // wrap it once more here to run last.
  const _origOnConfigureForSize =
    typeof node.onConfigure === "function" ? node.onConfigure.bind(node) : null;
  node.onConfigure = function (data) {
    if (_origOnConfigureForSize) _origOnConfigureForSize(data);
    enforceMinNodeSize();
  };

  // Block user drags from shrinking the node below the panel's minimum.
  const _origOnResize =
    typeof node.onResize === "function" ? node.onResize.bind(node) : null;
  node.onResize = function (size) {
    if (size && size[0] < MIN_NODE_WIDTH) size[0] = MIN_NODE_WIDTH;
    if (size && size[1] < MIN_NODE_HEIGHT) size[1] = MIN_NODE_HEIGHT;
    if (_origOnResize) _origOnResize(size);
  };

  requestAnimationFrame(() => {
    enforceMinNodeSize();
    const targetH = intrinsicPanelHeight() + 60;
    if (node.size[1] < targetH) {
      node.size[1] = targetH;
      node.graph && node.graph.setDirtyCanvas(true, true);
    }
  });

  // --- Auto-resize ---
  // Observe panel size changes only so we can react when the (rare) extra
  // dynamic rows appear or disappear (e.g. insertWarnEl). We measure the
  // intrinsic content height (NOT panelEl.scrollHeight) to avoid the
  // self-feeding loop that height:100% on the panel would otherwise trigger.
  let _resizing = false;
  const _resizeObs = new ResizeObserver(() => {
    if (!node.graph || _resizing) return;
    _resizing = true;
    requestAnimationFrame(() => {
      const targetH = intrinsicPanelHeight() + 60;
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
    const targetField = currentTargetField;
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
      currentTargetField = TARGET_FIELD_OPTIONS.includes(defaultTarget)
        ? defaultTarget
        : "general";
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
    const targetField = currentTargetField;

    if (!composerNodeId) {
      insertWarnEl.textContent = "対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      return;
    }
    if (!targetField) {
      insertWarnEl.textContent = "挿入先フィールドを決定できませんでした。";
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

  /** Helper: find the currently selected target Composer node (or null). */
  function _resolveTargetComposer() {
    const composerNodeId = parseInt(composerSelect.value, 10);
    if (!composerNodeId || !node.graph) return null;
    const composers = getComposerNodes(node.graph);
    return composers.find((c) => c.id === composerNodeId) || null;
  }

  /** Update editPresetBtn enabled state based on the currently selected preset. */
  function _refreshEditButtonState() {
    const id = presetSelect.value;
    if (!id) {
      editPresetBtn.disabled = true;
      return;
    }
    const p = CharacterPresetStore ? CharacterPresetStore.getById(id) : null;
    editPresetBtn.disabled = !(p && p.user);
  }

  // --- Preset change handler (apply to target composer) ---
  presetSelect.addEventListener("change", () => {
    _refreshEditButtonState();
    const selectedId = presetSelect.value;
    if (!selectedId) return;
    const preset = CharacterPresetStore ? CharacterPresetStore.getById(selectedId) : null;
    if (!preset) return;
    const targetComposer = _resolveTargetComposer();
    if (!targetComposer) {
      insertWarnEl.textContent = "対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      // keep selection so user can click edit / re-apply after selecting composer
      return;
    }
    applyPreset(targetComposer, preset);
    insertWarnEl.style.display = "none";
  });

  // --- "+" new preset button ---
  newPresetBtn.addEventListener("click", () => {
    openPresetEditor({ mode: "create" });
  });

  // --- "📷" save current composer state as preset ---
  saveCurrentBtn.addEventListener("click", () => {
    const targetComposer = _resolveTargetComposer();
    if (!targetComposer) {
      insertWarnEl.textContent =
        "現在の値を保存するには、まず対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      return;
    }
    insertWarnEl.style.display = "none";
    quickSaveFromComposer(targetComposer);
  });

  // --- "✎" edit selected user preset ---
  editPresetBtn.addEventListener("click", () => {
    const id = presetSelect.value;
    if (!id) return;
    const preset = CharacterPresetStore ? CharacterPresetStore.getById(id) : null;
    if (!preset || !preset.user) return;
    openPresetEditor({ mode: "edit", preset });
  });

  /** Update editSituationBtn enabled state based on the selected situation. */
  function _refreshEditSituationButtonState() {
    const id = situationSelect.value;
    if (!id) {
      editSituationBtn.disabled = true;
      return;
    }
    const p = SituationPresetStore ? SituationPresetStore.getById(id) : null;
    editSituationBtn.disabled = !(p && p.user);
  }

  // --- Situation preset change handler ---
  situationSelect.addEventListener("change", () => {
    _refreshEditSituationButtonState();
    const selectedId = situationSelect.value;
    if (!selectedId) return;
    const preset = SituationPresetStore
      ? SituationPresetStore.getById(selectedId)
      : null;
    if (!preset) return;
    const targetComposer = _resolveTargetComposer();
    if (!targetComposer) {
      insertWarnEl.textContent = "対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      // keep selection so user can still hit edit; do not reset
      return;
    }
    applySituationPreset(targetComposer, preset);
    insertWarnEl.style.display = "none";
    // keep selection so the edit button stays enabled for the just-applied preset
  });

  // --- Situation "+" new preset ---
  newSituationBtn.addEventListener("click", () => {
    openSituationPresetEditor({ mode: "create" });
  });

  // --- Situation "📷" snapshot current composer ---
  saveCurrentSituationBtn.addEventListener("click", () => {
    const targetComposer = _resolveTargetComposer();
    if (!targetComposer) {
      insertWarnEl.textContent =
        "現在の値を保存するには、まず対象 Composer を選択してください。";
      insertWarnEl.style.display = "";
      return;
    }
    insertWarnEl.style.display = "none";
    quickSaveSituationFromComposer(targetComposer);
  });

  // --- Situation "✎" edit selected user preset ---
  editSituationBtn.addEventListener("click", () => {
    const id = situationSelect.value;
    if (!id) return;
    const preset = SituationPresetStore ? SituationPresetStore.getById(id) : null;
    if (!preset || !preset.user) return;
    openSituationPresetEditor({ mode: "edit", preset });
  });

  // --- Subscribe to situation preset store mutations ---
  const unsubscribeSituationStore =
    SituationPresetStore && typeof SituationPresetStore.subscribe === "function"
      ? SituationPresetStore.subscribe(() => {
          const prev = situationSelect.value;
          rebuildSituationOptions();
          if (prev) {
            const opt = Array.from(situationSelect.options)
              .find((o) => o.value === prev);
            if (opt) situationSelect.value = prev;
          }
          _refreshEditSituationButtonState();
        })
      : null;

  // --- Subscribe to character preset store mutations ---
  const unsubscribePresetStore =
    CharacterPresetStore && typeof CharacterPresetStore.subscribe === "function"
      ? CharacterPresetStore.subscribe(() => {
          const prev = presetSelect.value;
          rebuildPresetOptions();
          // Try to restore previous selection
          if (prev) {
            const opt = Array.from(presetSelect.options)
              .find((o) => o.value === prev);
            if (opt) presetSelect.value = prev;
          }
          _refreshEditButtonState();
        })
      : null;

  // Hide warning on any interaction
  composerSelect.addEventListener("change", () => {
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
    const palCategories = allCategories
      .filter((c) => !COMPOSER_ONLY_TABS.includes(c.id))
      .map((c) => ({ ...c, label: _formatCategoryTabLabel(c) }));
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

    // Set initial target field (only for non-special tabs)
    const isSpecial = currentCategoryId === "__favorites__" || currentCategoryId === "__history__";
    if (!isSpecial && currentCategoryId) {
      const defaultTarget =
        CATEGORY_DEFAULT_TARGET[currentCategoryId] ?? "general";
      currentTargetField = TARGET_FIELD_OPTIONS.includes(defaultTarget)
        ? defaultTarget
        : "general";
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
    if (typeof unsubscribePresetStore === "function") {
      unsubscribePresetStore();
    }
    if (typeof unsubscribeSituationStore === "function") {
      unsubscribeSituationStore();
    }
    if (origOnRemoved) origOnRemoved();
  };

  node._aphTpInitPanel = initPanel;
}
