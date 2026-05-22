# anima-prompt-helper — Troubleshooting Guide

Step-by-step solutions for the most common problems. Use the section headings to jump to the category that matches your symptom.

---

## Contents

- [Installation issues](#installation-issues)
- [Palette and data issues](#palette-and-data-issues)
- [Generation and validation issues](#generation-and-validation-issues)
- [Workflow and serialization issues](#workflow-and-serialization-issues)
- [Preset behavior issues](#preset-behavior-issues)
- [Performance issues](#performance-issues)

---

## Installation issues

### Nodes don't appear in the Add Node menu

**Symptom**: Right-click → Add Node → no "Anima" category is visible.

**Cause**: ComfyUI was not restarted after the extension was copied into `custom_nodes/`. ComfyUI only scans `custom_nodes/` at startup; hot-reloading is not supported for new extensions.

**Fix**:
1. Confirm the folder is in the correct location:
   ```
   ComfyUI/custom_nodes/anima-prompt-helper/   ← correct
   ComfyUI/custom_nodes/some-pack/anima-prompt-helper/  ← wrong (nested)
   ```
2. Stop ComfyUI (Ctrl+C in the terminal or close the process).
3. Restart ComfyUI.
4. Open the Add Node menu and look for the **Anima** category.

**Verification**: Three entries should appear under **Anima**: `Anima Prompt Composer`, `Anima Prompt -> Conditioning`, and `Anima Negative Prompt Composer`.

---

### Nodes appear in the menu but the palette panel UI is missing

**Symptom**: The node is on the canvas but the tab strip, search box, and live preview are absent — only the raw text widgets appear.

**Cause**: Either (a) the browser has cached the old (or absent) frontend JS file and is not loading the current version, or (b) the `WEB_DIRECTORY` path is not being served at the expected URL prefix, causing the browser's `fetch` of the extension JS to fail silently.

**Fix**:
1. Hard-reload the ComfyUI browser tab:
   - Windows/Linux: **Ctrl + Shift + R**
   - macOS: **Cmd + Shift + R**
2. Open the browser DevTools Console (F12). Look for a red `Failed to load` or `404` error referencing `anima_prompt_helper.js`.
3. If the error says `404`, confirm that `web/extensions/anima_prompt_helper.js` exists inside the extension folder. The path relative to the extension root must be:
   ```
   anima-prompt-helper/web/extensions/anima_prompt_helper.js
   ```
4. If the file exists and you still get 404, check that `WEB_DIRECTORY = "./web"` is set in `__init__.py`. Open the file and verify this line is present.
5. Restart ComfyUI, then hard-reload the browser again.

**Verification**: After reload, clicking the node shows a tab strip with category tabs (Quality, Year / Era, etc.) and a search input below it.

---

### `ImportError: cannot import name 'PromptServer'` on startup

**Symptom**: ComfyUI terminal prints a Python traceback like:
```
ImportError: cannot import name 'PromptServer' from 'server'
```
or the extension fails to load entirely.

**Cause**: A stale installation from an early prototype used a top-level `from server import PromptServer` statement in `__init__.py`. In the current version this import is wrapped in a `try/except ImportError` block inside `python/api/__init__.py`, so it is skipped gracefully outside ComfyUI. If you see this error, the installed files are out of date.

**Fix**:
1. Check whether you have an older copy of the extension:
   ```powershell
   Get-Content "ComfyUI\custom_nodes\anima-prompt-helper\__init__.py" | Select-String "PromptServer"
   ```
   The current version should produce no output (the import is in `python/api/__init__.py` only, inside `try/except`).
2. If the old pattern is present, update the extension:
   ```powershell
   cd ComfyUI\custom_nodes\anima-prompt-helper
   git pull
   ```
3. Restart ComfyUI.

**Verification**: No `ImportError` lines appear in the startup log. The `Anima` category appears in the Add Node menu.

---

### "Extension not loaded" in the ComfyUI startup log

**Symptom**: The terminal shows something like `Failed to load extension anima-prompt-helper` or the extension is silently absent.

**Cause**: A Python syntax error in `__init__.py` (or any file it imports at module load time) prevents the module from loading. This is distinct from a runtime error — it happens before any node is registered.

**Fix**:
1. Run a syntax check manually:
   ```powershell
   python -m py_compile ComfyUI\custom_nodes\anima-prompt-helper\__init__.py
   ```
   If there is a syntax error, the command prints the file and line number.
2. Also check the node files:
   ```powershell
   python -m py_compile ComfyUI\custom_nodes\anima-prompt-helper\python\nodes.py
   python -m py_compile ComfyUI\custom_nodes\anima-prompt-helper\python\composer.py
   python -m py_compile ComfyUI\custom_nodes\anima-prompt-helper\python\validators.py
   ```
3. Fix any reported syntax errors or restore the files from the repository.
4. Restart ComfyUI.

**Verification**: The startup log no longer shows an error for this extension, and the Anima nodes appear in the menu.

---

## Palette and data issues

### Tag palette is empty or shows "Palette failed to load"

**Symptom**: The palette panel renders but the tag grid is empty and shows "Palette failed to load. Check the console for details."

**Cause**: The backend's `GET /anima_prompt_helper/palette` route returned HTTP 503, which means `data/tag_palette.json` was not found at the expected path (`anima-prompt-helper/data/tag_palette.json`). The file may have been deleted, the clone may be incomplete, or the `data/` subdirectory is missing entirely.

**Fix**:
1. Open the browser DevTools Console (F12) and look for a `console.error` from `[AnimaPromptHelper]`.
2. Check the ComfyUI terminal for the log line:
   ```
   tag_palette.json not found at ...
   ```
3. Verify the file exists:
   ```powershell
   Test-Path "ComfyUI\custom_nodes\anima-prompt-helper\data\tag_palette.json"
   ```
4. If `False`, re-clone or re-download the extension to restore the `data/` directory.
5. Restart ComfyUI (the palette is cached in memory after the first successful read; a restart clears the cache).

**Verification**: The palette panel shows clickable tag buttons organized into category tabs.

---

### "presets unavailable" shown in the character preset dropdown

**Symptom**: The character preset dropdown at the top of the panel shows "presets unavailable" and is disabled.

**Cause**: `GET /anima_prompt_helper/character_presets` returned HTTP 503, meaning `data/character_presets.json` is missing. `panel.js` disables the `<select>` element and inserts the "presets unavailable" option when `CharacterPresetStore.getAll()` returns an empty array (which happens when the API call fails at load time).

**Fix**:
1. Check the ComfyUI terminal for:
   ```
   character_presets.json not found at ...
   ```
2. Verify the file:
   ```powershell
   Test-Path "ComfyUI\custom_nodes\anima-prompt-helper\data\character_presets.json"
   ```
3. Re-clone or restore the `data/` directory if the file is absent.
4. Restart ComfyUI.

**Verification**: The dropdown lists character names such as "Hatsune Miku (Vocaloid)" and is interactive.

---

### Some palette tags don't appear when searching

**Symptom**: Typing a tag name in the search box produces no results even though the tag exists in a palette tab.

**Cause**: Search matches against the `tag` field and all entries in the `aliases` array in `data/tag_palette.json`. If the search term matches an alias that is not listed in the `aliases` array for that tag, the tag is not returned. The search is a case-insensitive substring match; it does not perform fuzzy matching.

**Fix**:
1. Try searching for the exact canonical tag text (e.g. `drill hair` instead of `ringlet curl`).
2. If the tag exists in the palette but a useful alias is missing, open `data/tag_palette.json` and add the alias to the tag's `aliases` array:
   ```json
   { "tag": "drill hair", "aliases": ["ringlet", "spiral curl"], "count": 0 }
   ```
3. Restart ComfyUI to reload the palette (the file is cached in memory after the first read).

**Verification**: Searching with the new alias term returns the expected tag button.

---

### Tag palette buttons click but nothing is added to the field

**Symptom**: Clicking a palette tag button does not add the tag to any widget field.

**Cause**: `addTagToField` in `composer.js` calls `getFieldWidget(node, fieldName)`, which searches `node.widgets` for a widget with a matching `name` property. If the widget name in the node's `INPUT_TYPES` has been renamed or the node was loaded from a workflow created with an older version where widget names differed, the lookup returns `null` and a warning is logged.

**Fix**:
1. Open the browser DevTools Console (F12) and look for:
   ```
   [AnimaPromptHelper] addTagToField: widget not found: <fieldName>
   ```
2. If present, the node's widget list does not contain a widget named `<fieldName>`. Delete the node and re-add a fresh **Anima Prompt Composer** from the Add Node menu.
3. If the issue persists on a freshly created node, verify that `python/nodes.py` defines `INPUT_TYPES` with the expected field names (`quality`, `year`, `rating`, `count`, `character`, `series`, `artist`, `general`, `natural_language`, `prefix_preset`).

**Verification**: Clicking a palette tag appends it to the corresponding field widget and the live preview updates.

---

## Generation and validation issues

### Red ERROR badge: "Artist tag must start with '@'"

**Symptom**: A red `ARTIST_MISSING_AT` badge appears in the validation bar.

**Cause**: The `artist` field contains a token that does not begin with `@`. The check fires on every comma-separated token individually; even a single bare name (e.g. `wlop`) among otherwise correct entries (e.g. `@kantoku`) will trigger the error. The rule is defined in `validators.py` (`check_artist_at`).

**Fix**:
1. Find the token(s) flagged by hovering over the badge (the tooltip shows "Tag: `<token>`").
2. Prepend `@` to each bare name: `wlop` → `@wlop`.
3. Alternatively, delete the artist field content and re-add artists using the **Artists** tab in the palette — those buttons always include the `@` prefix.

**Verification**: The red badge disappears after the 400 ms debounce elapses.

---

### Orange WARNING badge: "contains underscore — use spaces"

**Symptom**: A yellow/orange `UNDERSCORE_TAG` badge appears.

**Cause**: A tag in a non-`natural_language` field contains an underscore character (`_`) and does not match the exempt patterns (`score_\d+` or `score_\d+_up`). Common examples: `blue_hair`, `school_uniform`, `long_hair`. The rule is defined in `validators.py` (`check_underscore`).

**Fix**:
1. Hover over the badge to see which field and tag triggered it.
2. Replace underscores with spaces in the tag: `blue_hair` → `blue hair`.
3. Tags from the palette are always correctly space-separated. Use the palette to re-insert the tag if uncertain.

**Verification**: The orange badge clears. Note: `score_7`, `score_7_up`, `score_8`, etc. are intentionally exempt and will never trigger this warning.

---

### Orange WARNING badge: "Tag contains uppercase letters"

**Symptom**: An `UPPERCASE_TAG` warning badge appears.

**Cause**: A token in a field that is subject to the lowercase check (`quality`, `year`, `count`, `artist`, `general`) contains at least one uppercase letter. The `character`, `series`, and `natural_language` fields are exempt. The rule is defined in `validators.py` (`check_lowercase`).

**Fix**:
1. Find the offending token via the badge tooltip.
2. Rewrite it in all lowercase: `Masterpiece` → `masterpiece`, `Blue Hair` → `blue hair`.
3. The palette only inserts lowercase tags, so switching to palette-based input avoids this entirely.

**Verification**: The warning badge clears after 400 ms.

---

### Orange WARNING badge: "Assembled prompt is N chars (> 3000)"

**Symptom**: A `LONG_PROMPT` badge appears; the live preview shows a very long string.

**Cause**: The assembled prompt exceeds 3000 characters. The threshold is defined in `validators.py` (`check_long`). This is a warning only — it does not block generation. The concern is that standard CLIP tokenizes in 77-token chunks; very long prompts may have distant tokens weighted lower by the encoder.

**Fix**: This is informational, not blocking. If prompt length is a concern:
1. Remove low-priority tags from the `general` field.
2. Shorten the `natural_language` description.
3. Consider whether duplicated tags exist across fields (check for `DUPLICATE_TAG` warnings too).

**Verification**: Trimming the prompt below 3000 characters clears the badge. Generation proceeds normally regardless.

---

### `RuntimeError: CLIP input is None` — node turns red

**Symptom**: Queuing a generation causes the **Anima Prompt -> Conditioning** node to turn red with the error message `CLIP input is None`.

**Cause**: The `clip` input slot on the `AnimaPromptToConditioning` node has nothing connected to it. The check is in `nodes.py` (`encode` method): `if clip is None: raise RuntimeError("CLIP input is None")`.

**Fix**:
1. Add a **Load Checkpoint** node (or **DualCLIPLoader**) if one is not present in the workflow.
2. Connect the `CLIP` output socket from the checkpoint loader to the `clip` input socket on the **Anima Prompt -> Conditioning** node.
3. Queue again.

**Verification**: The node is no longer red and the generation completes, returning a `CONDITIONING` tensor.

---

### Character preset fills wrong tags or omits expected tags

**Symptom**: Selecting a character preset populates the fields but the output prompt is missing expected character-specific tags, or the tags look like the wrong character.

**Cause**: Each preset in `data/character_presets.json` supplies a fixed set of `essential_general_tags`. If the preset was selected but the `general` field already contained conflicting tags, the new preset tags are appended — they do not replace existing content. Alternatively, the wrong preset was selected (some characters share similar names).

**Fix**:
1. Before selecting a preset, clear the `character`, `series`, and `general` fields manually if you want a clean slate.
2. After selecting, review the `general` field and remove any tags that conflict with the new character's design.
3. Verify the correct preset was selected — Danbooru uses inverted name order for some characters (e.g. "Nezuko Kamado" maps to `kamado nezuko`; the preset handles this automatically).

**Verification**: The live preview shows the canonical character, series, and essential general tags in the correct positions.

---

### "Empty prompt" INFO badge even though text fields are filled

**Symptom**: An `EMPTY_PROMPT` info badge appears despite all fields appearing to have content.

**Cause**: The `check_empty` rule fires when the assembled string, after all tokenization and joining, is empty. This can happen when all field values consist entirely of whitespace or commas — `join_fields` strips each token and drops empty strings, so a field containing only `"  ,  ,  "` contributes nothing to the output.

**Fix**:
1. Check each field widget for invisible whitespace or comma-only content.
2. Clear and retype the values, or use palette buttons to add tags.
3. Check the live preview textarea — if it is also empty, the assembled output genuinely has no content.

**Verification**: The INFO badge disappears once the assembled string is non-empty.

---

### Duplicate tag WARNING fires unexpectedly

**Symptom**: A `DUPLICATE_TAG` warning appears even though you don't think you repeated any tag.

**Cause**: The duplicate check normalizes tokens by lowercasing and collapsing whitespace, then compares across all nine fields. A character preset may have added a tag (e.g. `blue hair`) to the `general` field that you also have in another field. The check is cross-field, not per-field.

**Fix**:
1. Hover over the badge tooltip — it shows `Tag '<token>' appears in both '<field1>' and '<field2>'`.
2. Remove the tag from one of the two fields.

**Verification**: The warning clears after 400 ms.

---

## Workflow and serialization issues

### Workflow reopens but panel state (selected tab, search query) does not restore

**Symptom**: After saving a workflow and reopening it, the correct tab is not selected and the search box is empty, even though those states were set when the workflow was saved.

**Cause**: Panel state (selected tab, search query) is persisted via a `node.serialize` override defined in `persist.js`, which writes an `anima_state` property into the node's serialized JSON. If another extension has also overridden `node.serialize` for the same node type (or for all nodes), one of the overrides may silently clobber the other, causing `anima_state` to not be written.

**Fix**:
1. Disable other extensions one at a time (using ComfyUI-Manager's disable feature) and reload to identify the conflicting extension.
2. If a conflict is identified, report it to the other extension's author so they can use a `super`/chain pattern rather than replacing `serialize` entirely.
3. As a workaround, note that widget field values (`quality`, `year`, `rating`, etc.) are always restored correctly because ComfyUI handles those via `widgets_values` natively — only the cosmetic panel state (tab, search) is affected.

**Verification**: After disabling the conflicting extension, save and reopen the workflow; the tab and search query should be restored.

---

### Saved workflow doesn't restore the `prefix_preset` selection

**Symptom**: Reopening a saved workflow shows `prefix_preset` reset to its default (`ooo_anima_default`) rather than the value you had set.

**Cause**: ComfyUI serializes widget values in the order they are defined in `INPUT_TYPES`. The `prefix_preset` COMBO is the 10th widget in `AnimaPromptComposer.INPUT_TYPES` (0-indexed: `quality`, `year`, `rating`, `count`, `character`, `series`, `artist`, `general`, `natural_language`, `prefix_preset`). If a workflow was saved with an older version of the extension that had fewer widgets, the `widgets_values` array in the JSON may be shorter than 10 entries, causing ComfyUI to fall back to the widget's default for the missing position.

**Fix**:
1. Open the workflow JSON in a text editor and find the `AnimaPromptComposer` node.
2. Check that `widgets_values` has exactly 10 entries (one per widget, in the order above).
3. If the array is shorter, add the missing values at the correct positions and save.
4. Reload the workflow in ComfyUI.

**Verification**: The `prefix_preset` widget shows the expected value after loading.

---

### Two AnimaPromptComposer nodes interfere with each other's validation

**Symptom**: When two Anima Prompt Composer nodes are on the canvas, typing in one node's fields sometimes triggers validation badge updates on the other node.

**Cause**: `validateRemote` in `composer.js` uses a single module-level `_validateTimer` variable (`let _validateTimer = null`). This timer is shared across all node instances in the same browser session (it is not per-node). Rapid typing in one node can cancel a pending validation for the other node.

**Fix**: This is a known limitation in v0.2.0. Each node does eventually receive its correct validation result — the shared timer only causes a slight delay or missed intermediate update; the final state is always correct once typing stops. A per-node timer is planned for a future release.

**Verification**: Stop typing; after 400 ms both nodes will have up-to-date validation badges.

---

## Preset behavior issues

### OOO_Anima preset output doesn't include `game cg`

**Symptom**: Using the `ooo_anima_default` preset, the assembled prompt does not contain the `game cg` token that the OOO_Anima model card recommends.

**Cause**: In versions before v0.2.0, `join_fields` did not inject the `default_extra` field after the rating token. This was fixed in v0.2.0: `composer.py` now reads `default_extra` from `data/anima_spec.json` and inserts it as a separate stage immediately after the `rating` field.

**Fix**:
1. Check your installed version:
   ```powershell
   cd ComfyUI\custom_nodes\anima-prompt-helper
   git log --oneline -5
   ```
2. If you are on a pre-v0.2.0 commit, update:
   ```powershell
   git pull
   ```
3. Restart ComfyUI.

**Verification**: The live preview now shows `..., safe, game cg, 1girl, ...` when `prefix_preset` is `ooo_anima_default`.

---

### OOO_Anima preset overrides my custom quality value

**Symptom**: You typed custom quality tags into the `quality` field, but the assembled prompt (and live preview) shows the preset defaults instead of your text.

**Cause**: This is intentional. When `prefix_preset` is `ooo_anima_default`, `join_fields` (in `composer.py`) replaces the `quality`, `year`, and `rating` field values with the values from `data/anima_spec.json` before assembling the prompt. Your widget values are ignored for those three fields. This behavior is documented in the README under "Behavior."

**Fix**: To use your own quality and year values, change the `prefix_preset` COMBO from `ooo_anima_default` to `none` (or `custom`). Both `none` and `custom` pass all field values through exactly as typed.

**Verification**: Setting `prefix_preset` to `none` and re-checking the live preview shows your custom quality text in the assembled output.

---

### Negative preset does not override my custom field values

**Symptom**: You set `negative_preset` to `none` or `custom`, but the negative prompt output seems to be the model default rather than your fields.

**Cause**: Only `anima_base_default` and `ooo_anima_default` override fields. When `negative_preset` is `none` or `custom`, `join_negative_fields` in `composer.py` joins the six fields in canonical order using the field values exactly as supplied. If the output looks like a model default, it is likely that the field values themselves already contain those tokens (they are the widget defaults).

**Fix**: Verify that the six negative field widgets actually contain your intended values (not the factory defaults). Clear and retype each field as needed.

**Verification**: The `negative_prompt` STRING output wire carries your custom text, not the model default string.

---

## Performance issues

### Validation badge update feels slow while typing

**Symptom**: After typing into a field, the validation badges take a visible moment to update.

**Cause**: This is intentional. `validateRemote` in `composer.js` is debounced with a 400 ms delay. Every keystroke resets the timer; badges only update 400 ms after the last keystroke. This prevents a `POST /validate` request from being sent on every character press.

**Fix**: This is expected behavior, not a bug. If you want to see the current badge state immediately, stop typing for 400 ms. There is no configuration option to change the debounce interval without editing `composer.js`.

**Verification**: After pausing typing for 400 ms, badges update to reflect the current field contents.

---

### The palette tag grid renders slowly with many tags visible

**Symptom**: Switching palette tabs or clearing the search box causes a brief rendering pause.

**Cause**: The tag grid is rebuilt by DOM manipulation on every tab switch or search change. The full palette contains 509 tags across 30 categories. Rendering all of them simultaneously in a 4-column grid is generally fast in modern browsers; the bottleneck, when it occurs, is browser layout recalculation for large grids.

**Fix**:
1. Use the search box to reduce the number of rendered buttons — search filtering happens before rendering.
2. If the slowdown is severe, check whether the browser's hardware acceleration is enabled (about:settings → System → Use hardware acceleration when available in Chrome/Edge).
3. If the issue is reproducible and severe, file a bug report with browser version and the number of tags in the category that triggers the slowdown.

**Verification**: Typing a few characters in the search box reduces the grid to a small subset and the rendering delay should be absent.
