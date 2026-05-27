/**
 * artist_randomizer_panel.js — DOM panel for AnimaArtistRandomizer nodes.
 *
 * The node has three native widgets: ``count`` (INT), ``seed`` (INT, with
 * control_after_generate) and ``pool`` (multiline STRING). This panel hides
 * the ``pool`` widget and manages it through a richer UI:
 *
 *   - 元プール dropdown: pick a saved pool (built-in high-score or a user pool)
 *     and 読込 to load its tags into the active pool. 💾 saves the current pool
 *     as a named local user pool; 🗑 deletes the selected user pool.
 *   - 絵師を追加: an autocomplete input (reuses the artist suggest index) that
 *     appends a chosen artist to the active pool.
 *   - The active pool is shown as a count + removable chip list.
 *   - 🎲 試し引き previews ``count`` random artists (client-side) for a quick
 *     visual check. Actual graph runs use the node's ``seed`` widget in Python.
 *   - 対象 Composer dropdown + 「artist欄へ挿入」 injects ``count`` random
 *     artists straight into a same-graph AnimaPromptComposer's ``artist`` field.
 *
 * The active pool lives in the node's ``pool`` widget (serialized with the
 * workflow), so Python reads exactly what the panel shows.
 */

import { addTagToField } from "./composer.js";
import { ArtistPoolStore } from "./artist_pools.js";
import {
  searchArtists,
  formatArtistTagForInsert,
  formatCount,
  hasArtistList,
} from "./artist_suggest.js";

// Hard cap on how many chips we render at once — the built-in pool has
// thousands of tags and rendering them all would stall the canvas.
const MAX_CHIPS_RENDERED = 300;
const MIN_NODE_WIDTH = 320;
const MIN_NODE_HEIGHT = 360;
const CHIP_AREA_HEIGHT = 150;
const NODE_CHROME_HEIGHT = 90; // count + seed widgets + title above the panel

// ---------------------------------------------------------------------------
// Pool widget read / write helpers
// ---------------------------------------------------------------------------

function _poolWidget(node) {
  return Array.isArray(node.widgets)
    ? node.widgets.find((w) => w.name === "pool")
    : null;
}

/** Parse the node's pool widget value into a de-duplicated tag array. */
function getPoolTags(node) {
  const w = _poolWidget(node);
  const raw = w && typeof w.value === "string" ? w.value : "";
  const out = [];
  const seen = new Set();
  for (const chunk of raw.replace(/\n/g, ",").split(",")) {
    const t = chunk.trim();
    if (!t) continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
  }
  return out;
}

/** Write a tag array back into the node's pool widget (comma-joined). */
function setPoolTags(node, tags) {
  const w = _poolWidget(node);
  if (!w) return;
  const newVal = tags.join(", ");
  w.value = newVal;
  const el = w.element || w.inputEl;
  if (el) {
    el.value = newVal;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
  try {
    if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
      node.graph.setDirtyCanvas(true, true);
    }
  } catch (_) { /* ignore */ }
}

