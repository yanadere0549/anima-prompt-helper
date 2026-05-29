/**
 * preset_editor.js — Modal dialog for creating / editing / deleting user
 * character and situation presets.
 *
 * Public API:
 *   openPresetEditor({ mode, preset, sourceComposerNode })
 *     - mode: "create" | "edit"; preset: existing preset when editing;
 *       sourceComposerNode: composer to snapshot field defaults from.
 *   quickSaveFromComposer(composerNode) — character preset quick save.
 *
 *   openSituationPresetEditor({ mode, preset, sourceComposerNode })
 *     - Same shape, but builds the situation-preset fields:
 *       category / count_override / general_tags / natural_language.
 *   quickSaveSituationFromComposer(composerNode) — situation preset quick save.
 */

import { CharacterPresetStore, snapshotComposerFields } from "./character_presets.js";
import { SituationPresetStore, snapshotSituationFromComposer } from "./situation_presets.js";
import { PrefixPresetStore, snapshotPrefixFromComposer } from "./prefix_presets.js";

// ---------------------------------------------------------------------------
// Dialog: full-form editor
// ---------------------------------------------------------------------------

let _activeDialog = null;

/**
 * Generates a kebab-case-ish id from a label.
 * Falls back to "preset_<timestamp>" if the label produces an empty slug.
 */
