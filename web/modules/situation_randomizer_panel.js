/**
 * situation_randomizer_panel.js — DOM panel for AnimaSituationRandomizer nodes.
 *
 * The node has three native widgets: ``count`` (INT), ``seed`` (INT, with
 * control_after_generate) and ``pool`` (multiline STRING). This panel hides
 * the ``pool`` widget and manages it through a richer UI:
 *
 *   - 元プール dropdown: pick a saved pool (built-in default or a user pool)
 *     and 読込 to load its tags into the active pool. 💾 saves the current pool
 *     as a named local user pool; 🗑 deletes the selected user pool.
 *   - シチュエーションを追加: a simple text input with Enter / 追加 button that
 *     appends a situation tag to the active pool. Input `(`/`)` are
 *     backslash-escaped and `_` is normalized to spaces.
 *   - The active pool is shown as a count + removable chip list.
 *   - 🎲 試し引き previews ``count`` random tags (client-side) for a quick
 *     visual check. Actual graph runs use the node's ``seed`` widget in Python.
 *   - 対象 Composer dropdown + 「general欄へ挿入」 injects ``count`` random
 *     situation tags straight into a same-graph AnimaPromptComposer's
 *     ``general`` field.
 *
 * The active pool lives in the node's ``pool`` widget (serialized with the
 * workflow), so Python reads exactly what the panel shows.
 */

import { addTagToField } from "./composer.js";
import {
  SituationPoolStore,
  DEFAULT_POOL_ID,
  seededPickTags,
} from "./situation_pools.js";

// Hard cap on how many chips we render at once — large pools would stall the
// canvas.
const MAX_CHIPS_RENDERED = 300;
const MIN_NODE_WIDTH = 320;
const MIN_NODE_HEIGHT = 360;
const CHIP_AREA_HEIGHT = 150;
const NODE_CHROME_HEIGHT = 90; // count + seed widgets + title above the panel

// ---------------------------------------------------------------------------
// Tag formatting helper (mirrors formatArtistTagForInsert from artist_suggest)
// ---------------------------------------------------------------------------

/**
 * Normalize a raw situation tag for insertion into the prompt pool:
 * - Replace `_` with a space (danbooru convention)
 * - Backslash-escape `(` and `)` (ComfyUI/A1111 prompt syntax)
 *
 * Precondition: tag is a non-empty string
 * Postcondition: returns the formatted string ready to embed in a prompt
 *
 * @param {string} tag
 * @returns {string}
 */
function formatTagForInsert(tag) {
  return tag
    .replace(/_/g, " ")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");
}

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

/** Read a numeric widget by name with a fallback. */
function _intWidget(node, name, fallback) {
  const w = Array.isArray(node.widgets)
    ? node.widgets.find((x) => x.name === name)
    : null;
  const n = w ? parseInt(w.value, 10) : fallback;
  return Number.isFinite(n) ? n : fallback;
}

/** Read the node's ``count`` widget value (>= 1). */
function getCount(node) {
  return Math.max(1, _intWidget(node, "count", 1));
}

/** Read the node's ``seed`` widget value (>= 0). */
function getSeed(node) {
  return Math.max(0, _intWidget(node, "seed", 0));
}

