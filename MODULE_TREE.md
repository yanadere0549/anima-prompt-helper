# anima-prompt-helper — Module Tree

```
anima-prompt-helper/
├── __init__.py                  Extension entry point: re-exports NODE_CLASS_MAPPINGS,
│                                NODE_DISPLAY_NAME_MAPPINGS, WEB_DIRECTORY = "./web";
│                                triggers API route registration.
│
├── python/
│   ├── __init__.py              Re-exports from nodes.py; imported by root __init__.py.
│   ├── nodes.py                 AnimaPromptComposer, AnimaPromptToConditioning,
│   │                            AnimaNegativePromptComposer, AnimaTagPalette,
│   │                            AnimaArtistRandomizer, AnimaCharacterRandomizer,
│   │                            AnimaSituationRandomizer node class definitions.
│   ├── composer.py              Pure functions: join_fields(), validate_fields().
│   │                            No I/O; fully unit-testable.
│   ├── validators.py            Individual validation rule functions returning
│   │                            ValidationIssue namedtuples.
│   ├── artist_pool.py           parse_pool / pick_artists (seeded, no-replacement) /
│   │                            load_default_pool / join_artists.
│   ├── character_pool.py        parse_pool / pick_characters (seeded, no-replacement) /
│   │                            load_default_pool / join_characters.
│   ├── situation_pool.py        parse_pool / pick_situations (seeded, no-replacement) /
│   │                            load_default_pool / join_situations.
│   ├── metadata_extractor.py    Extracts Anima field values from PNG workflow/prompt
│   │                            metadata (used by AnimaPromptImporter); merges
│   │                            AnimaArtistRandomizer picked values into artist field.
│   └── api/
│       ├── __init__.py          Attaches all aiohttp route handlers to
│       │                        PromptServer.instance.routes at import time.
│       └── routes.py            Async route handlers: get_palette, get_spec,
│                                post_validate, get_character_presets, get_health,
│                                get_artist_pools, post/delete user_artist_pools,
│                                get_character_pools, post/delete user_character_pools,
│                                get_situation_pools, post/delete user_situation_pools;
│                                lazy-loads JSON data files.
│
├── web/
│   ├── extensions/
│   │   └── anima_prompt_helper.js   Main extension file loaded by ComfyUI's
│   │                                extension loader (app.registerExtension).
│   │                                Orchestrates palette, composer, persist modules.
│   ├── modules/
│   │   ├── palette.js               PaletteStore singleton; fetches and caches tag data;
│   │   │                            renders tab buttons.
│   │   ├── composer.js              JS-side field join logic and preview assembly;
│   │   │                            addTagToField(), assemblePreview(), validatePreview().
│   │   ├── persist.js               Per-node state serialization helpers (selectedTab,
│   │   │                            searchQuery) via node.serialize / node.onConfigure.
│   │   ├── artist_pools.js          ArtistPoolStore singleton + fetchArtistPools;
│   │   │                            parsePoolString / seededPickArtists (mulberry32).
│   │   ├── artist_randomizer_panel.js  Panel UI for AnimaArtistRandomizer;
│   │   │                            populateArtistRandomizers(graph).
│   │   ├── artist_suggest.js        searchArtists / formatCount for autocomplete reuse.
│   │   ├── character_pools.js       CharacterPoolStore singleton + fetchCharacterPools;
│   │   │                            seeded pick helpers for character tags.
│   │   ├── character_randomizer_panel.js  Panel UI for AnimaCharacterRandomizer;
│   │   │                            populateCharacterRandomizers(graph).
│   │   ├── situation_pools.js       SituationPoolStore singleton + fetchSituationPools;
│   │   │                            seeded pick helpers for situation tags.
│   │   └── situation_randomizer_panel.js  Panel UI for AnimaSituationRandomizer;
│   │                                populateSituationRandomizers(graph).
│   └── styles/
│       └── anima_prompt_helper.css  Panel styles (tab strip, search box, tag buttons,
│                                    preview area, badge bar).
│
├── data/
│   ├── tag_palette.json              Tag data by category (built by parallel worker).
│   ├── tag_palette_extras.json       Extra category tags merged at runtime.
│   ├── anima_spec.json               Canonical order, presets, validation rule params.
│   ├── character_presets.json        49 curated character preset entries.
│   ├── artist_pool_default.json      Built-in artist pool (3,195 tags, animadex.net
│   │                                 score >= 0.5). Regenerate: fetch_artist_pool.py.
│   ├── character_pool_default.json   Built-in character pool (~3,349 animadex.net
│   │                                 1girl character tags). Regenerate:
│   │                                 fetch_character_pool.py.
│   ├── situation_pool_default.json   Built-in situation pool (~293 Danbooru general
│   │                                 scene/situation tags). Regenerate:
│   │                                 fetch_situation_pool.py.
│   ├── user_artist_pools.json        Runtime-created; gitignored. Stores user-defined
│   │                                 artist pools.
│   ├── user_character_pools.json     Runtime-created; gitignored. Stores user-defined
│   │                                 character pools.
│   └── user_situation_pools.json     Runtime-created; gitignored. Stores user-defined
│                                     situation pools.
│
├── tests/
│   ├── test_composer.py              Unit tests for join_fields() and validate_fields().
│   ├── test_validators.py            Unit tests for each individual validation rule.
│   ├── test_routes.py                Integration tests for the core API route handlers
│   │                                 (uses aiohttp test client; mocks data file reads).
│   ├── test_api_health.py            Tests for GET /health (routes, node classes, files).
│   ├── test_nodes_tag_palette.py     Tests for AnimaTagPalette INPUT_TYPES/passthrough.
│   ├── test_parity.py                JS/Python prompt assembly parity tests.
│   ├── test_artist_randomizer.py     Unit tests for artist_pool.py pick logic.
│   ├── test_api_artist_pools.py      Integration tests for artist pool API routes.
│   ├── test_character_randomizer.py  Unit tests for character_pool.py pick logic.
│   ├── test_api_character_pools.py   Integration tests for character pool API routes.
│   ├── test_situation_randomizer.py  Unit tests for situation_pool.py pick logic.
│   └── test_api_situation_pools.py   Integration tests for situation pool API routes.
│
├── scripts/
│   ├── fetch_artist_pool.py          Fetches animadex.net artist data and rebuilds
│   │                                 data/artist_pool_default.json.
│   ├── fetch_character_pool.py       Fetches animadex.net 1girl character data and
│   │                                 rebuilds data/character_pool_default.json.
│   ├── fetch_situation_pool.py       Fetches Danbooru general tags and rebuilds
│   │                                 data/situation_pool_default.json.
│   ├── check_data_integrity.py       Validates palette and spec JSON structure (runs in CI).
│   ├── benchmark_composer.py         Benchmarks join_fields() and join_negative_fields().
│   ├── run_all_checks.ps1 / .sh      Run all local CI checks (py_compile, pytest,
│   │                                 data integrity, JSON validation, benchmarks).
│   └── install_templates.ps1 / .sh   Copy workflow JSON templates into the ComfyUI
│                                     workflow picker.
│
├── pyproject.toml               Optional packaging metadata (name, version, deps).
├── README.md                    Install / usage / screenshot.
├── DESIGN.md                    Architecture document (this design).
├── MODULE_TREE.md               This file.
└── api_contract.md              HTTP route contract.
```