/** Read the node's ``count`` widget value (>= 1). */
function getCount(node) {
  const w = Array.isArray(node.widgets)
    ? node.widgets.find((x) => x.name === "count")
    : null;
  const n = w ? parseInt(w.value, 10) : 1;
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

/** Client-side random sample without replacement (preview / manual insert). */
function sampleN(arr, n) {
  const pool = arr.slice();
  const k = Math.min(n, pool.length);
  const out = [];
  for (let i = 0; i < k; i++) {
    const idx = Math.floor(Math.random() * pool.length);
    out.push(pool.splice(idx, 1)[0]);
  }
  return out;
}

/** Same-graph AnimaPromptComposer nodes. */
function getComposerNodes(graph) {
  if (!graph || !Array.isArray(graph._nodes)) return [];
  return graph._nodes.filter((n) => n && n.type === "AnimaPromptComposer");
}

/** Derive a server-valid pool id (matches ^[A-Za-z0-9_-]{1,64}$) from a label. */
function _slugifyId(label) {
  const base = (label || "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 64);
  return base || ("pool_" + Date.now().toString(36));
}

// ---------------------------------------------------------------------------
// Panel injection
// ---------------------------------------------------------------------------

/**
 * Build and attach the artist-randomizer panel to a node.
 * @param {Object} node - AnimaArtistRandomizer LiteGraph node instance
 */
export function injectArtistRandomizerPanel(node) {
  // --- Hide the pool widget (managed via the panel) ---
  const poolW = _poolWidget(node);
  if (poolW) {
    poolW.computeSize = () => [0, -4];
    poolW.hidden = true;
    if (poolW.element instanceof HTMLElement) poolW.element.style.display = "none";
    if (poolW.inputEl instanceof HTMLElement) poolW.inputEl.style.display = "none";
  }

  const panelEl = document.createElement("div");
  panelEl.className = "aph-panel aph-artist-randomizer-panel";

  // --- Header ---
  const headerEl = document.createElement("div");
  headerEl.className = "aph-header";
  const headerIcon = document.createElement("img");
  headerIcon.className = "aph-header-icon";
  headerIcon.src = "/extensions/anima-prompt-helper/assets/icon.svg";
  headerIcon.setAttribute("alt", "");
  const headerTitle = document.createElement("span");
  headerTitle.className = "aph-header-title";
  headerTitle.textContent = "Anima Artist Randomizer";
  headerEl.appendChild(headerIcon);
  headerEl.appendChild(headerTitle);

  // --- Source pool row ---
  const sourceRow = document.createElement("div");
  sourceRow.className = "aph-ar-row aph-ar-source-row";
  const poolSelect = document.createElement("select");
  poolSelect.className = "aph-ar-pool-select";
  poolSelect.setAttribute("aria-label", "元プール");
  const loadBtn = document.createElement("button");
  loadBtn.className = "aph-btn aph-ar-load-btn";
  loadBtn.textContent = "読込";
  loadBtn.title = "選択したプールを編集中プールに読み込む";
  const saveBtn = document.createElement("button");
  saveBtn.className = "aph-btn aph-ar-save-btn";
  saveBtn.textContent = "💾保存";
  saveBtn.title = "編集中プールを名前付きでローカル保存";
  const delBtn = document.createElement("button");
  delBtn.className = "aph-btn aph-ar-del-btn";
  delBtn.textContent = "🗑";
  delBtn.title = "選択中のユーザープールを削除";
  sourceRow.append(poolSelect, loadBtn, saveBtn, delBtn);

  // --- Add-artist (suggest) row ---
  const addRow = document.createElement("div");
  addRow.className = "aph-ar-row aph-ar-add-row";
  const addInput = document.createElement("input");
  addInput.type = "text";
  addInput.className = "aph-ar-add-input";
  addInput.placeholder = hasArtistList()
    ? "絵師を検索して追加… (例: dairi)"
    : "絵師サジェスト未ロード";
  if (!hasArtistList()) addInput.disabled = true;
  addRow.appendChild(addInput);

  // Floating suggest dropdown (appended to body, positioned under the input).
  const suggestEl = document.createElement("div");
  suggestEl.className = "aph-artist-suggest aph-ar-suggest";
  suggestEl.style.display = "none";
  document.body.appendChild(suggestEl);

  // --- Pool summary + chips ---
  const summaryEl = document.createElement("div");
  summaryEl.className = "aph-ar-summary";
  const chipsEl = document.createElement("div");
  chipsEl.className = "aph-ar-chips";
  chipsEl.style.maxHeight = CHIP_AREA_HEIGHT + "px";

  // --- Preview row ---
  const previewRow = document.createElement("div");
  previewRow.className = "aph-ar-row aph-ar-preview-row";
  const rollBtn = document.createElement("button");
  rollBtn.className = "aph-btn aph-ar-roll-btn";
  rollBtn.textContent = "🎲 試し引き";
  rollBtn.title = "count 件をランダム抽選してプレビュー（実行時は seed で決定）";
  const previewEl = document.createElement("div");
  previewEl.className = "aph-ar-preview";
  previewRow.append(rollBtn, previewEl);

  // --- Target composer row ---
  const targetRow = document.createElement("div");
  targetRow.className = "aph-ar-row aph-ar-target-row";
  const composerSelect = document.createElement("select");
  composerSelect.className = "aph-ar-composer-select";
  composerSelect.setAttribute("aria-label", "対象 Composer");
  const insertBtn = document.createElement("button");
  insertBtn.className = "aph-btn aph-ar-insert-btn";
  insertBtn.textContent = "artist欄へ挿入";
  targetRow.append(composerSelect, insertBtn);

  // --- Status line ---
  const statusEl = document.createElement("div");
  statusEl.className = "aph-ar-status";
  statusEl.style.display = "none";

  panelEl.append(
    headerEl, sourceRow, addRow, summaryEl, chipsEl,
    previewRow, targetRow, statusEl
  );

  function setStatus(msg, isError) {
    if (!msg) {
      statusEl.style.display = "none";
      statusEl.textContent = "";
      return;
    }
    statusEl.textContent = msg;
    statusEl.style.display = "";
    statusEl.classList.toggle("aph-ar-status-error", !!isError);
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  function renderChips() {
    const tags = getPoolTags(node);
    summaryEl.textContent = `プール: ${tags.length} 絵師`;
    chipsEl.innerHTML = "";
    const shown = tags.slice(0, MAX_CHIPS_RENDERED);
    for (const tag of shown) {
      const chip = document.createElement("span");
      chip.className = "aph-ar-chip";
      const label = document.createElement("span");
      label.className = "aph-ar-chip-label";
      label.textContent = tag;
      const x = document.createElement("button");
      x.className = "aph-ar-chip-x";
      x.textContent = "×";
      x.title = "プールから削除";
      x.addEventListener("click", () => {
        const next = getPoolTags(node).filter(
          (t) => t.toLowerCase() !== tag.toLowerCase()
        );
        setPoolTags(node, next);
        renderChips();
      });
      chip.append(label, x);
      chipsEl.appendChild(chip);
    }
    if (tags.length > MAX_CHIPS_RENDERED) {
      const more = document.createElement("span");
      more.className = "aph-ar-chip-more";
      more.textContent = `…他 ${tags.length - MAX_CHIPS_RENDERED} 件`;
      chipsEl.appendChild(more);
    }
  }

  function rebuildPoolOptions() {
    const prev = poolSelect.value;
    poolSelect.innerHTML = "";
    const pools = ArtistPoolStore.getAll();
    for (const p of pools) {
      const opt = document.createElement("option");
      opt.value = p.id;
      const mark = p.user ? "★ " : "● ";
      opt.textContent = `${mark}${p.label} (${(p.tags || []).length})`;
      poolSelect.appendChild(opt);
    }
    if (pools.some((p) => p.id === prev)) poolSelect.value = prev;
    else if (pools.length) poolSelect.value = pools[0].id;
    _refreshDelBtn();
  }

  function _refreshDelBtn() {
    const p = ArtistPoolStore.getById(poolSelect.value);
    delBtn.disabled = !(p && p.user);
  }

  function refreshComposerList() {
    const prev = composerSelect.value;
    composerSelect.innerHTML = "";
    const composers = getComposerNodes(node.graph);
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = composers.length
      ? "-- 対象 Composer --"
      : "(Composer なし)";
    composerSelect.appendChild(placeholder);
    for (const c of composers) {
      const opt = document.createElement("option");
      opt.value = String(c.id);
      opt.textContent = `#${c.id} ${c.title || "Composer"}`;
      composerSelect.appendChild(opt);
    }
    if ([...composerSelect.options].some((o) => o.value === prev)) {
      composerSelect.value = prev;
    }
  }

  // -------------------------------------------------------------------------
  // Suggest dropdown behaviour for the add-artist input
  // -------------------------------------------------------------------------

  let _activeIdx = -1;
  let _matches = [];

  function positionSuggest() {
    const r = addInput.getBoundingClientRect();
    suggestEl.style.left = r.left + "px";
    suggestEl.style.top = (r.bottom + 2) + "px";
    suggestEl.style.width = Math.max(r.width, 220) + "px";
  }

  function hideSuggest() {
    suggestEl.style.display = "none";
    _activeIdx = -1;
    _matches = [];
  }

  function addArtist(tag) {
    const insert = formatArtistTagForInsert(tag);
    const tags = getPoolTags(node);
    if (!tags.some((t) => t.toLowerCase() === insert.toLowerCase())) {
      tags.push(insert);
      setPoolTags(node, tags);
      renderChips();
    }
    addInput.value = "";
    hideSuggest();
    addInput.focus();
  }

  function renderSuggest() {
    suggestEl.innerHTML = "";
    if (!_matches.length) { hideSuggest(); return; }
    _matches.forEach((m, idx) => {
      const item = document.createElement("div");
      item.className = "aph-artist-suggest-item";
      if (idx === _activeIdx) item.classList.add("active");
      const tagSpan = document.createElement("span");
      tagSpan.className = "aph-artist-suggest-tag";
      tagSpan.textContent = formatArtistTagForInsert(m.t);
      const cSpan = document.createElement("span");
      cSpan.className = "aph-artist-suggest-count";
      cSpan.textContent = formatCount(m.c);
      item.append(tagSpan, cSpan);
      item.addEventListener("mousedown", (e) => { e.preventDefault(); addArtist(m.t); });
      item.addEventListener("mouseenter", () => {
        _activeIdx = idx;
        [...suggestEl.children].forEach((c, i) => c.classList.toggle("active", i === idx));
      });
      suggestEl.appendChild(item);
    });
    positionSuggest();
    suggestEl.style.display = "block";
  }

  function refreshSuggest() {
    const q = addInput.value.trim();
    if (q.length < 1) { hideSuggest(); return; }
    _matches = searchArtists(q, 20);
    _activeIdx = _matches.length ? 0 : -1;
    renderSuggest();
  }

  addInput.addEventListener("input", refreshSuggest);
  addInput.addEventListener("keydown", (e) => {
    if (suggestEl.style.display === "none") return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      _activeIdx = (_activeIdx + 1) % _matches.length;
      renderSuggest();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      _activeIdx = (_activeIdx - 1 + _matches.length) % _matches.length;
      renderSuggest();
    } else if (e.key === "Enter" || e.key === "Tab") {
      if (_activeIdx >= 0) { e.preventDefault(); addArtist(_matches[_activeIdx].t); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      hideSuggest();
    }
  });
  addInput.addEventListener("blur", () => setTimeout(hideSuggest, 150));

  // -------------------------------------------------------------------------
  // Button handlers
  // -------------------------------------------------------------------------

  poolSelect.addEventListener("change", _refreshDelBtn);

  loadBtn.addEventListener("click", () => {
    const p = ArtistPoolStore.getById(poolSelect.value);
    if (!p) { setStatus("プールが見つかりません。", true); return; }
    setPoolTags(node, (p.tags || []).slice());
    renderChips();
    setStatus(`「${p.label}」を読み込みました (${(p.tags || []).length} 絵師)。`, false);
  });

  saveBtn.addEventListener("click", async () => {
    const tags = getPoolTags(node);
    if (!tags.length) { setStatus("プールが空です。先に絵師を追加してください。", true); return; }
    const selected = ArtistPoolStore.getById(poolSelect.value);
    const suggestedName = selected && selected.user ? selected.label : "My Artists";
    const label = window.prompt("プール名を入力してください:", suggestedName);
    if (label === null) return;
    if (!label.trim()) { setStatus("プール名が空です。", true); return; }
    const id = (selected && selected.user) ? selected.id : _slugifyId(label);
    setStatus("保存中…", false);
    const res = await ArtistPoolStore.saveUserPool({ id, label: label.trim(), tags });
    if (res.ok) {
      rebuildPoolOptions();
      poolSelect.value = res.pool.id;
      _refreshDelBtn();
      setStatus(`「${res.pool.label}」を保存しました (${res.pool.tags.length} 絵師)。`, false);
    } else {
      setStatus(`保存に失敗しました: ${res.error}`, true);
    }
  });

  delBtn.addEventListener("click", async () => {
    const p = ArtistPoolStore.getById(poolSelect.value);
    if (!p || !p.user) { setStatus("ユーザープールを選択してください。", true); return; }
    if (!window.confirm(`「${p.label}」を削除しますか？`)) return;
    const res = await ArtistPoolStore.deleteUserPool(p.id);
    if (res.ok) {
      rebuildPoolOptions();
      setStatus(`「${p.label}」を削除しました。`, false);
    } else {
      setStatus(`削除に失敗しました: ${res.error}`, true);
    }
  });

  rollBtn.addEventListener("click", () => {
    const tags = getPoolTags(node);
    if (!tags.length) { previewEl.textContent = "(プールが空)"; return; }
    const picked = sampleN(tags, getCount(node));
    previewEl.textContent = picked.join(", ");
  });

  insertBtn.addEventListener("click", () => {
    const composerId = parseInt(composerSelect.value, 10);
    if (!composerId) { setStatus("対象 Composer を選択してください。", true); return; }
    const composer = getComposerNodes(node.graph).find((c) => c.id === composerId);
    if (!composer) { setStatus("Composer が見つかりません。", true); return; }
    const slot = composer.inputs
      ? composer.inputs.find((i) => i.name === "artist")
      : null;
    if (slot && slot.link != null) {
      setStatus("Composer の artist は接続済みです。出力ポートを配線してください。", true);
      return;
    }
    const tags = getPoolTags(node);
    if (!tags.length) { setStatus("プールが空です。", true); return; }
    const picked = sampleN(tags, getCount(node));
    for (const t of picked) addTagToField(composer, "artist", t);
    previewEl.textContent = picked.join(", ");
    setStatus(`#${composerId} の artist 欄に ${picked.length} 絵師を挿入しました。`, false);
  });

  // -------------------------------------------------------------------------
  // Attach as a DOM widget
  // -------------------------------------------------------------------------

  const widget = node.addDOMWidget(
    "anima_artist_randomizer_panel", "div", panelEl, { serialize: false }
  );
  if (widget) {
    widget.computeSize = function (width) {
      const h = Math.max(panelEl.scrollHeight + 8, MIN_NODE_HEIGHT - NODE_CHROME_HEIGHT);
      return [width, h];
    };
    Object.defineProperty(widget, "width", {
      get() { return undefined; },
      set(_v) { /* swallow inspector-driven writes */ },
      configurable: true,
    });
  }

  if (node.size[0] < MIN_NODE_WIDTH) node.size[0] = MIN_NODE_WIDTH;
  if (node.size[1] < MIN_NODE_HEIGHT) node.size[1] = MIN_NODE_HEIGHT;

  // Keep the source dropdown in sync with store mutations (save/delete).
  const unsubscribe = ArtistPoolStore.subscribe(rebuildPoolOptions);

  const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    try { unsubscribe(); } catch (_) { /* ignore */ }
    if (suggestEl.parentNode) suggestEl.parentNode.removeChild(suggestEl);
    if (origOnRemoved) origOnRemoved();
  };

  // Refresh the composer list when the node is interacted with (cheap).
  const origOnMouseDown = node.onMouseDown ? node.onMouseDown.bind(node) : null;
  node.onMouseDown = function (...args) {
    refreshComposerList();
    if (origOnMouseDown) return origOnMouseDown(...args);
  };

  // Initial paint.
  rebuildPoolOptions();
  refreshComposerList();
  renderChips();
}
