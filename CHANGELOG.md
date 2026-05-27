# Changelog

## [Unreleased]

### Added
- **AnimaArtistRandomizer node** — picks `count` random artist tags from a locally-saved pool and outputs them as an insert-ready STRING (`artist_tags`), wireable into an `AnimaPromptComposer` `artist` input.
  - **Seed-reproducible** selection (`seed` widget with `control_after_generate`). Pair with ComfyUI's batch count to run "j times" and get j different artist sets per queue.
  - Falls back to the **built-in high-score pool** when the pool is empty, so a freshly-dropped node works immediately.
  - **Chosen artists are embedded in image metadata** — a serialized `picked` widget is populated at queue time (via an `app.graphToPrompt` hook, per batch iteration, using a deterministic seeded RNG) so the actual artists land in the saved PNG's workflow / prompt. Python returns `picked` verbatim when present; headless / API callers fall back to the seeded Python selection. Panel 🎲 試し引き now previews the exact seed-based pick.
  - `web/modules/artist_pools.js`: `parsePoolString` / `seededPickArtists` (mulberry32) shared by the panel preview and queue-time population. `artist_randomizer_panel.js`: exported `populateArtistRandomizers(graph)`.
- **Built-in high-score pool** `data/artist_pool_default.json` — 3,195 artist tags with animadex.net quality `score >= 0.5`, mapped to canonical Anima tags via `data/anima/search.json`. Regenerable with `scripts/fetch_artist_pool.py`.
- **Locally-saved artist pools** — `GET /anima_prompt_helper/artist_pools` (builtin + user), `POST /anima_prompt_helper/user_artist_pools`, `DELETE /anima_prompt_helper/user_artist_pools/{id}`; stored in `data/user_artist_pools.json` (gitignored).
- **Artist randomizer panel** (`web/modules/artist_randomizer_panel.js`) — pool source dropdown (load / 💾 save / 🗑 delete), autocomplete artist add (reuses the artist suggest index), removable chip list, 🎲 試し引き preview, and 「artist欄へ挿入」 into a same-graph composer.
- `python/artist_pool.py`: `parse_pool` / `pick_artists` (seeded, no-replacement) / `load_default_pool` / `join_artists`.
- `web/modules/artist_pools.js`: `ArtistPoolStore` singleton + `fetchArtistPools`. `web/modules/artist_suggest.js`: exported `searchArtists` / `formatCount` for reuse.
- 30 new tests (`tests/test_artist_randomizer.py`, `tests/test_api_artist_pools.py`).

- **Prompt Importer recognises randomizer artists** — `python/metadata_extractor.py` now reads `AnimaArtistRandomizer`'s `picked` value (the composer's `artist` field is a link, so the literal artists live on the randomizer) and merges it into `anima_fields["artist"]` + the positive text, both in the `prompt` and `workflow` extraction paths. Dropping such an image into the Prompt Importer now surfaces the artists in the "Artist / 絵師" bucket.

### Fixed
- `tests/test_api_health.py`: synced the stale `_EXPECTED_ROUTES` / `_EXPECTED_NODE_CLASSES` / `_EXPECTED_FILES` lists with the current routes and node classes (the routes assertion had drifted out of sync).

## [0.5.0] - 2026-05-22

