# anima-prompt-helper — Design Document

## Goal & Non-Goals

### Goals
- Decompose an Anima-model positive prompt into nine ordered category fields,
  concatenate them in canonical order, and output a STRING (and optionally CONDITIONING).
- Provide a rich in-node tag palette (tabs, search, click-to-add) sourced from
  `data/tag_palette.json` fetched via a backend API route.
- Give live preview of the assembled prompt and inline validation badges.
- Support round-trip workflow serialization: reopening a saved `.json` workflow
  restores every field value and palette state.

### Non-Goals
- Not a standalone web UI (no new browser tab / full-page admin panel).
- Not a negative-prompt helper (separate concern, out of scope for v1).
- Not responsible for building `tag_palette.json` or `anima_spec.json`
  (built by parallel workers; this extension only reads them).
- Not modifying ComfyUI core files.

---

## High-Level Architecture

```
+--------------------------- ComfyUI process ----------------------------+
|                                                                          |
|  +-------------------------------+   +------------------------------+  |
|  |      AnimaPromptComposer      |   |  AnimaPromptToConditioning   |  |
|  |  (Python node class)          |   |  (Python node class)         |  |
|  |  - join 9 fields in order     |   |  - STRING + CLIP -> COND     |  |
|  |  - validate, return STRING    |   |  - delegates to CLIPTextEnc  |  |
|  +-------------+-----------------+   +------------------------------+  |
|                | PromptServer.instance.routes                          |
|  +-------------+----------------------------------------------+        |
|  |                    api/routes.py                            |        |
|  |  GET  /anima_prompt_helper/palette                          |        |
|  |  GET  /anima_prompt_helper/spec                             |        |
|  |  POST /anima_prompt_helper/validate                         |        |
|  +-------------------------------------------------------------+        |
|                                                                          |
|  +--------------- web/ (WEB_DIRECTORY) ---------------------------+    |
|  |  extensions/anima_prompt_helper.js  (app.registerExtension)    |    |
|  |  +-----------------------------------------------------------+ |    |
|  |  |  beforeRegisterNodeDef("AnimaPromptComposer")            | |    |
|  |  |  -> injects DOM widgets onto the LiteGraph node:         | |    |
|  |  |    +-----------------------------------------------+     | |    |
|  |  |    |  Tab Strip: quality|year|rating|count|char|.. |     | |    |
|  |  |    |  Search box + filtered tag buttons grid       |     | |    |
|  |  |    |  Live preview textarea (read-only)            |     | |    |
|  |  |    |  Validation badge bar                         |     | |    |
|  |  |    +-----------------------------------------------+     | |    |
|  |  +-----------------------------------------------------------+ |    |
|  |  modules/palette.js    (tag data cache, render buttons)        |    |
|  |  modules/composer.js   (assemble / validate prompt)            |    |
|  |  modules/persist.js    (serialize/deserialize per-node state)  |    |
|  +----------------------------------------------------------------+    |
+--------------------------------------------------------------------------+

   data/tag_palette.json  <- built externally, read-only at runtime
   data/anima_spec.json   <- built externally, read-only at runtime
```

---

## Backend Python Module Layout

```
python/
  __init__.py          re-exports NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
  nodes.py             AnimaPromptComposer and AnimaPromptToConditioning classes
  composer.py          pure-function join_fields() and validate_fields()
  api/
    __init__.py        registers the three aiohttp routes via PromptServer.instance.routes
    routes.py          route handler coroutines; reads data files; calls validate
  validators.py        stateless rule functions (lower_case, underscore, at_prefix, ...)
```

### File responsibilities

