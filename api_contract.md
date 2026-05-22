# anima-prompt-helper — API Contract

All routes are registered on `PromptServer.instance.routes` (aiohttp `RouteTableDef`). URL prefix `/anima_prompt_helper/`.

---

## Route 1: GET /anima_prompt_helper/palette

**Purpose:** Serve the full tag palette dataset to the browser.

### Request
- Method: `GET`
- Path: `/anima_prompt_helper/palette`
- Body: none

### Preconditions
- `data/tag_palette.json` exists and is valid JSON.

### Response (200 OK)
```json
{
  "version": "1.0",
  "categories": [
    {
      "id": "quality",
      "label": "Quality",
      "tags": [
        { "tag": "masterpiece", "aliases": [], "count": 12000 }
      ]
    }
  ]
}
```

### Error responses

| Status | Body | Condition |
|--------|------|-----------|
| 503 | `{"error":"palette_not_found"}` | File missing |
| 500 | `{"error":"palette_parse_error"}` | Invalid JSON |

### Postconditions
- Cached in-memory after first read; invalidated only on server restart.

### Invariants
- Content-Type: `application/json`.
- Handler never modifies the file.

---

## Route 2: GET /anima_prompt_helper/spec

**Purpose:** Serve the Anima spec (canonical order, presets, validation params).

### Request
- Method: `GET`
- Path: `/anima_prompt_helper/spec`
- Body: none

### Preconditions
- `data/anima_spec.json` exists and is valid JSON.

