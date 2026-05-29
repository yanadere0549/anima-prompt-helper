/**
 * prompt_importer_panel.js — DOM panel for AnimaPromptImporter nodes.
 *
 * Lets the user:
 *   - Drag-and-drop or browse for a generated image (PNG/JPEG).
 *   - See the extracted positive/negative prompts (auto-split, editable).
 *   - Inspect tokens grouped by composer field (quality / year / count /
 *     character / series / artist / general / NL / rating).
 *   - Toggle individual tokens on/off, or apply an entire bucket at once.
 *   - Push the selected tokens into a same-graph AnimaPromptComposer.
 */

import { addTagToField, getFieldWidget } from "./composer.js";
import { openSituationPresetEditor } from "./preset_editor.js";
import {
  COMPOSER_FIELDS,
  buildTagToFieldMap,
  buildCharacterTagMap,
  classifyPrompt,
  tokenizePrompt,
} from "./prompt_classifier.js";

// ---------------------------------------------------------------------------
// Module-scope caches set by setPromptImporterCaches()
// ---------------------------------------------------------------------------
let _paletteCache = null;
let _characterPresetsCache = null;

// Derived maps rebuilt whenever caches change.
let _paletteMap = new Map();
let _characterMap = new Map();

const _FIELD_LABELS = {
  quality: "Quality / 品質",
  year: "Year / 年代",
  rating: "Rating / レーティング",
  count: "Count / 人数",
  character: "Character / キャラ",
  series: "Series / 作品",
  artist: "Artist / 絵師",
  general: "General / 一般",
  natural_language: "Natural Language / 自然言語",
};

/**
 * Called by the main extension to pass shared caches in.
 * Also called whenever caches change so we can rebuild the lookup maps.
 *
 * @param {Object|null} paletteCache
 * @param {Object|null} characterPresetsCache
 */
export function setPromptImporterCaches(paletteCache, characterPresetsCache) {
  _paletteCache = paletteCache;
  _characterPresetsCache = characterPresetsCache;
  _paletteMap = buildTagToFieldMap(paletteCache);
  const presets =
    characterPresetsCache && Array.isArray(characterPresetsCache.presets)
      ? characterPresetsCache.presets
      : [];
  _characterMap = buildCharacterTagMap(presets);
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * Collect all AnimaPromptComposer nodes in the same graph.
 * @param {Object} graph - LiteGraph graph
 * @returns {Object[]}
 */
function _getComposerNodes(graph) {
  if (!graph || !Array.isArray(graph._nodes)) return [];
  return graph._nodes.filter((n) => n && n.type === "AnimaPromptComposer");
}

/**
 * Update a buffer widget on the node so the panel state persists across
 * save/load and downstream nodes can read the value.
 *
 * @param {Object} node
 * @param {string} widgetName
 * @param {string} value
 */
function _writeBufferWidget(node, widgetName, value) {
  if (!node || !Array.isArray(node.widgets)) return;
  const w = node.widgets.find((ww) => ww.name === widgetName);
  if (!w) return;
  w.value = value;
  const inputEl = w.element || w.inputEl;
  if (inputEl) {
    inputEl.value = value;
    inputEl.dispatchEvent(new Event("input", { bubbles: true }));
  }
  if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
    node.graph.setDirtyCanvas(true, true);
  }
}

// ---------------------------------------------------------------------------
// Main panel injector
// ---------------------------------------------------------------------------

/**
 * Inject the prompt importer panel onto an AnimaPromptImporter node.
 *
 * Preconditions:
 *   - ``node`` is a valid LiteGraph node of type AnimaPromptImporter.
 * Postconditions:
 *   - A DOM widget is mounted that handles file drops, extraction calls,
 *     and Composer field application.
 *
 * @param {Object} node
 */