function _slugifyLabel(label) {
  const slug = (label || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
  if (slug) return "user_" + slug;
  return "user_preset_" + Date.now();
}

function _isValidId(id) {
  return typeof id === "string" && /^[A-Za-z0-9_\-]{1,64}$/.test(id);
}

/**
 * Open the preset editor dialog.
 *
 * @param {Object} opts
 * @param {"create"|"edit"} opts.mode
 * @param {Object} [opts.preset] - existing preset when editing
 * @param {Object} [opts.sourceComposerNode] - composer to pre-fill from
 *                                              when creating from current state
 */
export function openPresetEditor(opts) {
  closeActive();
  const mode = opts && opts.mode === "edit" ? "edit" : "create";
  const existing = mode === "edit" && opts && opts.preset ? opts.preset : null;
  const snapshot = mode === "create" && opts && opts.sourceComposerNode
    ? snapshotComposerFields(opts.sourceComposerNode)
    : { character: "", series: "", general: [], artist: [] };

  const overlay = document.createElement("div");
  overlay.className = "aph-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const dialog = document.createElement("div");
  dialog.className = "aph-modal-dialog";
  overlay.appendChild(dialog);

  // Header
  const header = document.createElement("div");
  header.className = "aph-modal-header";
  const title = document.createElement("h3");
  title.className = "aph-modal-title";
  title.textContent = mode === "edit"
    ? "キャラクタープリセットを編集"
    : "キャラクタープリセットを作成";
  header.appendChild(title);
  const closeBtn = document.createElement("button");
  closeBtn.className = "aph-modal-close";
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "閉じる");
  closeBtn.textContent = "×";
  header.appendChild(closeBtn);

  // Form body
  const body = document.createElement("div");
  body.className = "aph-modal-body";

  // ID
  const idGroup = _formGroup("ID (英数_-, 半角)", "aph-pe-id");
  const idInput = document.createElement("input");
  idInput.type = "text";
  idInput.id = "aph-pe-id";
  idInput.className = "aph-modal-input";
  idInput.maxLength = 64;
  idInput.value = existing ? existing.id : "";
  if (existing) idInput.disabled = true;
  idGroup.appendChild(idInput);

  // Label
  const labelGroup = _formGroup("表示名 (Label) *", "aph-pe-label");
  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.id = "aph-pe-label";
  labelInput.className = "aph-modal-input";
  labelInput.maxLength = 120;
  labelInput.value = existing ? (existing.label || "") : "";
  labelGroup.appendChild(labelInput);

  // Character
  const charGroup = _formGroup("Character タグ", "aph-pe-char");
  const charInput = document.createElement("input");
  charInput.type = "text";
  charInput.id = "aph-pe-char";
  charInput.className = "aph-modal-input";
  charInput.maxLength = 512;
  charInput.value = existing ? (existing.character || "") : snapshot.character;
  charGroup.appendChild(charInput);

  // Series
  const seriesGroup = _formGroup("Series タグ", "aph-pe-series");
  const seriesInput = document.createElement("input");
  seriesInput.type = "text";
  seriesInput.id = "aph-pe-series";
  seriesInput.className = "aph-modal-input";
  seriesInput.maxLength = 512;
  seriesInput.value = existing ? (existing.series || "") : snapshot.series;
  seriesGroup.appendChild(seriesInput);

  // Essential general tags
  const generalGroup = _formGroup(
    "Essential general tags (カンマ区切り)", "aph-pe-general");
  const generalInput = document.createElement("textarea");
  generalInput.id = "aph-pe-general";
  generalInput.className = "aph-modal-textarea";
  generalInput.rows = 3;
  generalInput.value = existing
    ? (Array.isArray(existing.essential_general_tags)
        ? existing.essential_general_tags.join(", ") : "")
    : snapshot.general.join(", ");
  generalGroup.appendChild(generalInput);

  // Recommended artists
  const artistGroup = _formGroup(
    "Recommended artists (@-prefix, カンマ区切り)", "aph-pe-artist");
  const artistInput = document.createElement("textarea");
  artistInput.id = "aph-pe-artist";
  artistInput.className = "aph-modal-textarea";
  artistInput.rows = 2;
  artistInput.value = existing
    ? (Array.isArray(existing.recommended_artists)
        ? existing.recommended_artists.join(", ") : "")
    : snapshot.artist.join(", ");
  artistGroup.appendChild(artistInput);

  // Notes
  const notesGroup = _formGroup("Notes", "aph-pe-notes");
  const notesInput = document.createElement("textarea");
  notesInput.id = "aph-pe-notes";
  notesInput.className = "aph-modal-textarea";
  notesInput.rows = 2;
  notesInput.maxLength = 1024;
  notesInput.value = existing ? (existing.notes || "") : "";
  notesGroup.appendChild(notesInput);

  // Tier
  const tierGroup = _formGroup("Tier (優先度 1-5)", "aph-pe-tier");
  const tierSelect = document.createElement("select");
  tierSelect.id = "aph-pe-tier";
  tierSelect.className = "aph-modal-input";
  for (let t = 5; t >= 1; t--) {
    const o = document.createElement("option");
    o.value = String(t);
    o.textContent = String(t);
    tierSelect.appendChild(o);
  }
  tierSelect.value = String(existing ? (existing.tier || 3) : 5);
  tierGroup.appendChild(tierSelect);

  body.appendChild(idGroup);
  body.appendChild(labelGroup);
  body.appendChild(charGroup);
  body.appendChild(seriesGroup);
  body.appendChild(generalGroup);
  body.appendChild(artistGroup);
  body.appendChild(notesGroup);
  body.appendChild(tierGroup);

  // Status line
  const statusEl = document.createElement("p");
  statusEl.className = "aph-modal-status";
  statusEl.style.display = "none";

  // Footer buttons
  const footer = document.createElement("div");
  footer.className = "aph-modal-footer";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "aph-modal-btn aph-modal-btn-danger";
  deleteBtn.textContent = "削除";
  if (mode !== "edit" || !existing || !existing.user) {
    deleteBtn.style.display = "none";
  }

  const spacer = document.createElement("div");
  spacer.style.flex = "1";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "aph-modal-btn";
  cancelBtn.textContent = "キャンセル";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "aph-modal-btn aph-modal-btn-primary";
  saveBtn.textContent = mode === "edit" ? "更新" : "保存";

  footer.appendChild(deleteBtn);
  footer.appendChild(spacer);
  footer.appendChild(cancelBtn);
  footer.appendChild(saveBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(statusEl);
  dialog.appendChild(footer);

  // Auto-generate id while label changes (create mode only)
  if (!existing) {
    labelInput.addEventListener("input", () => {
      if (!idInput.dataset.userEdited) {
        idInput.value = _slugifyLabel(labelInput.value);
      }
    });
    idInput.addEventListener("input", () => {
      idInput.dataset.userEdited = "true";
    });
  }

  // Event handlers
  const close = () => {
    if (overlay.parentElement) overlay.parentElement.removeChild(overlay);
    if (_activeDialog === overlay) _activeDialog = null;
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };
  document.addEventListener("keydown", onKey);
  closeBtn.addEventListener("click", close);
  cancelBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  saveBtn.addEventListener("click", async () => {
    const id = idInput.value.trim();
    const label = labelInput.value.trim();
    if (!_isValidId(id)) {
      _showStatus(statusEl, "ID は半角英数字 _ - のみ、1〜64文字で。", "error");
      idInput.focus();
      return;
    }
    if (!label) {
      _showStatus(statusEl, "表示名 (Label) を入力してください。", "error");
      labelInput.focus();
      return;
    }
    const generalTags = generalInput.value
      .split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    const artists = artistInput.value
      .split(/[,\n]/).map((s) => s.trim()).filter(Boolean);

    const payload = {
      id,
      label,
      character: charInput.value.trim(),
      series: seriesInput.value.trim(),
      essential_general_tags: generalTags,
      recommended_artists: artists,
      notes: notesInput.value.trim(),
      tier: parseInt(tierSelect.value, 10) || 3,
    };
    saveBtn.disabled = true;
    _showStatus(statusEl, "保存中…", "info");
    const result = await CharacterPresetStore.saveUserPreset(payload);
    saveBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "保存しました。", "success");
      setTimeout(close, 600);
    } else {
      _showStatus(statusEl, `保存失敗: ${result.error}`, "error");
    }
  });

  deleteBtn.addEventListener("click", async () => {
    if (!existing) return;
    if (!confirm(`プリセット「${existing.label}」を削除しますか？`)) return;
    deleteBtn.disabled = true;
    _showStatus(statusEl, "削除中…", "info");
    const result = await CharacterPresetStore.deleteUserPreset(existing.id);
    deleteBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "削除しました。", "success");
      setTimeout(close, 500);
    } else {
      _showStatus(statusEl, `削除失敗: ${result.error}`, "error");
    }
  });

  document.body.appendChild(overlay);
  _activeDialog = overlay;
  labelInput.focus();
}