| File | Responsibility |
|------|---------------|
| `__init__.py` (root) | Module entry point. Imports node classes; sets `WEB_DIRECTORY = "./web"`. Registers API routes (imports `python/api/__init__.py`). Exports `NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`. |
| `python/nodes.py` | Defines `AnimaPromptComposer` and `AnimaPromptToConditioning`. Declares `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, `CATEGORY`. Calls `composer.join_fields()`. |
| `python/composer.py` | `join_fields(fields: dict[str, str]) -> str` and `validate_fields(fields: dict[str, str]) -> list[ValidationIssue]`. Pure, no I/O. |
| `python/validators.py` | Individual rule functions: `check_lowercase`, `check_no_underscore`, `check_artist_at_prefix`, `check_rating_value`. Each returns a list of `ValidationIssue(field, tag, severity, message)`. |
| `python/api/__init__.py` | Calls `PromptServer.instance.routes` to attach the three routes. Lazy-loads data files once on first request. |
| `python/api/routes.py` | `get_palette(request)`, `get_spec(request)`, `post_validate(request)` async handlers. |

---

## Node Specs

### AnimaPromptComposer

**CATEGORY:** `"Anima"`

**INPUT_TYPES (required):**

| Name | Type | Config | Behavior |
|------|------|--------|----------|
| `quality` | `STRING` | `multiline=False, default="masterpiece, best quality, high quality"` | Prepended first. Free text. |
| `year` | `STRING` | `multiline=False, default="newest, year 2025, year 2024"` | After quality. |
| `rating` | `COMBO` | `options=["safe","sensitive","nsfw","explicit"], default="safe"` | Single value. |
| `count` | `STRING` | `multiline=False, default="1girl"` | e.g. `1girl`, `2boys`. |
| `character` | `STRING` | `multiline=True, default=""` | Character name tags. |
| `series` | `STRING` | `multiline=True, default=""` | Copyright / series. |
| `artist` | `STRING` | `multiline=True, default=""` | Each token MUST begin with `@`. |
| `general` | `STRING` | `multiline=True, default=""` | Free booru-style tags. |
| `natural_language` | `STRING` | `multiline=True, default=""` | Natural-language sentences appended last. |
| `prefix_preset` | `COMBO` | `options=["none","ooo_anima_default","custom"], default="ooo_anima_default"` | When set to `ooo_anima_default`, overrides `quality`/`year`/`rating` with OOO_Anima defaults. `custom` uses field values as-is. |

**RETURN_TYPES:** `("STRING",)`
**RETURN_NAMES:** `("positive_prompt",)`
**FUNCTION:** `"compose"`
**OUTPUT_NODE:** `False`

**Joining rules (compose method):**
1. If `prefix_preset == "ooo_anima_default"`, replace quality/year content with the OOO_Anima preset before joining (rating remains `safe`).
2. Collect fields in canonical order: `[quality, year, rating, count, character, series, artist, general]`.
3. Strip leading/trailing whitespace from each field value. Skip empty strings.
4. Split each field by comma; strip each token; drop empty tokens; rejoin with `", "`.
5. Join all non-empty field results with `", "`. Append `natural_language` (no splitting) after a `". "` separator when non-empty.
6. Return the assembled string.

**Preconditions:**
- All STRING inputs: `isinstance(v, str)` (ComfyUI guarantees this).
- `rating in {"safe","sensitive","nsfw","explicit"}` (COMBO enforces).
- `prefix_preset in {"none","ooo_anima_default","custom"}` (COMBO enforces).

**Postconditions:**
- Returns a 1-tuple `(str,)`. Never `None`; may be `""` if all fields empty.

**Invariants:**
- Field order in output is always: quality -> year -> rating -> count -> character -> series -> artist -> general -> natural_language.
- `artist` tokens that lack `@` prefix are NOT silently fixed; warning is logged.

**Error handling:**
- prefix_preset shadowing: silently overrides quality/year; logs INFO.
- Long prompts (> 3000 chars): pass through with `logging.warning`.

### AnimaPromptToConditioning

**Decision: Keep separate from AnimaPromptComposer.** Rationale: composability — STRING output is useful without a CLIP wire.

**CATEGORY:** `"Anima"`

**INPUT_TYPES:**

| Name | Type | Config |
|------|------|--------|
| `positive_prompt` | `STRING` | `forceInput=True` |
| `clip` | `CLIP` | required |

**RETURN_TYPES:** `("CONDITIONING", "STRING")`
**RETURN_NAMES:** `("conditioning", "positive_prompt")`
**FUNCTION:** `"encode"`

**Preconditions:**
- `clip is not None` — raises `RuntimeError("CLIP input is None")`.
- `positive_prompt` is `str`.

**Postconditions:**
- Returns `(conditioning, positive_prompt)` tuple.

---

## Frontend (web/) Extension Architecture

### Entry point

`web/extensions/anima_prompt_helper.js` — loaded via `WEB_DIRECTORY = "./web"`. Uses ES modules:
```js
import { app } from "/scripts/app.js";
```

### registerExtension hook

```js
app.registerExtension({
  name: "AnimaPromptHelper",
  async setup() { /* fetch palette + spec once; cache in module scope */ },
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name !== "AnimaPromptComposer") return;
    // override onNodeCreated to inject DOM panel
  }
});
```

### DOM widget injection

Inside `beforeRegisterNodeDef`, override `nodeType.prototype.onNodeCreated`:
1. `node.addDOMWidget("anima_palette_panel", "div", panelEl, { serialize: false })`.
2. `panelEl` contains: tab strip, search input, tag-button grid (scrollable), live-preview textarea, validation badge div.
3. Initial size `[680, 520]`.

Each category field is a standard STRING widget created by Python's `INPUT_TYPES`. JS reads/writes via `node.widgets.find(w => w.name === "quality")`.

### modules/palette.js

- Singleton `PaletteStore`. Fetches `/anima_prompt_helper/palette` once.
- `renderTabButtons(category, query, container)`.
- Tag button click -> `composer.addTagToField(node, category, tag)`.

### modules/composer.js

- `getFieldWidget(node, fieldName)`.
- `addTagToField(node, category, tag)` — dedup, rejoin, set `widget.value` and `widget.inputEl.value`, fire `input` event.
- `assemblePreview(node)` — mirrors Python join logic.
- `validatePreview(node)` — POST to `/validate`, debounced 400 ms; renders badges.

### modules/persist.js

- `serializeState(node)` -> `{ selectedTab, searchQuery }`.
- `restoreState(node, data)`.
- Hooked via `node.serialize` override and `node.onConfigure`.

### Event flow: tag button click

```
User clicks "cat ears"
  -> composer.addTagToField(node, "general", "cat ears")
    -> find widget "general"
    -> split current value by ","
    -> dedup (lowercase compare)
    -> push "cat ears", rejoin
    -> widget.value = newVal
    -> widget.inputEl.value = newVal
    -> dispatchEvent(new Event("input"))
  -> composer.assemblePreview(node) -> update preview
  -> debounced validatePreview(node) -> POST -> badges