export function injectPromptImporterPanel(node) {
  // -------------------------------------------------------------------------
  // Hide the two internal buffer widgets — they're driven by the panel UI.
  // -------------------------------------------------------------------------
  for (const wname of ["positive_buffer", "negative_buffer"]) {
    const w = Array.isArray(node.widgets)
      ? node.widgets.find((ww) => ww.name === wname)
      : null;
    if (w) {
      w.computeSize = () => [0, -4];
      w.hidden = true;
      if (w.element instanceof HTMLElement) w.element.style.display = "none";
      if (w.inputEl instanceof HTMLElement) w.inputEl.style.display = "none";
    }
  }

  // -------------------------------------------------------------------------
  // Build DOM
  // -------------------------------------------------------------------------
  const panelEl = document.createElement("div");
  panelEl.className = "aph-panel aph-importer-panel";

  // --- Header ---
  const headerEl = document.createElement("div");
  headerEl.className = "aph-header";
  const headerIcon = document.createElement("img");
  headerIcon.className = "aph-header-icon";
  headerIcon.src = "/extensions/anima-prompt-helper/assets/icon.svg";
  headerIcon.setAttribute("alt", "");
  const headerTitle = document.createElement("span");
  headerTitle.className = "aph-header-title";
  headerTitle.textContent = "Anima Prompt Importer";
  headerEl.appendChild(headerIcon);
  headerEl.appendChild(headerTitle);

  // --- Composer selector + insert all button ---
  const controlsEl = document.createElement("div");
  controlsEl.className = "aph-importer-controls";

  const composerSelect = document.createElement("select");
  composerSelect.className = "aph-palette-composer-select";
  composerSelect.setAttribute("aria-label", "対象 AnimaPromptComposer");
  const composerDefaultOpt = document.createElement("option");
  composerDefaultOpt.value = "";
  composerDefaultOpt.textContent = "-- 対象 Composer --";
  composerSelect.appendChild(composerDefaultOpt);

  const applyAllBtn = document.createElement("button");
  applyAllBtn.type = "button";
  applyAllBtn.className = "aph-palette-insert-btn";
  applyAllBtn.textContent = "選択中タグを全て適用";

  const clearSelBtn = document.createElement("button");
  clearSelBtn.type = "button";
  clearSelBtn.className = "aph-importer-secondary-btn";
  clearSelBtn.textContent = "選択クリア";

  const saveSituationBtn = document.createElement("button");
  saveSituationBtn.type = "button";
  saveSituationBtn.className = "aph-importer-secondary-btn";
  saveSituationBtn.textContent = "💾 シチュとして保存";
  saveSituationBtn.title =
    "選択中の general / natural_language / count をシチュエーションプリセットとして保存";

  controlsEl.appendChild(composerSelect);
  controlsEl.appendChild(applyAllBtn);
  controlsEl.appendChild(clearSelBtn);
  controlsEl.appendChild(saveSituationBtn);

  // --- Status / warning line ---
  const statusEl = document.createElement("p");
  statusEl.className = "aph-tag-palette-warn";
  statusEl.style.display = "none";

  // --- Drop zone + image preview ---
  const dropZone = document.createElement("div");
  dropZone.className = "aph-importer-dropzone";
  dropZone.setAttribute("tabindex", "0");
  dropZone.setAttribute("role", "button");
  dropZone.setAttribute("aria-label", "画像ファイルをドロップ");

  const dropHint = document.createElement("div");
  dropHint.className = "aph-importer-drop-hint";
  dropHint.innerHTML =
    "📷 <strong>画像をドロップ</strong> または <u>クリックで選択</u><br>" +
    "<small>PNG (ComfyUI / A1111) / JPEG (A1111 EXIF)</small>";
  dropZone.appendChild(dropHint);

  const previewWrap = document.createElement("div");
  previewWrap.className = "aph-importer-preview-wrap";
  previewWrap.style.display = "none";
  const previewImg = document.createElement("img");
  previewImg.className = "aph-importer-preview-img";
  previewImg.alt = "ドロップした画像のプレビュー";
  const previewMeta = document.createElement("div");
  previewMeta.className = "aph-importer-preview-meta";
  previewWrap.appendChild(previewImg);
  previewWrap.appendChild(previewMeta);

  // Hidden file picker triggered by clicking the drop zone.
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "image/png,image/jpeg,image/webp";
  fileInput.style.display = "none";

  dropZone.appendChild(fileInput);
  dropZone.appendChild(previewWrap);

  // --- Raw textarea tabs ---
  const rawTabs = document.createElement("div");
  rawTabs.className = "aph-importer-raw-tabs";

  const rawPosBtn = document.createElement("button");
  rawPosBtn.type = "button";
  rawPosBtn.className = "aph-importer-raw-tab aph-importer-raw-tab-active";
  rawPosBtn.textContent = "Positive";
  rawPosBtn.dataset.tab = "pos";

  const rawNegBtn = document.createElement("button");
  rawNegBtn.type = "button";
  rawNegBtn.className = "aph-importer-raw-tab";
  rawNegBtn.textContent = "Negative";
  rawNegBtn.dataset.tab = "neg";

  const rawReclassifyBtn = document.createElement("button");
  rawReclassifyBtn.type = "button";
  rawReclassifyBtn.className = "aph-importer-secondary-btn";
  rawReclassifyBtn.textContent = "🔄 再分類";
  rawReclassifyBtn.title = "編集した raw プロンプトで分類しなおす";

  rawTabs.appendChild(rawPosBtn);
  rawTabs.appendChild(rawNegBtn);
  rawTabs.appendChild(rawReclassifyBtn);

  const rawTextarea = document.createElement("textarea");
  rawTextarea.className = "aph-importer-raw-textarea";
  rawTextarea.placeholder =
    "ここに直接プロンプトを貼り付けて『再分類』を押すこともできます…";
  rawTextarea.rows = 3;

  // --- Buckets container ---
  const bucketsEl = document.createElement("div");
  bucketsEl.className = "aph-importer-buckets";

  // -------------------------------------------------------------------------
  // Assemble
  // -------------------------------------------------------------------------
  panelEl.appendChild(headerEl);
  panelEl.appendChild(controlsEl);
  panelEl.appendChild(statusEl);
  panelEl.appendChild(dropZone);
  panelEl.appendChild(rawTabs);
  panelEl.appendChild(rawTextarea);
  panelEl.appendChild(bucketsEl);

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  /** @type {string} which raw tab is active: "pos" or "neg" */
  let activeRawTab = "pos";

  /** @type {{positive: string, negative: string, format: string, anima_fields: Object|null}} */
  let lastExtracted = {
    positive: "",
    negative: "",
    format: "unknown",
    anima_fields: null,
  };

  /** Token selection state per bucket: Map<field, Set<lowerCaseBareTag>>. */
  /** @type {Object<string, Set<string>>} */
  const selected = {};
  for (const f of COMPOSER_FIELDS) selected[f] = new Set();

  /** Last classification result. */
  let lastBuckets = null;

  // -------------------------------------------------------------------------
  // Sizing
  // -------------------------------------------------------------------------
  const MIN_NODE_WIDTH = 540;
  const MIN_NODE_HEIGHT = 560;
  const NODE_CHROME_HEIGHT = 60;
  const MIN_PANEL_HEIGHT = 520;

  const _panelWidget = node.addDOMWidget(
    "anima_prompt_importer_panel",
    "div",
    panelEl,
    { serialize: false }
  );
  if (_panelWidget) {
    _panelWidget.computeSize = function (width) {
      const nodeBased = (node.size && node.size[1]) - NODE_CHROME_HEIGHT;
      return [width, Math.max(MIN_PANEL_HEIGHT, nodeBased || 0)];
    };
    Object.defineProperty(_panelWidget, "width", {
      get() {
        return undefined;
      },
      set(_v) {
        /* swallow inspector writes */
      },
      configurable: true,
    });
  }

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
    if (changed && node.graph) node.graph.setDirtyCanvas(true, true);
  }
  enforceMinNodeSize();

  const _origOnResize =
    typeof node.onResize === "function" ? node.onResize.bind(node) : null;
  node.onResize = function (size) {
    if (size && size[0] < MIN_NODE_WIDTH) size[0] = MIN_NODE_WIDTH;
    if (size && size[1] < MIN_NODE_HEIGHT) size[1] = MIN_NODE_HEIGHT;
    if (_origOnResize) _origOnResize(size);
  };

  // -------------------------------------------------------------------------
  // Status helpers
  // -------------------------------------------------------------------------
  function showStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.style.display = "";
    statusEl.classList.toggle("aph-importer-status-error", !!isError);
  }
  function clearStatus() {
    statusEl.style.display = "none";
    statusEl.textContent = "";
    statusEl.classList.remove("aph-importer-status-error");
  }

  // -------------------------------------------------------------------------
  // Composer dropdown
  // -------------------------------------------------------------------------
  function refreshComposerList() {
    while (composerSelect.options.length > 1) composerSelect.remove(1);
    const composers = _getComposerNodes(node.graph);
    for (const cn of composers) {
      const opt = document.createElement("option");
      opt.value = String(cn.id);
      opt.textContent =
        cn.title || cn.properties?.title || "Composer #" + cn.id;
      composerSelect.appendChild(opt);
    }
    if (composers.length === 1) {
      composerSelect.value = String(composers[0].id);
    }
  }

  // -------------------------------------------------------------------------
  // Bucket UI
  // -------------------------------------------------------------------------

  /**
   * Render the buckets section from the current ``lastBuckets`` state.
   *
   * For each non-empty bucket we render a labelled section with:
   *   - section header (label + "全選択" / "全解除" / "Composerへ適用" buttons).
   *   - a flexbox row of chip-style buttons; clicking a chip toggles its
   *     selection state.
   */
  function renderBuckets() {
    while (bucketsEl.firstChild) bucketsEl.removeChild(bucketsEl.firstChild);
    if (!lastBuckets) {
      const hint = document.createElement("p");
      hint.className = "aph-importer-empty";
      hint.textContent =
        "ここに分類されたタグが表示されます。画像をドロップするか raw 欄に貼って『再分類』してください。";
      bucketsEl.appendChild(hint);
      return;
    }

    let anyShown = false;
    for (const field of COMPOSER_FIELDS) {
      const tokens = lastBuckets[field] || [];
      if (!tokens.length) continue;
      anyShown = true;
      const section = document.createElement("section");
      section.className = "aph-importer-bucket";
      section.dataset.field = field;

      const head = document.createElement("div");
      head.className = "aph-importer-bucket-head";
      const title = document.createElement("span");
      title.className = "aph-importer-bucket-title";
      title.textContent = _FIELD_LABELS[field] || field;
      const count = document.createElement("span");
      count.className = "aph-importer-bucket-count";
      count.textContent = "(" + tokens.length + ")";

      const allBtn = document.createElement("button");
      allBtn.type = "button";
      allBtn.className = "aph-importer-bucket-btn";
      allBtn.textContent = "全選択";

      const noneBtn = document.createElement("button");
      noneBtn.type = "button";
      noneBtn.className = "aph-importer-bucket-btn";
      noneBtn.textContent = "全解除";

      const applyBtn = document.createElement("button");
      applyBtn.type = "button";
      applyBtn.className = "aph-importer-bucket-apply";
      applyBtn.textContent = "適用 →";
      applyBtn.title = "このカテゴリの選択中タグを Composer の " + field + " に追加";

      head.appendChild(title);
      head.appendChild(count);
      head.appendChild(allBtn);
      head.appendChild(noneBtn);
      head.appendChild(applyBtn);

      const chipRow = document.createElement("div");
      chipRow.className = "aph-importer-chip-row";

      for (const tok of tokens) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "aph-importer-chip";
        chip.dataset.token = tok;
        chip.textContent = tok;
        const key = tok.trim().toLowerCase();
        if (selected[field].has(key)) {
          chip.classList.add("aph-importer-chip-active");
        }
        chip.addEventListener("click", () => {
          if (selected[field].has(key)) {
            selected[field].delete(key);
            chip.classList.remove("aph-importer-chip-active");
          } else {
            selected[field].add(key);
            chip.classList.add("aph-importer-chip-active");
          }
        });
        chipRow.appendChild(chip);
      }

      allBtn.addEventListener("click", () => {
        for (const tok of tokens) selected[field].add(tok.trim().toLowerCase());
        for (const chip of chipRow.querySelectorAll(".aph-importer-chip")) {
          chip.classList.add("aph-importer-chip-active");
        }
      });
      noneBtn.addEventListener("click", () => {
        for (const tok of tokens) selected[field].delete(tok.trim().toLowerCase());
        for (const chip of chipRow.querySelectorAll(".aph-importer-chip")) {
          chip.classList.remove("aph-importer-chip-active");
        }
      });
      applyBtn.addEventListener("click", () => {
        applyFieldToComposer(field);
      });

      section.appendChild(head);
      section.appendChild(chipRow);
      bucketsEl.appendChild(section);
    }

    if (!anyShown) {
      const hint = document.createElement("p");
      hint.className = "aph-importer-empty";
      hint.textContent = "タグが見つかりませんでした。";
      bucketsEl.appendChild(hint);
    }
  }

  /**
   * Apply the currently-selected tokens for ``field`` to the chosen Composer.
   * Returns the number of tokens written (0 if nothing applicable).
   */
  function applyFieldToComposer(field) {
    const composerNodeId = parseInt(composerSelect.value, 10);
    if (!composerNodeId) {
      showStatus("対象 Composer を選択してください。", true);
      return 0;
    }
    const targetComposer = _getComposerNodes(node.graph).find(
      (c) => c.id === composerNodeId
    );
    if (!targetComposer) {
      showStatus("指定した Composer が見つかりません。", true);
      return 0;
    }

    // Source tokens preserve original casing/weights; selection is keyed by
    // lower-case bare tag.
    const tokens = (lastBuckets[field] || []).filter((t) =>
      selected[field].has(t.trim().toLowerCase())
    );
    if (!tokens.length) return 0;

    if (field === "rating") {
      // Combo widget — accept the first selected value only.
      const w = getFieldWidget(targetComposer, "rating");
      if (!w) {
        showStatus("Composer に rating widget がありません。", true);
        return 0;
      }
      const val = tokens[0].trim().toLowerCase();
      if (!["safe", "sensitive", "nsfw", "explicit"].includes(val)) {
        showStatus(`rating '${val}' は無効な値です。`, true);
        return 0;
      }
      w.value = val;
      if (targetComposer.graph) {
        targetComposer.graph.setDirtyCanvas(true, true);
      }
      return 1;
    }

    if (field === "natural_language") {
      // Single-text field — write whole NL block, overwriting existing value.
      const w = getFieldWidget(targetComposer, "natural_language");
      if (!w) return 0;
      const text = tokens.join(" ").trim();
      w.value = text;
      const inputEl = w.element || w.inputEl;
      if (inputEl) {
        inputEl.value = text;
        inputEl.dispatchEvent(new Event("input", { bubbles: true }));
      }
      if (targetComposer.graph) {
        targetComposer.graph.setDirtyCanvas(true, true);
      }
      return 1;
    }

    // Multiline comma-separated fields use the standard add helper, which
    // dedupes lower-case-equivalent tokens.
    let added = 0;
    for (const tok of tokens) {
      const before = (getFieldWidget(targetComposer, field)?.value || "");
      addTagToField(targetComposer, field, tok);
      const after = (getFieldWidget(targetComposer, field)?.value || "");
      if (after !== before) added++;
    }
    return added;
  }

  /**
   * Build a situation-preset snapshot from the currently-selected tokens.
   *
   * Maps the importer's classified buckets onto the situation-preset shape:
   *   - general          → general_tags (array, original casing preserved)
   *   - natural_language  → natural_language (selected NL tokens joined by space)
   *   - count             → count_override (selected count tokens joined by ", ")
   *
   * The other buckets (quality/year/rating/character/series/artist) are not part
   * of a situation preset and are ignored.
   *
   * @returns {{count_override: ?string, general_tags: string[], natural_language: string}}
   */
  function buildSituationSnapshot() {
    const pickSelected = (field) =>
      (lastBuckets && lastBuckets[field] ? lastBuckets[field] : []).filter((t) =>
        selected[field].has(t.trim().toLowerCase())
      );
    const generalTags = pickSelected("general");
    const nlTokens = pickSelected("natural_language");
    const countTokens = pickSelected("count");
    return {
      count_override: countTokens.length ? countTokens.join(", ") : null,
      general_tags: generalTags,
      natural_language: nlTokens.join(" ").trim(),
    };
  }

  // -------------------------------------------------------------------------
  // Classification driver
  // -------------------------------------------------------------------------
  function classifyActiveText() {
    const text = activeRawTab === "pos"
      ? lastExtracted.positive
      : lastExtracted.negative;

    // When classifying the positive tab and we have backend-extracted Anima
    // fields, hand them through so the buckets honour the original layout.
    const animaFields =
      activeRawTab === "pos" ? lastExtracted.anima_fields : null;

    const { buckets } = classifyPrompt(
      text,
      _paletteMap,
      _characterMap,
      animaFields
    );
    lastBuckets = buckets;

    // Default selection: every token of the current tab is selected, so the
    // user can immediately hit "選択中タグを全て適用" and have it do what
    // they expect.
    for (const f of COMPOSER_FIELDS) selected[f] = new Set();
    for (const f of COMPOSER_FIELDS) {
      for (const tok of buckets[f] || []) {
        selected[f].add(tok.trim().toLowerCase());
      }
    }
    renderBuckets();
  }

  // -------------------------------------------------------------------------
  // Extraction
  // -------------------------------------------------------------------------
  async function extractFromFile(file) {
    clearStatus();
    showStatus("メタデータを解析中…");
    try {
      // Display preview
      const reader = new FileReader();
      reader.onload = (e) => {
        previewImg.src = e.target.result;
      };
      reader.readAsDataURL(file);
      previewWrap.style.display = "";
      previewMeta.textContent = file.name + " (" + Math.round(file.size / 1024) + " KB)";

      // Upload to backend
      const fd = new FormData();
      fd.append("image", file);
      const resp = await fetch("/anima_prompt_helper/extract_metadata", {
        method: "POST",
        body: fd,
      });
      if (!resp.ok) {
        const errText = await resp.text();
        showStatus("抽出に失敗しました: " + resp.status + " " + errText, true);
        return;
      }
      const data = await resp.json();
      lastExtracted = {
        positive: data.positive || "",
        negative: data.negative || "",
        format: data.format || "unknown",
        anima_fields: data.anima_fields || null,
      };
      _writeBufferWidget(node, "positive_buffer", lastExtracted.positive);
      _writeBufferWidget(node, "negative_buffer", lastExtracted.negative);

      // Update preview meta with format
      previewMeta.textContent =
        file.name + " — format: " + lastExtracted.format;

      // Show positive tab content
      activeRawTab = "pos";
      rawPosBtn.classList.add("aph-importer-raw-tab-active");
      rawNegBtn.classList.remove("aph-importer-raw-tab-active");
      rawTextarea.value = lastExtracted.positive;

      if (lastExtracted.format === "unknown") {
        showStatus(
          "プロンプトメタデータが見つかりませんでした。raw 欄に直接貼って『再分類』してください。",
          true
        );
      } else {
        showStatus(
          "抽出完了: " + lastExtracted.format +
            "  (positive: " + lastExtracted.positive.length + " 文字 / negative: " +
            lastExtracted.negative.length + " 文字)"
        );
      }

      classifyActiveText();
    } catch (err) {
      console.error("[AnimaPromptImporter] extract error:", err);
      showStatus("抽出エラー: " + err, true);
    }
  }

  // -------------------------------------------------------------------------
  // Wire up events
  // -------------------------------------------------------------------------

  // Drop zone events
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });
  dropZone.addEventListener("dragenter", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add("aph-importer-drop-active");
  });
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.add("aph-importer-drop-active");
  });
  dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove("aph-importer-drop-active");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove("aph-importer-drop-active");
    const file = e.dataTransfer?.files?.[0];
    if (file) extractFromFile(file);
  });
  fileInput.addEventListener("change", () => {
    const f = fileInput.files?.[0];
    if (f) extractFromFile(f);
  });

  // Raw tab switch
  function switchRawTab(tab) {
    activeRawTab = tab;
    if (tab === "pos") {
      rawPosBtn.classList.add("aph-importer-raw-tab-active");
      rawNegBtn.classList.remove("aph-importer-raw-tab-active");
      rawTextarea.value = lastExtracted.positive;
    } else {
      rawNegBtn.classList.add("aph-importer-raw-tab-active");
      rawPosBtn.classList.remove("aph-importer-raw-tab-active");
      rawTextarea.value = lastExtracted.negative;
    }
    classifyActiveText();
  }
  rawPosBtn.addEventListener("click", () => switchRawTab("pos"));
  rawNegBtn.addEventListener("click", () => switchRawTab("neg"));

  // Re-classify from edited textarea
  rawReclassifyBtn.addEventListener("click", () => {
    const text = rawTextarea.value;
    if (activeRawTab === "pos") {
      lastExtracted.positive = text;
      // User-edited text invalidates the backend-extracted anima_fields,
      // so the classifier falls back to heuristics.
      lastExtracted.anima_fields = null;
      _writeBufferWidget(node, "positive_buffer", text);
    } else {
      lastExtracted.negative = text;
      _writeBufferWidget(node, "negative_buffer", text);
    }
    classifyActiveText();
    clearStatus();
  });

  // Apply all selected
  applyAllBtn.addEventListener("click", () => {
    if (!lastBuckets) {
      showStatus("先に画像をドロップするか raw を再分類してください。", true);
      return;
    }
    let total = 0;
    for (const f of COMPOSER_FIELDS) {
      total += applyFieldToComposer(f);
    }
    if (total > 0) {
      showStatus("Composer に " + total + " 件適用しました。");
    } else {
      showStatus("適用するタグが選択されていません。", true);
    }
  });

  clearSelBtn.addEventListener("click", () => {
    for (const f of COMPOSER_FIELDS) selected[f].clear();
    renderBuckets();
  });

  // Save the selected general / natural_language / count tokens as a new
  // situation preset. Opens the shared situation-preset editor pre-filled from
  // the importer's classified state (no Composer node required).
  saveSituationBtn.addEventListener("click", () => {
    if (!lastBuckets) {
      showStatus("先に画像をドロップするか raw を再分類してください。", true);
      return;
    }
    const snapshot = buildSituationSnapshot();
    if (
      !snapshot.general_tags.length &&
      !snapshot.natural_language &&
      !snapshot.count_override
    ) {
      showStatus(
        "general / natural_language / count に選択中のタグがありません。",
        true
      );
      return;
    }
    openSituationPresetEditor({ mode: "create", snapshot });
  });

  composerSelect.addEventListener("change", clearStatus);

  // -------------------------------------------------------------------------
  // Initial state — restore from persisted widget values if any.
  // -------------------------------------------------------------------------
  function initFromWidgets() {
    const posW = node.widgets?.find((w) => w.name === "positive_buffer");
    const negW = node.widgets?.find((w) => w.name === "negative_buffer");
    lastExtracted.positive = (posW && typeof posW.value === "string") ? posW.value : "";
    lastExtracted.negative = (negW && typeof negW.value === "string") ? negW.value : "";
    rawTextarea.value = lastExtracted.positive;
    if (lastExtracted.positive || lastExtracted.negative) {
      classifyActiveText();
    } else {
      renderBuckets();
    }
  }

  refreshComposerList();
  initFromWidgets();

  // Periodic refresh of the composer list (composer nodes may be added later)
  const composerRefreshTimer = setInterval(() => refreshComposerList(), 1500);

  const origOnRemoved =
    typeof node.onRemoved === "function" ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    clearInterval(composerRefreshTimer);
    if (origOnRemoved) origOnRemoved();
  };
}