/**
 * Quick save: snapshot the composer's current character/series/general/artist
 * values, prompt for a label, and save.
 *
 * @param {Object} composerNode
 */
export async function quickSaveFromComposer(composerNode) {
  if (!composerNode) return;
  const snap = snapshotComposerFields(composerNode);
  if (!snap.character && !snap.series && snap.general.length === 0) {
    alert("character / series / general フィールドが空のため、保存できません。");
    return;
  }
  // Open the editor pre-filled (let the user confirm label/id).
  openPresetEditor({ mode: "create", sourceComposerNode: composerNode });
}

function closeActive() {
  if (_activeDialog && _activeDialog.parentElement) {
    _activeDialog.parentElement.removeChild(_activeDialog);
  }
  _activeDialog = null;
}

// ---------------------------------------------------------------------------
// Situation preset editor
// ---------------------------------------------------------------------------

// Predefined category options for the situation editor. "custom" lets the
// user type their own.
const SITUATION_CATEGORY_OPTIONS = [
  "daily", "nature", "weather", "season", "urban",
  "fantasy", "scifi", "studio", "battle", "custom",
];

/**
 * Open the situation-preset editor dialog.
 *
 * Pre-fill priority (create mode): ``opts.snapshot`` (a direct
 * {count_override, general_tags, natural_language} object — used by the Prompt
 * Importer to seed the form from its classified tokens) takes precedence over
 * ``opts.sourceComposerNode`` (snapshotted from a live Composer node).
 *
 * @param {Object} opts
 * @param {"create"|"edit"} opts.mode
 * @param {Object} [opts.preset]
 * @param {Object} [opts.sourceComposerNode]
 * @param {{count_override: ?string, general_tags: string[], natural_language: string}} [opts.snapshot]
 */