### Response (200 OK)
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
      "recommended": { "sampler": "er_sde", "scheduler": "simple", "steps": 30, "cfg": 4.0, "resolution_range": [512, 1536] }
    },
    "ooo_anima": {
      "id": "ooo_anima",
      "label": "OOO_Anima v1.0",
      "default_prefix_quality": "masterpiece, best quality, high quality",
      "default_prefix_year": "newest, year 2025, year 2024",
      "default_rating": "safe",
      "default_extra": "game cg",
      "default_negative": "worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic",
      "recommended": { "sampler": "euler_ancestral", "scheduler": "simple", "steps": 35, "cfg": 4.5, "resolution_range": [512, 1920] }
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

### Error responses

| Status | Body | Condition |
|--------|------|-----------|
| 503 | `{"error":"spec_not_found"}` | File missing |
| 500 | `{"error":"spec_parse_error"}` | Invalid JSON |

### Postconditions
- Cached identically to palette.

---

## Route 3: POST /anima_prompt_helper/validate

**Purpose:** Run server-side validation rules on current field values.

### Request
- Method: `POST`
- Path: `/anima_prompt_helper/validate`
- Content-Type: `application/json`
- Body:
```json
{
  "fields": {
    "quality":          "masterpiece, best quality",
    "year":             "newest, year 2025",
    "rating":           "safe",
    "count":            "1girl",
    "character":        "hatsune miku",
    "series":           "vocaloid",
    "artist":           "@wlop, artist without at",
    "general":          "blue hair, cat_ears",
    "natural_language": "She is standing in a field."
  }
}
```

**Server-side enforcement:**
- Body must be JSON with top-level `"fields"` object.
- Each value must be a string (absent/null treated as `""`).
- Unknown keys ignored.

### Response (200 OK)
```json
{
  "issues": [
    {
      "field": "artist",
      "tag": "artist without at",
      "rule": "ARTIST_MISSING_AT",
      "severity": "error",
      "message": "Artist tag 'artist without at' must start with '@'"
    },
    {
      "field": "general",
      "tag": "cat_ears",
      "rule": "UNDERSCORE_TAG",
      "severity": "warning",
      "message": "Tag 'cat_ears' contains underscore; use 'cat ears' instead (exception: score_N)"
    }
  ],
  "assembled_length": 87
}
```

`issues[].field`: one of the 9 field names.
`issues[].tag`: the specific token that triggered the rule.
`issues[].rule`: one of `UPPERCASE_TAG`, `UNDERSCORE_TAG`, `ARTIST_MISSING_AT`, `INVALID_RATING`, `EMPTY_PROMPT`, `LONG_PROMPT`, `DUPLICATE_TAG`.
`issues[].severity`: `"error"` | `"warning"` | `"info"`.
`issues[].message`: human-readable.
`assembled_length`: integer >= 0.

### Error responses

| Status | Body | Condition |
|--------|------|-----------|
| 400 | `{"error":"invalid_request"}` | Malformed body |
| 500 | `{"error":"internal_error"}` | Unexpected exception |

### Postconditions
- Pure read-only computation. No side effects.
- `assembled_length` always present.

### Invariants
- Deterministic: identical input -> identical output.
- Content-Type: `application/json`.

---

## Route 4: GET /anima_prompt_helper/character_presets

**Purpose:** Serve the character preset list verbatim.

### Request
- Method: `GET`
- Path: `/anima_prompt_helper/character_presets`
- Body: none

### Preconditions
- `data/character_presets.json` exists and is valid JSON.

### Response (200 OK)
```json
{
  "version": "1.0",
  "presets": [
    { "id": "hatsune_miku", "label": "Hatsune Miku", "tags": "hatsune miku, vocaloid" }
  ]
}
```

### Error responses

| Status | Body | Condition |
|--------|------|-----------|
| 503 | `{"error":"character_presets_not_found"}` | File missing |
| 500 | `{"error":"character_presets_parse_error"}` | Invalid JSON |

### Postconditions
- Cached in-memory after first read; invalidated only on server restart.

### Invariants
- Content-Type: `application/json`.
- Handler never modifies the file.

---

## Route 5: GET /anima_prompt_helper/health

**Purpose:** Diagnostic endpoint for operators and the frontend to verify the extension is fully loaded and all data files are available. Useful for debugging startup issues without inspecting server logs.

### Request
- Method: `GET`
- Path: `/anima_prompt_helper/health`
- Body: none

### Preconditions
- None. The endpoint always responds regardless of extension state.

### Response (200 OK)
```json
{
  "status": "ok",
  "version": "0.2.0",
  "data_files": {
    "tag_palette.json":        {"exists": true,  "cached": true,  "size_bytes": 37075},
    "tag_palette_extras.json": {"exists": true,  "cached": false, "size_bytes": 21119},
    "anima_spec.json":         {"exists": true,  "cached": true,  "size_bytes": 3602},
    "character_presets.json":  {"exists": true,  "cached": false, "size_bytes": 20274},
    "i18n/ja.json":            {"exists": true,  "cached": false, "size_bytes": 19700}
  },
  "node_classes": [
    "AnimaPromptComposer",
    "AnimaPromptToConditioning",
    "AnimaNegativePromptComposer"
  ],
  "routes": [
    "/anima_prompt_helper/palette",
    "/anima_prompt_helper/spec",
    "/anima_prompt_helper/character_presets",
    "/anima_prompt_helper/validate",
    "/anima_prompt_helper/health"
  ]
}
```

`status`: `"ok"` if all expected data files exist on disk; `"degraded"` if any are missing or if `NODE_CLASS_MAPPINGS` cannot be imported.
`version`: string read from `pyproject.toml` at startup (lazy-loaded once, then cached); falls back to `"0.2.0"` if the file cannot be read.
`data_files[<path>].exists`: `true` if the file is present on disk.
`data_files[<path>].cached`: `true` if the route handler's in-memory cache for that file is currently populated.
`data_files[<path>].size_bytes`: file size in bytes if the file exists; `null` if it does not or on `OSError`.
`node_classes`: list of keys from `NODE_CLASS_MAPPINGS` in the root `__init__.py`; `["import_error"]` on failure.
`routes`: hardcoded list of all 5 registered routes.

### Error responses
None. The endpoint always returns HTTP 200 with a parseable JSON body.

### Postconditions
- Pure read-only. No caches are mutated, no files are written.

### Invariants
- Always HTTP 200. Never throws a 5xx response.
- Content-Type: `application/json`.
- Response time: < 10 ms on a warm cache; < 50 ms cold.

---

## Node: AnimaTagPalette (v0.4.0+)

**Python class:** `python.nodes.AnimaTagPalette`  
**ComfyUI key:** `AnimaTagPalette`  
**Display name:** `Anima Tag Palette`

### Inputs

| Name | Type | Notes |
|------|------|-------|
| `tags_buffer` | `STRING` (multiline) | Accumulates comma-separated tags from the panel UI. May be empty. |

### Outputs

| Name | Type | Notes |
|------|------|-------|
| `tags` | `STRING` | Returns `tags_buffer` verbatim. |

### Usage patterns

**Connection path:** Connect `tags` output → any `AnimaPromptComposer` field input (e.g. `general`). When connected, the Composer's widget for that field becomes a forceInput port and the AnimaTagPalette's `tags_buffer` value flows through directly.

**DOM injection path:** Leave `tags` unconnected. Use the in-panel "Composerへ挿入" button to write `tags_buffer` content into a same-graph Composer widget directly via DOM. The panel shows a Composer dropdown and a field dropdown; if the selected field's widget is absent (because it is connected), a warning is shown and the insertion is blocked.

### Invariants
- `passthrough` never mutates its input.
- Returns a 1-tuple `(str,)`.
- Raises `TypeError` if `tags_buffer` is not `str`.