/** Generate a new random seed within JS-safe integer range. */
function _generateRandomSeed() {
  // Number.MAX_SAFE_INTEGER 以下で安全に整数を生成（0xFFFFFFFFFFFFFF は
  // MAX_SAFE_INTEGER を超えて浮動小数点精度が失われるため使用しない）
  return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

/** Write a new seed value into the node's seed widget and fire an input event. */
function _setSeedWidget(node, seedValue) {
  const w = Array.isArray(node.widgets)
    ? node.widgets.find((x) => x.name === "seed")
    : null;
  if (!w) return;
  w.value = seedValue;
  if (w.element && "value" in w.element) {
    w.element.value = String(seedValue);
    try {
      w.element.dispatchEvent(new Event("input", { bubbles: true }));
    } catch (_) { /* ignore */ }
  }
}

/** The node's active tags: its pool, or the built-in default pool if empty. */
function getActiveTags(node) {
  const tags = getPoolTags(node);
  if (tags.length) return tags;
  const builtin = SituationPoolStore.getById(DEFAULT_POOL_ID);
  return builtin ? (builtin.tags || []).slice() : [];
}

/** Write the comma-joined picks into the node's serialized ``picked`` widget. */
function setPickedWidget(node, value) {
  const w = Array.isArray(node.widgets)
    ? node.widgets.find((x) => x.name === "picked")
    : null;
  if (!w) return;
  w.value = value;
  const el = w.element || w.inputEl;
  if (el) {
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

/**
 * Compute a order-independent fingerprint for a tag array.
 * Used to detect whether the pool has changed since the last populate run.
 * @param {string[]} tags
 * @returns {string}
 */
function _computePoolFingerprint(tags) {
  return tags.slice().map((t) => t.toLowerCase()).sort().join("");
}

/**
 * Populate the ``picked`` widget of every AnimaSituationRandomizer node in the
 * graph from its pool, count and seed. Called from the ``app.graphToPrompt``
 * hook at queue time so the chosen situations are serialized into the workflow /
 * prompt and embedded in the saved image's metadata.
 *
 * When ``picked`` already has a value and the pool has not changed since the
 * last run (fingerprint match), the node is skipped so that a workflow loaded
 * from a PNG retains its saved picks on the first queue.
 *
 * @param {Object} graph - LiteGraph graph instance
 * @param {Object} [options]
 * @param {boolean} [options.force=false] - bypass skip logic and always recompute
 */
export function populateSituationRandomizers(graph, { force = false } = {}) {
  if (!graph || !Array.isArray(graph._nodes)) return;
  for (const node of graph._nodes) {
    if (!node || node.type !== "AnimaSituationRandomizer") continue;
    const tags = getActiveTags(node);
    if (!tags.length) { setPickedWidget(node, ""); continue; }

    if (!force) {
      const pickedW = Array.isArray(node.widgets)
        ? node.widgets.find((x) => x.name === "picked") : null;
      const currentPicked = pickedW && typeof pickedW.value === "string"
        ? pickedW.value.trim() : "";
      const fingerprint = _computePoolFingerprint(tags);
      if (currentPicked !== "") {
        if (node.__animaLastPoolFingerprint === undefined) {
          // 初回ロード: picked を信頼して fingerprint だけ初期化
          node.__animaLastPoolFingerprint = fingerprint;
          continue;
        }
        if (node.__animaLastPoolFingerprint === fingerprint) {
          continue; // pool 変更なし → skip
        }
      }
    }

    const picked = seededPickTags(tags, getCount(node), getSeed(node));
    setPickedWidget(node, picked.join(", "));
    node.__animaLastPoolFingerprint = _computePoolFingerprint(tags);
  }
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
 * Build and attach the situation-randomizer panel to a node.
 * @param {Object} node - AnimaSituationRandomizer LiteGraph node instance
 */
export function injectSituationRandomizerPanel(node) {
  // --- Hide the pool + picked widgets (both managed via the panel) ---
  // ``picked`` is still serialized while hidden, so the situations chosen at
  // queue time land in the workflow / prompt metadata even though the widget
  // is not shown; the panel surfaces them in the preview area instead.
  for (const name of ["pool", "picked"]) {
    const w = Array.isArray(node.widgets)
      ? node.widgets.find((x) => x.name === name)
      : null;
    if (!w) continue;
    w.computeSize = () => [0, -4];
    w.hidden = true;
    if (w.element instanceof HTMLElement) w.element.style.display = "none";
    if (w.inputEl instanceof HTMLElement) w.inputEl.style.display = "none";
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
  headerTitle.textContent = "Anima Situation Randomizer";
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

  // --- Add-situation row (simple text input + button, no autocomplete) ---
  const addRow = document.createElement("div");
  addRow.className = "aph-ar-row aph-ar-add-row";
  const addInput = document.createElement("input");
  addInput.type = "text";
  addInput.className = "aph-ar-add-input";
  addInput.placeholder = "シチュエーションタグを検索して追加…（例: classroom）";
  const addBtn = document.createElement("button");
  addBtn.className = "aph-btn";
  addBtn.textContent = "追加";
  addBtn.title = "シチュエーションを追加";
  addRow.append(addInput, addBtn);

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

  // --- Shuffle row ---
  const shuffleRow = document.createElement("div");
  shuffleRow.className = "aph-ar-row aph-ar-shuffle-row";
  const shuffleBtn = document.createElement("button");
  shuffleBtn.className = "aph-btn aph-ar-shuffle-btn";
  shuffleBtn.textContent = "🔀 再シャッフル";
  shuffleBtn.title = "picked を強制再計算して次の queue に反映する（fingerprint を無視）";
  shuffleBtn.style.borderColor = "var(--aph-accent, #4a90e2)";
  shuffleBtn.style.fontWeight = "600";
  shuffleRow.appendChild(shuffleBtn);

  // --- Target composer row ---
  const targetRow = document.createElement("div");
  targetRow.className = "aph-ar-row aph-ar-target-row";
  const composerSelect = document.createElement("select");
  composerSelect.className = "aph-ar-composer-select";
  composerSelect.setAttribute("aria-label", "対象 Composer");
  const insertBtn = document.createElement("button");
  insertBtn.className = "aph-btn aph-ar-insert-btn";
  insertBtn.textContent = "general欄へ挿入";
  targetRow.append(composerSelect, insertBtn);

  // --- Status line ---
  const statusEl = document.createElement("div");
  statusEl.className = "aph-ar-status";
  statusEl.style.display = "none";

  panelEl.append(
    headerEl, sourceRow, addRow, summaryEl, chipsEl,
    previewRow, shuffleRow, targetRow, statusEl
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
    summaryEl.textContent = `プール: ${tags.length} シチュエーション`;
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
    const pools = SituationPoolStore.getAll();
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
    const p = SituationPoolStore.getById(poolSelect.value);
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
  // Add-situation input handlers (no autocomplete; simple Enter / button)
  // -------------------------------------------------------------------------

  function addSituation() {
    const raw = addInput.value.trim();
    if (!raw) return;
    const insert = formatTagForInsert(raw);
    const tags = getPoolTags(node);
    if (!tags.some((t) => t.toLowerCase() === insert.toLowerCase())) {
      tags.push(insert);
      setPoolTags(node, tags);
      renderChips();
    }
    addInput.value = "";
    addInput.focus();
  }

  addBtn.addEventListener("click", addSituation);
  addInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addSituation();
    }
  });

  // -------------------------------------------------------------------------
  // Button handlers
  // -------------------------------------------------------------------------

  poolSelect.addEventListener("change", _refreshDelBtn);

  loadBtn.addEventListener("click", () => {
    const p = SituationPoolStore.getById(poolSelect.value);
    if (!p) { setStatus("プールが見つかりません。", true); return; }
    setPoolTags(node, (p.tags || []).slice());
    renderChips();
    setStatus(`「${p.label}」を読み込みました (${(p.tags || []).length} シチュエーション)。`, false);
  });

  saveBtn.addEventListener("click", async () => {
    const tags = getPoolTags(node);
    if (!tags.length) { setStatus("プールが空です。先にシチュエーションを追加してください。", true); return; }
    const selected = SituationPoolStore.getById(poolSelect.value);
    const suggestedName = selected && selected.user ? selected.label : "My Situations";
    const label = window.prompt("プール名を入力してください:", suggestedName);
    if (label === null) return;
    if (!label.trim()) { setStatus("プール名が空です。", true); return; }
    const id = (selected && selected.user) ? selected.id : _slugifyId(label);
    setStatus("保存中…", false);
    const res = await SituationPoolStore.saveUserPool({ id, label: label.trim(), tags });
    if (res.ok) {
      rebuildPoolOptions();
      poolSelect.value = res.pool.id;
      _refreshDelBtn();
      setStatus(`「${res.pool.label}」を保存しました (${res.pool.tags.length} シチュエーション)。`, false);
    } else {
      setStatus(`保存に失敗しました: ${res.error}`, true);
    }
  });

  delBtn.addEventListener("click", async () => {
    const p = SituationPoolStore.getById(poolSelect.value);
    if (!p || !p.user) { setStatus("ユーザープールを選択してください。", true); return; }
    if (!window.confirm(`「${p.label}」を削除しますか？`)) return;
    const res = await SituationPoolStore.deleteUserPool(p.id);
    if (res.ok) {
      rebuildPoolOptions();
      setStatus(`「${p.label}」を削除しました。`, false);
    } else {
      setStatus(`削除に失敗しました: ${res.error}`, true);
    }
  });

  rollBtn.addEventListener("click", () => {
    const tags = getActiveTags(node);
    if (!tags.length) { previewEl.textContent = "(プールが空)"; return; }
    // Seed-based: this matches exactly what generation will pick (and record).
    const picked = seededPickTags(tags, getCount(node), getSeed(node));
    previewEl.textContent = `seed ${getSeed(node)}: ${picked.join(", ")}`;
  });

  shuffleBtn.addEventListener("click", () => {
    const tags = getActiveTags(node);
    if (!tags.length) { setStatus("プールが空です。", true); return; }
    const newSeed = _generateRandomSeed();
    _setSeedWidget(node, newSeed);
    const picked = seededPickTags(tags, getCount(node), newSeed);
    setPickedWidget(node, picked.join(", "));
    node.__animaLastPoolFingerprint = _computePoolFingerprint(tags);
    previewEl.textContent = `seed ${newSeed}: ${picked.join(", ")}`;
    try {
      if (node.graph && typeof node.graph.setDirtyCanvas === "function") {
        node.graph.setDirtyCanvas(true, true);
      }
    } catch (_) { /* ignore */ }
    setStatus(`シャッフルしました（seed: ${newSeed}）。次の queue に反映されます。`, false);
  });

  insertBtn.addEventListener("click", () => {
    const composerId = parseInt(composerSelect.value, 10);
    if (!composerId) { setStatus("対象 Composer を選択してください。", true); return; }
    const composer = getComposerNodes(node.graph).find((c) => c.id === composerId);
    if (!composer) { setStatus("Composer が見つかりません。", true); return; }
    const slot = composer.inputs
      ? composer.inputs.find((i) => i.name === "general")
      : null;
    if (slot && slot.link != null) {
      setStatus("Composer の general は接続済みです。出力ポートを配線してください。", true);
      return;
    }
    const tags = getActiveTags(node);
    if (!tags.length) { setStatus("プールが空です。", true); return; }
    const picked = seededPickTags(tags, getCount(node), getSeed(node));
    for (const t of picked) addTagToField(composer, "general", t);
    previewEl.textContent = picked.join(", ");
    setStatus(`#${composerId} の general 欄に ${picked.length} シチュエーションを挿入しました。`, false);
  });

  // -------------------------------------------------------------------------
  // Attach as a DOM widget
  // -------------------------------------------------------------------------

  const widget = node.addDOMWidget(
    "anima_situation_randomizer_panel", "div", panelEl, { serialize: false }
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
  const unsubscribe = SituationPoolStore.subscribe(rebuildPoolOptions);

  const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
  node.onRemoved = function () {
    try { unsubscribe(); } catch (_) { /* ignore */ }
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

  // PNG 復元検出: パネル初期描画時に picked が既に埋まっていれば
  // ワークフロー（PNG）から復元されたと判断してその旨を表示する。
  const initialPicked = (Array.isArray(node.widgets)
    ? node.widgets.find((x) => x.name === "picked") : null)?.value?.trim?.() || "";
  if (initialPicked) {
    setStatus("PNG から復元済み。シャッフルすると別の picks に変わります。", false);
  }
}