export function openSituationPresetEditor(opts) {
  closeActive();
  const mode = opts && opts.mode === "edit" ? "edit" : "create";
  const existing = mode === "edit" && opts && opts.preset ? opts.preset : null;
  let snapshot = { count_override: null, general_tags: [], natural_language: "" };
  if (mode === "create" && opts) {
    if (opts.snapshot && typeof opts.snapshot === "object") {
      snapshot = {
        count_override: opts.snapshot.count_override || null,
        general_tags: Array.isArray(opts.snapshot.general_tags)
          ? opts.snapshot.general_tags
          : [],
        natural_language: typeof opts.snapshot.natural_language === "string"
          ? opts.snapshot.natural_language
          : "",
      };
    } else if (opts.sourceComposerNode) {
      snapshot = snapshotSituationFromComposer(opts.sourceComposerNode);
    }
  }

  const overlay = document.createElement("div");
  overlay.className = "aph-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const dialog = document.createElement("div");
  dialog.className = "aph-modal-dialog";
  overlay.appendChild(dialog);

  // Header
  const header = document.createElement("div");
  header.className = "aph-modal-header";
  const title = document.createElement("h3");
  title.className = "aph-modal-title";
  title.textContent = mode === "edit"
    ? "シチュエーションプリセットを編集"
    : "シチュエーションプリセットを作成";
  header.appendChild(title);
  const closeBtn = document.createElement("button");
  closeBtn.className = "aph-modal-close";
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "閉じる");
  closeBtn.textContent = "×";
  header.appendChild(closeBtn);

  // Body
  const body = document.createElement("div");
  body.className = "aph-modal-body";

  // ID
  const idGroup = _formGroup("ID (英数_-, 半角)", "aph-spe-id");
  const idInput = document.createElement("input");
  idInput.type = "text";
  idInput.id = "aph-spe-id";
  idInput.className = "aph-modal-input";
  idInput.maxLength = 64;
  idInput.value = existing ? existing.id : "";
  if (existing) idInput.disabled = true;
  idGroup.appendChild(idInput);

  // Label
  const labelGroup = _formGroup("表示名 (Label) *", "aph-spe-label");
  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.id = "aph-spe-label";
  labelInput.className = "aph-modal-input";
  labelInput.maxLength = 120;
  labelInput.value = existing ? (existing.label || "") : "";
  labelGroup.appendChild(labelInput);

  // Category (select, with custom override field shown when "custom")
  const catGroup = _formGroup("カテゴリ", "aph-spe-cat");
  const catSelect = document.createElement("select");
  catSelect.id = "aph-spe-cat";
  catSelect.className = "aph-modal-input";
  for (const c of SITUATION_CATEGORY_OPTIONS) {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    catSelect.appendChild(o);
  }
  const initialCat = existing && typeof existing.category === "string"
    ? existing.category : "daily";
  const isKnownCat = SITUATION_CATEGORY_OPTIONS.includes(initialCat);
  catSelect.value = isKnownCat ? initialCat : "custom";
  catGroup.appendChild(catSelect);

  const customCatInput = document.createElement("input");
  customCatInput.type = "text";
  customCatInput.placeholder = "カスタムカテゴリ名";
  customCatInput.className = "aph-modal-input";
  customCatInput.maxLength = 32;
  customCatInput.style.marginTop = "4px";
  customCatInput.value = isKnownCat ? "" : initialCat;
  customCatInput.style.display = catSelect.value === "custom" ? "" : "none";
  catGroup.appendChild(customCatInput);
  catSelect.addEventListener("change", () => {
    customCatInput.style.display = catSelect.value === "custom" ? "" : "none";
  });

  // Count override
  const countGroup = _formGroup(
    "count_override (空なら未設定 — 例: 1girl, solo)", "aph-spe-count");
  const countInput = document.createElement("input");
  countInput.type = "text";
  countInput.id = "aph-spe-count";
  countInput.className = "aph-modal-input";
  countInput.maxLength = 128;
  countInput.value = existing
    ? (existing.count_override || "")
    : (snapshot.count_override || "");
  countGroup.appendChild(countInput);

  // General tags
  const generalGroup = _formGroup(
    "general_tags (カンマ区切り)", "aph-spe-general");
  const generalInput = document.createElement("textarea");
  generalInput.id = "aph-spe-general";
  generalInput.className = "aph-modal-textarea";
  generalInput.rows = 3;
  generalInput.value = existing
    ? (Array.isArray(existing.general_tags)
        ? existing.general_tags.join(", ") : "")
    : snapshot.general_tags.join(", ");
  generalGroup.appendChild(generalInput);

  // Natural language
  const nlGroup = _formGroup(
    "natural_language (英語のシーン描写文)", "aph-spe-nl");
  const nlInput = document.createElement("textarea");
  nlInput.id = "aph-spe-nl";
  nlInput.className = "aph-modal-textarea";
  nlInput.rows = 3;
  nlInput.maxLength = 2048;
  nlInput.value = existing
    ? (existing.natural_language || "")
    : snapshot.natural_language;
  nlGroup.appendChild(nlInput);

  // Notes
  const notesGroup = _formGroup("Notes", "aph-spe-notes");
  const notesInput = document.createElement("textarea");
  notesInput.id = "aph-spe-notes";
  notesInput.className = "aph-modal-textarea";
  notesInput.rows = 2;
  notesInput.maxLength = 1024;
  notesInput.value = existing ? (existing.notes || "") : "";
  notesGroup.appendChild(notesInput);

  // Tier
  const tierGroup = _formGroup("Tier (優先度 1-5)", "aph-spe-tier");
  const tierSelect = document.createElement("select");
  tierSelect.id = "aph-spe-tier";
  tierSelect.className = "aph-modal-input";
  for (let t = 5; t >= 1; t--) {
    const o = document.createElement("option");
    o.value = String(t);
    o.textContent = String(t);
    tierSelect.appendChild(o);
  }
  tierSelect.value = String(existing ? (existing.tier || 3) : 5);
  tierGroup.appendChild(tierSelect);

  body.appendChild(idGroup);
  body.appendChild(labelGroup);
  body.appendChild(catGroup);
  body.appendChild(countGroup);
  body.appendChild(generalGroup);
  body.appendChild(nlGroup);
  body.appendChild(notesGroup);
  body.appendChild(tierGroup);

  // Status line
  const statusEl = document.createElement("p");
  statusEl.className = "aph-modal-status";
  statusEl.style.display = "none";

  // Footer
  const footer = document.createElement("div");
  footer.className = "aph-modal-footer";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "aph-modal-btn aph-modal-btn-danger";
  deleteBtn.textContent = "削除";
  if (mode !== "edit" || !existing || !existing.user) {
    deleteBtn.style.display = "none";
  }

  const spacer = document.createElement("div");
  spacer.style.flex = "1";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "aph-modal-btn";
  cancelBtn.textContent = "キャンセル";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "aph-modal-btn aph-modal-btn-primary";
  saveBtn.textContent = mode === "edit" ? "更新" : "保存";

  footer.appendChild(deleteBtn);
  footer.appendChild(spacer);
  footer.appendChild(cancelBtn);
  footer.appendChild(saveBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(statusEl);
  dialog.appendChild(footer);

  if (!existing) {
    labelInput.addEventListener("input", () => {
      if (!idInput.dataset.userEdited) {
        idInput.value = _slugifyLabel(labelInput.value);
      }
    });
    idInput.addEventListener("input", () => {
      idInput.dataset.userEdited = "true";
    });
  }

  const close = () => {
    if (overlay.parentElement) overlay.parentElement.removeChild(overlay);
    if (_activeDialog === overlay) _activeDialog = null;
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };
  document.addEventListener("keydown", onKey);
  closeBtn.addEventListener("click", close);
  cancelBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  saveBtn.addEventListener("click", async () => {
    const id = idInput.value.trim();
    const label = labelInput.value.trim();
    if (!_isValidId(id)) {
      _showStatus(statusEl, "ID は半角英数字 _ - のみ、1〜64文字で。", "error");
      idInput.focus();
      return;
    }
    if (!label) {
      _showStatus(statusEl, "表示名 (Label) を入力してください。", "error");
      labelInput.focus();
      return;
    }
    let category = catSelect.value;
    if (category === "custom") {
      category = customCatInput.value.trim().toLowerCase();
      if (!category) category = "custom";
    }
    const generalTags = generalInput.value
      .split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    const countOverride = countInput.value.trim();
    const payload = {
      id,
      label,
      category,
      count_override: countOverride || null,
      general_tags: generalTags,
      natural_language: nlInput.value.trim(),
      notes: notesInput.value.trim(),
      tier: parseInt(tierSelect.value, 10) || 3,
    };
    saveBtn.disabled = true;
    _showStatus(statusEl, "保存中…", "info");
    const result = await SituationPresetStore.saveUserPreset(payload);
    saveBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "保存しました。", "success");
      setTimeout(close, 600);
    } else {
      _showStatus(statusEl, `保存失敗: ${result.error}`, "error");
    }
  });

  deleteBtn.addEventListener("click", async () => {
    if (!existing) return;
    if (!confirm(`シチュエーション「${existing.label}」を削除しますか？`)) return;
    deleteBtn.disabled = true;
    _showStatus(statusEl, "削除中…", "info");
    const result = await SituationPresetStore.deleteUserPreset(existing.id);
    deleteBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "削除しました。", "success");
      setTimeout(close, 500);
    } else {
      _showStatus(statusEl, `削除失敗: ${result.error}`, "error");
    }
  });

  document.body.appendChild(overlay);
  _activeDialog = overlay;
  labelInput.focus();
}