```

### Why API routes instead of direct file reads

Browser `fetch()` cannot read arbitrary server files. WEB_DIRECTORY only serves `web/`. API routes bridge `data/` to the browser and allow future server-side processing.

---

## State Persistence

| Key | Type | Serialized | Restored |
|-----|------|-----------|---------|
| 9 field widget values + `prefix_preset` | `string` | Yes (ComfyUI `widgets_values`) | Yes |
| `anima_state.selectedTab` | `string` | Yes (node.serialize override) | Yes |
| `anima_state.searchQuery` | `string` | Yes | Yes |
| Palette HTML / rendered buttons | DOM | No | Reconstructed from palette data |

---

## Data File Contracts

### data/tag_palette.json

```json
{
  "version": "1.0",
  "categories": [
    {
      "id": "quality",
      "label": "Quality",
      "tags": [
        { "tag": "masterpiece", "aliases": [], "count": 12000 },
        { "tag": "best quality", "aliases": ["best_quality"], "count": 9800 }
      ]
    }
  ]
}
```

Rules:
- All tags lowercase.
- Spaces (not underscores), except `score_N`.
- Artist tags MUST have `@` prefix in the `tag` field.
- `count` is informational sort hint (0 if unknown).
- `aliases` used for search matching only.

### data/anima_spec.json

```json
{
  "version": "1.0",
  "canonical_order": ["quality","year","rating","count","character","series","artist","general","natural_language"],
  "model_presets": {
    "anima_base": {
      "id": "anima_base",
      "label": "Anima Base v1.0",
      "default_prefix_quality": "masterpiece, best quality, score_7",
      "default_prefix_year": "",
      "default_rating": "safe",
      "default_extra": "",
      "default_negative": "worst quality, low quality, score_1, score_2, score_3, artist name",
      "recommended": { "sampler": "er_sde", "scheduler": "simple", "steps": 30, "cfg": 4.0 }
    },
    "ooo_anima": {
      "id": "ooo_anima",
      "label": "OOO_Anima v1.0",
      "default_prefix_quality": "masterpiece, best quality, high quality",
      "default_prefix_year": "newest, year 2025, year 2024",
      "default_rating": "safe",
      "default_extra": "game cg",
      "default_negative": "worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic",
      "recommended": { "sampler": "euler_ancestral", "scheduler": "simple", "steps": 35, "cfg": 4.5 }
    }
  },
  "validation_rules": {
    "artist_at_required": true,
    "lowercase_required": true,
    "underscore_forbidden_except": ["score_\\d+", "score_\\d+_up"],
    "rating_allowed_values": ["safe","sensitive","nsfw","explicit"]
  }
}
```

---

## Validation Rules

| Rule ID | Trigger | Severity |
|---------|---------|---------|
| `UPPERCASE_TAG` | Token has uppercase letter (in non-NL fields) | WARNING |
| `UNDERSCORE_TAG` | Contains `_` and not in exempt list (`score_N`, `score_N_up`) | WARNING |
| `ARTIST_MISSING_AT` | Token in `artist` not starting with `@` | ERROR |
| `INVALID_RATING` | rating not in {safe,sensitive,nsfw,explicit} | ERROR |
| `EMPTY_PROMPT` | Assembled is empty | INFO |
| `LONG_PROMPT` | > 3000 chars | WARNING |
| `DUPLICATE_TAG` | Same normalized tag in 2+ fields | WARNING |

Normalization for duplicate check: lowercase, collapse spaces, strip.

---

## Error & Edge Cases

| Case | Handling |
|------|---------|
| `data/tag_palette.json` missing | 503 with `{"error":"palette_not_found"}`. Frontend shows banner. |
| `data/anima_spec.json` missing | 503 on `/spec`. Frontend falls back to hardcoded order. |
| CLIP missing on Conditioning node | `RuntimeError`. Red node. |
| All fields empty | Returns `("",)`. INFO issue. |
| Long prompt | Pass through + warning. |
| Duplicate across fields | WARNING, not blocking. |
| Workflow without `anima_state` | Defaults to first tab, empty query. |

---

## Open Questions / Risks

1. **Tag palette size**: Lazy per-category fetching if > 5 MB.
2. **Artist `@` enforcement**: Currently warn-only; auto-fix?
3. **OOO_Anima `game cg`**: Always or toggle?
4. **`score_N_up` exception**: Currently exempted.
5. **Frontend framework**: Plain DOM + fetch for now; reconsider if virtual scroll needed.