### Added
- **Hierarchical tag UI on AnimaTagPalette** modeled after [sdweb-easy-prompt-selector](https://github.com/blue-pen5805/sdweb-easy-prompt-selector):
  - **Subcategory dropdown** below the tab strip — drills into subgroups within a category (e.g. Hair Color → warm / cool / dark / multi).
  - **Random tag button (🎲)** with tier-weighted selection (tier 5 → 5× weight; uniform fallback).
  - **Weight adjustment** with hover `+` / `−` buttons on each tag chip; writes `(tag:weight)` syntax to the target Composer field. Weight clamped to [0.1, 2.0], rounded to 2 decimals.
  - **Favorites tab (★)** — toggle the star on any tag to add/remove from favorites; persisted per-node in `anima_state.favorites`.
  - **History tab (🕒)** — last 50 tags used (newest first); persisted per-node in `anima_state.history`.
  - **Right-click to remove** — right-click on any tag chip deletes that tag from the target field (matches both `(tag:weight)` and bare forms).
- `data/tag_palette.json` / `tag_palette_extras.json` schema **v1.1**: every tag now has a required `subcategory` field. 509 tags grouped into natural subcategories per category.
- `python/validators.py`: `_strip_weight()` helper + updated `check_lowercase` / `check_underscore` to treat `(tag:N.N)` syntax as opaque — only the bare tag inside is validated.
- `web/modules/palette.js`: `getSubcategories(catId)`, `getRandomTag(catId, subcatId?, useTierWeight=true)`, third `subcategoryId` argument on `getTagsFiltered` and `renderTagButtons`. `btn.dataset.tag` exposed.
- `web/modules/persist.js`: `favorites: string[]`, `history: string[]`, `selectedSubcategory: string|null` fields in `anima_state` + accessors: `getFavorites` / `toggleFavorite` / `isFavorite` / `getHistory` / `addToHistory` / `clearHistory` / `getSelectedSubcategory` / `setSelectedSubcategory`.
- `web/modules/composer.js`: `parseWeightedTag` / `formatWeightedTag` / `adjustTagWeight` / `removeTagFromField` helpers. `addTagToField` / `toggleTagInField` now match against the bare tag (weight-aware dedup).
- AnimaTagPalette panel structure: header → preset dropdown → composer/field/insert controls → warn label → tab strip (30 tabs + 2 special tabs) → subcategory row → search → tag grid.
- 8 new tests in `tests/test_validators.py` covering `_strip_weight` and the weighted-token branches of `check_lowercase` / `check_underscore`.

### Changed
- `COMPOSER_ONLY_TABS = []` (was `["quality", "year", "rating", "count"]`) — all 30 categories now live on AnimaTagPalette. AnimaPromptComposer node no longer renders a palette panel.
- AnimaPromptComposer's character preset dropdown moved to the AnimaTagPalette panel's top row; preset application requires selecting a target Composer first (multi-Composer graphs supported).
- `data/tag_palette.json` / `tag_palette_extras.json` version bumped to `1.1`.
- `scripts/check_data_integrity.py` accepts both `"1.0"` and `"1.1"` palette versions.

### Removed
- `web/modules/panel.js` — fully deleted (panel injection for AnimaPromptComposer removed from `web/extensions/anima_prompt_helper.js`).
- `web/modules/composer.js`: `validateRemote`, `collectFields`, `_validateTimer`, internal `debounce`. `assemblePreview` / `FALLBACK_CANONICAL_ORDER` / `tokenize` kept (used by `scripts/run_js_compose.mjs` for `tests/test_parity.py`).
- AnimaPromptComposer panel preview textarea + validation badge bar UI (the POST `/anima_prompt_helper/validate` route is retained for external consumers but the panel no longer surfaces it).

### Fixed
- Tag dedup now handles `(tag:weight)` correctly: adding `blonde hair` while `(blonde hair:1.2)` is present is a no-op (was: appended a duplicate).

### Tests
- **146 passed, 1 skipped** (was 138 passed before v0.5.0; +8 new tests for weighted-tag validation).

## 0.4.0 — 2026-05-21

- Panel overflow fixes: `web/styles/anima_prompt_helper.css` adds `min-width: 0` and `max-width: 100%` to `.aph-panel`, `.aph-tab-strip`, `.aph-tag-grid`, `.aph-tag-btn`, `.aph-preview` so flex/grid items can shrink and tab/tag content no longer escapes the node bounds.
- Panel auto-resize: `panel.js` and `negative_panel.js` assign `computeSize` directly on the widget returned by `addDOMWidget` (some ComfyUI builds ignore `options.computeSize`), perform an initial `requestAnimationFrame` size sync, and run a `ResizeObserver` with a `_resizing`/`requestAnimationFrame` reentry guard plus 8 px hysteresis to track panel content height without entering a layout feedback loop.
- AnimaTagPalette satellite node: new `AnimaTagPalette` node (passthrough STRING) hosts the 26 category tabs from `hair_color` (order=50) downward, keeping the AnimaPromptComposer panel scoped to the four "always-needed" tabs (`quality`, `year`, `rating`, `count`). New `web/modules/category_target_map.js` declares `COMPOSER_ONLY_TABS` and a category→target-field map so tag clicks resolve to the correct composer widget (this also fixes a previous bug where `currentCategoryId` was used directly as a widget name, silently failing for categories like `hair_color`).
- AnimaTagPalette panel UX: in-panel "対象 Composer" dropdown enumerates same-graph `AnimaPromptComposer` nodes, "挿入先フィールド" dropdown auto-updates on tab switch via `CATEGORY_DEFAULT_TARGET`, tag clicks write to the node's own `tags_buffer` widget and (when configured) also DOM-inject into the chosen composer's widget. The "Composerへ挿入" button batch-writes the buffer into the chosen field. Both paths refuse to write when the target field's input port already has an incoming link (the runtime value comes from the link, so widget writes would be discarded) and surface a warning instead.
- `tags_buffer` is now an internal-only state widget: declared with `multiline=False` in `python/nodes.py` so LiteGraph reserves only a single-line row, and the panel JS additionally sets `computeSize=[0,-4]`, `hidden=true`, and `display: none` on any rendered text input. This stops the node from growing taller as tags accumulate. The value is still exposed through the `tags` STRING output for node-link delivery.
- AnimaTagPalette panel shrink loop fix: `.aph-tab-strip` now has `flex-shrink: 0` and `min-height: 32px`, `.aph-tag-grid` has `min-height: 140px`, and `tag_palette_panel.js` clamps both `computeSize` and the ResizeObserver target to a `MIN_PANEL_HEIGHT` of 360 px. Previously the tab row collapsed to ~2 px and the tag grid to ~4 px after `tags_buffer` was hidden, because a momentarily small `panelEl.scrollHeight` fed back into `computeSize`, ComfyUI assigned a smaller widget row, the flex-column children shrank further, and the loop reinforced itself until tags became unclickable.
- Tag click is now a toggle: clicking a tag button removes the tag if it is already present in the target field (case-insensitive), otherwise appends it. New `toggleTagInField(node, field, tag)` helper in `composer.js` returns `"added"`/`"removed"`/`"noop"`. `panel.js` and `tag_palette_panel.js` both use the toggle path for the direct-click flow; `tag_palette_panel.js` also toggles the `tags_buffer` value to keep buffer and Composer field in sync. The "Composerへ挿入" button keeps its additive (dedup-on-add) behaviour because it is meant as a bulk commit of the buffer's contents.
- Dual delivery paths: connect `AnimaTagPalette.tags` → `AnimaPromptComposer.<field>` to forward `tags_buffer` through the node graph at execution time, or leave it unconnected and use the in-panel insert button for ad-hoc DOM injection. Link presence is detected per-field so the two paths can coexist on the same composer without overwriting each other.
- LoRA trigger word insertion point: AnimaPromptComposer adds an optional `lora_trigger_words` (STRING) input. Trigger words are collected by other extensions/nodes and connected (or typed) into this slot as a comma-separated string; `python/composer.py` `join_fields()` accepts a `lora_trigger_words: list[str] | None` argument and emits them between the `general` tag block and the `natural_language` block. This package intentionally does not enumerate LoRA files or parse `civitai` metadata — that responsibility is left to dedicated LoRA helper extensions.
- DbC docstrings: `join_fields()`, `AnimaPromptComposer.compose()`, and `AnimaTagPalette.passthrough()` document the contract for the new parameters and outputs.
- Tests: `tests/test_composer.py` adds 11 cases covering the `lora_trigger_words` argument. `tests/test_nodes_tag_palette.py` adds 16 cases covering `AnimaTagPalette` INPUT_TYPES / RETURN_TYPES / passthrough and the empty-string boundary.

## 0.3.0 — 2026-05-21

- Health endpoint: `GET /anima_prompt_helper/health` returns diagnostic status (version, data-file presence, cache state, node class list); 5 tests in `tests/test_api_health.py`.
- Character presets endpoint: `GET /anima_prompt_helper/character_presets` serves `data/character_presets.json` with in-memory caching (registered in `python/api/routes.py`).
- Template auto-installer scripts: `scripts/install_templates.{ps1,sh,bat}` copy workflow JSONs into the ComfyUI workflow picker; covered by `tests/test_install_templates.py`.
- Pre-commit hooks configuration: `.pre-commit-config.yaml` added; usage guide in `docs/PRE_COMMIT.md`; config test in `scripts/test_precommit_config.py`.
- Accessibility improvements: `web/modules/panel.js` and `negative_panel.js` wire ARIA attributes (`aria-label`, `role`, `aria-live`) and keyboard event handlers throughout the panel UI.
- AnimaNegativePromptComposer node + panel: `python/nodes.py` defines `AnimaNegativePromptComposer`; `web/modules/negative_composer.js` and `negative_panel.js` provide the UI.
- Mermaid architecture diagrams: `docs/ARCHITECTURE.md` contains 8 mermaid diagram blocks covering system overview, data flow, node graph, API routes, and more.
- Packaging hardening: `pyproject.toml` has 8 keywords and 10 classifiers; `setup.cfg` added; `scripts/build_dist.{ps1,sh}` and `scripts/zip_release.{ps1,sh}` automate distribution builds.
- Badge contrast meets WCAG AA: `.aph-sev-error` (5.59:1), `.aph-sev-warning` (10.45:1), `.aph-sev-info` (8.30:1) all exceed the 4.5:1 threshold; ratios documented in CSS comments.
- Logo header in panel: `panel.js` and `negative_panel.js` both inject an `aph-header-icon` element at the top of the panel.
- Negative composer benchmark: `scripts/benchmark_composer.py` benchmarks `join_negative_fields` across 3 variants (none, ooo_anima_default, anima_base_default) with spread-check.

## 0.2.0 — 2026-05-21

- Character preset dropdown: 49 presets across Vocaloid, Re:Zero, Genshin Impact, Honkai: Star Rail, Frieren, Spy x Family, Chainsaw Man, Demon Slayer, Lycoris Recoil, SAO, Persona, Hololive, Touhou, Atelier Ryza, Idolmaster, and 3 generic archetypes; selecting fills character/series/general fields.
- Merged tag palette: `/palette` endpoint now returns 30 categories (18 base + 12 extras = 509 tags total) merged and sorted by order field.
- Japanese localization: `i18n/ja.json` with 509 tag display labels, UI labels, and validation messages translated; available for future and community integration.
- Workflow templates: `templates/OOO_Anima_simple.json` (10-node basic), `templates/OOO_Anima_standard.json` (11-node with negative + groups), `templates/OOO_Anima_highquality.json` (13-node two-pass hires).
- OOO_Anima preset parity: `game cg` is now correctly injected after the rating field in Python (Python/JS parity confirmed via `tests/test_parity.py`).
- Validation rules documented and covered: ARTIST_MISSING_AT, UNDERSCORE_TAG, UPPERCASE_TAG, INVALID_RATING, EMPTY_PROMPT, LONG_PROMPT, DUPLICATE_TAG.
- New HTTP route: GET `/anima_prompt_helper/character_presets` serving `data/character_presets.json` with in-memory caching.
- CI workflows: `.github/workflows/ci.yml` (runs on push/PR) and `release.yml` (version-tag releases).
- Local CI runner: `scripts/run_all_checks.ps1` / `.sh` / `.bat` executing py_compile, pytest, data integrity, JSON validation, and benchmarks.
- Benchmarks: `scripts/benchmark_composer.py`, `scripts/benchmark_palette_load.py`, `scripts/benchmark_validate_route.py` with baselines of ~4 µs (composer) and ~1 ms (validate route).
- Data integrity checker: `scripts/check_data_integrity.py` runs in CI to validate palette and spec JSON structure.
- SVG icon assets: `web/assets/icon.svg`, `logo.svg`, `icon-light.svg` added (not yet wired into the node UI).
- Distribution metadata: `pyproject.toml` enriched, `node_list.json` added for ComfyUI Manager, GitHub ISSUE and PR templates added.
- Added: `AnimaNegativePromptComposer` node with 6 ordered negative-prompt categories (`quality_negative`, `score_negative`, `style_negative`, `content_negative`, `meta_negative`, `extra_negative`) and per-model preset (`anima_base_default` / `ooo_anima_default`) that returns the model's canonical negative string from `data/anima_spec.json` directly.

## 0.1.0 — initial release

- AnimaPromptComposer node with 9 ordered fields
- AnimaPromptToConditioning node
- Tag palette UI with tabs, search, click-to-add
- Validation rules: artist @ prefix, lowercase, underscore, rating, duplicates
- Preset support: OOO_Anima default
- HTTP routes: /palette, /spec, /validate