/**
 * Quick save for a situation: snapshot the composer's count/general/
 * natural_language fields and open the editor pre-filled.
 *
 * @param {Object} composerNode
 */
export async function quickSaveSituationFromComposer(composerNode) {
  if (!composerNode) return;
  const snap = snapshotSituationFromComposer(composerNode);
  if (snap.general_tags.length === 0 && !snap.natural_language && !snap.count_override) {
    alert("general / natural_language / count フィールドが空のため、保存できません。");
    return;
  }
  openSituationPresetEditor({ mode: "create", sourceComposerNode: composerNode });
}

// ---------------------------------------------------------------------------
// Prefix preset editor
// ---------------------------------------------------------------------------

const PREFIX_RATING_OPTIONS = ["safe", "sensitive", "nsfw", "explicit"];

/**
 * Open the prefix-preset editor dialog.
 *
 * Saved fields: id, label, quality, year, rating (combo), extra, notes, tier.
 * The ``extra`` field is the comma-separated string inserted immediately
 * after ``rating`` when this preset is selected (mirroring ``default_extra``
 * for the built-in ooo_anima_default preset).
 *
 * @param {Object} opts
 * @param {"create"|"edit"} opts.mode
 * @param {Object} [opts.preset] - existing preset when editing
 * @param {Object} [opts.sourceComposerNode] - composer to pre-fill from
 *                                              when creating from current state
 */
export function openPrefixPresetEditor(opts) {
  closeActive();
  const mode = opts && opts.mode === "edit" ? "edit" : "create";
  const existing = mode === "edit" && opts && opts.preset ? opts.preset : null;
  const snapshot = mode === "create" && opts && opts.sourceComposerNode
    ? snapshotPrefixFromComposer(opts.sourceComposerNode)
    : { quality: "", year: "", rating: "safe", extra: "" };

  const overlay = document.createElement("div");
  overlay.className = "aph-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const dialog = document.createElement("div");
  dialog.className = "aph-modal-dialog";
  overlay.appendChild(dialog);

  // Header
  const header = document.createElement("div");
  header.className = "aph-modal-header";
  const title = document.createElement("h3");
  title.className = "aph-modal-title";
  title.textContent = mode === "edit"
    ? "プリフィックスプリセットを編集"
    : "プリフィックスプリセットを作成";
  header.appendChild(title);
  const closeBtn = document.createElement("button");
  closeBtn.className = "aph-modal-close";
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "閉じる");
  closeBtn.textContent = "×";
  header.appendChild(closeBtn);

  // Body
  const body = document.createElement("div");
  body.className = "aph-modal-body";

  // ID
  const idGroup = _formGroup("ID (英数_-, 半角)", "aph-ppe-id");
  const idInput = document.createElement("input");
  idInput.type = "text";
  idInput.id = "aph-ppe-id";
  idInput.className = "aph-modal-input";
  idInput.maxLength = 64;
  idInput.value = existing ? existing.id : "";
  if (existing) idInput.disabled = true;
  idGroup.appendChild(idInput);

  // Label
  const labelGroup = _formGroup("表示名 (Label) *", "aph-ppe-label");
  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.id = "aph-ppe-label";
  labelInput.className = "aph-modal-input";
  labelInput.maxLength = 120;
  labelInput.value = existing ? (existing.label || "") : "";
  labelGroup.appendChild(labelInput);

  // Quality
  const qGroup = _formGroup("Quality タグ (カンマ区切り)", "aph-ppe-quality");
  const qInput = document.createElement("input");
  qInput.type = "text";
  qInput.id = "aph-ppe-quality";
  qInput.className = "aph-modal-input";
  qInput.maxLength = 512;
  qInput.value = existing ? (existing.quality || "") : snapshot.quality;
  qInput.placeholder = "masterpiece, best quality, high quality";
  qGroup.appendChild(qInput);

  // Year
  const yGroup = _formGroup("Year / era (カンマ区切り)", "aph-ppe-year");
  const yInput = document.createElement("input");
  yInput.type = "text";
  yInput.id = "aph-ppe-year";
  yInput.className = "aph-modal-input";
  yInput.maxLength = 256;
  yInput.value = existing ? (existing.year || "") : snapshot.year;
  yInput.placeholder = "newest, year 2025, year 2024";
  yGroup.appendChild(yInput);

  // Rating (combo)
  const rGroup = _formGroup("Rating", "aph-ppe-rating");
  const rSelect = document.createElement("select");
  rSelect.id = "aph-ppe-rating";
  rSelect.className = "aph-modal-input";
  for (const r of PREFIX_RATING_OPTIONS) {
    const o = document.createElement("option");
    o.value = r;
    o.textContent = r;
    rSelect.appendChild(o);
  }
  const initialRating = existing
    ? (PREFIX_RATING_OPTIONS.includes(existing.rating) ? existing.rating : "safe")
    : (PREFIX_RATING_OPTIONS.includes(snapshot.rating) ? snapshot.rating : "safe");
  rSelect.value = initialRating;
  rGroup.appendChild(rSelect);

  // Extra (inserted after rating)
  const eGroup = _formGroup(
    "Extra (rating の後に挿入, 例: game cg)", "aph-ppe-extra");
  const eInput = document.createElement("input");
  eInput.type = "text";
  eInput.id = "aph-ppe-extra";
  eInput.className = "aph-modal-input";
  eInput.maxLength = 256;
  eInput.value = existing ? (existing.extra || "") : snapshot.extra;
  eGroup.appendChild(eInput);

  // Notes
  const notesGroup = _formGroup("Notes", "aph-ppe-notes");
  const notesInput = document.createElement("textarea");
  notesInput.id = "aph-ppe-notes";
  notesInput.className = "aph-modal-textarea";
  notesInput.rows = 2;
  notesInput.maxLength = 1024;
  notesInput.value = existing ? (existing.notes || "") : "";
  notesGroup.appendChild(notesInput);

  // Tier
  const tierGroup = _formGroup("Tier (優先度 1-5)", "aph-ppe-tier");
  const tierSelect = document.createElement("select");
  tierSelect.id = "aph-ppe-tier";
  tierSelect.className = "aph-modal-input";
  for (let t = 5; t >= 1; t--) {
    const o = document.createElement("option");
    o.value = String(t);
    o.textContent = String(t);
    tierSelect.appendChild(o);
  }
  tierSelect.value = String(existing ? (existing.tier || 3) : 5);
  tierGroup.appendChild(tierSelect);

  body.appendChild(idGroup);
  body.appendChild(labelGroup);
  body.appendChild(qGroup);
  body.appendChild(yGroup);
  body.appendChild(rGroup);
  body.appendChild(eGroup);
  body.appendChild(notesGroup);
  body.appendChild(tierGroup);

  // Status
  const statusEl = document.createElement("p");
  statusEl.className = "aph-modal-status";
  statusEl.style.display = "none";

  // Footer
  const footer = document.createElement("div");
  footer.className = "aph-modal-footer";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "aph-modal-btn aph-modal-btn-danger";
  deleteBtn.textContent = "削除";
  // Only user presets can be deleted (builtin entries are read-only).
  if (mode !== "edit" || !existing || !existing.user) {
    deleteBtn.style.display = "none";
  }

  const spacer = document.createElement("div");
  spacer.style.flex = "1";

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "aph-modal-btn";
  cancelBtn.textContent = "キャンセル";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "aph-modal-btn aph-modal-btn-primary";
  saveBtn.textContent = mode === "edit" ? "更新" : "保存";

  footer.appendChild(deleteBtn);
  footer.appendChild(spacer);
  footer.appendChild(cancelBtn);
  footer.appendChild(saveBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(statusEl);
  dialog.appendChild(footer);

  if (!existing) {
    labelInput.addEventListener("input", () => {
      if (!idInput.dataset.userEdited) {
        idInput.value = _slugifyLabel(labelInput.value);
      }
    });
    idInput.addEventListener("input", () => {
      idInput.dataset.userEdited = "true";
    });
  }

  const close = () => {
    if (overlay.parentElement) overlay.parentElement.removeChild(overlay);
    if (_activeDialog === overlay) _activeDialog = null;
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  };
  document.addEventListener("keydown", onKey);
  closeBtn.addEventListener("click", close);
  cancelBtn.addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  saveBtn.addEventListener("click", async () => {
    const id = idInput.value.trim();
    const label = labelInput.value.trim();
    if (!_isValidId(id)) {
      _showStatus(statusEl, "ID は半角英数字 _ - のみ、1〜64文字で。", "error");
      idInput.focus();
      return;
    }
    if (id === "none" || id === "ooo_anima_default" || id === "custom") {
      _showStatus(statusEl, "その ID は組み込み予約語のため使用できません。", "error");
      idInput.focus();
      return;
    }
    if (!label) {
      _showStatus(statusEl, "表示名 (Label) を入力してください。", "error");
      labelInput.focus();
      return;
    }
    const payload = {
      id,
      label,
      quality: qInput.value.trim(),
      year: yInput.value.trim(),
      rating: rSelect.value,
      extra: eInput.value.trim(),
      notes: notesInput.value.trim(),
      tier: parseInt(tierSelect.value, 10) || 3,
    };
    saveBtn.disabled = true;
    _showStatus(statusEl, "保存中…", "info");
    const result = await PrefixPresetStore.saveUserPreset(payload);
    saveBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "保存しました。", "success");
      setTimeout(close, 600);
    } else {
      _showStatus(statusEl, `保存失敗: ${result.error}`, "error");
    }
  });

  deleteBtn.addEventListener("click", async () => {
    if (!existing) return;
    if (!confirm(`プリセット「${existing.label}」を削除しますか？`)) return;
    deleteBtn.disabled = true;
    _showStatus(statusEl, "削除中…", "info");
    const result = await PrefixPresetStore.deleteUserPreset(existing.id);
    deleteBtn.disabled = false;
    if (result.ok) {
      _showStatus(statusEl, "削除しました。", "success");
      setTimeout(close, 500);
    } else {
      _showStatus(statusEl, `削除失敗: ${result.error}`, "error");
    }
  });

  document.body.appendChild(overlay);
  _activeDialog = overlay;
  labelInput.focus();
}

/**
 * Quick save: snapshot the composer's current quality/year/rating fields and
 * open the editor pre-filled.
 *
 * @param {Object} composerNode
 */
export async function quickSavePrefixFromComposer(composerNode) {
  if (!composerNode) return;
  const snap = snapshotPrefixFromComposer(composerNode);
  if (!snap.quality && !snap.year && !snap.extra) {
    alert("quality / year / extra のいずれも空のため、保存できません。");
    return;
  }
  openPrefixPresetEditor({ mode: "create", sourceComposerNode: composerNode });
}

function _formGroup(labelText, forId) {
  const group = document.createElement("div");
  group.className = "aph-modal-group";
  const label = document.createElement("label");
  label.className = "aph-modal-label";
  label.htmlFor = forId;
  label.textContent = labelText;
  group.appendChild(label);
  return group;
}

function _showStatus(el, text, kind) {
  el.textContent = text;
  el.dataset.kind = kind || "info";
  el.style.display = "";
}
