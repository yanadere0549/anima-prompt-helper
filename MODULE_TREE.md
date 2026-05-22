# anima-prompt-helper — Module Tree

```
anima-prompt-helper/
├── __init__.py                  Extension entry point: re-exports NODE_CLASS_MAPPINGS,
│                                NODE_DISPLAY_NAME_MAPPINGS, WEB_DIRECTORY = "./web";
│                                triggers API route registration.
│
├── python/
│   ├── __init__.py              Re-exports from nodes.py; imported by root __init__.py.
│   ├── nodes.py                 AnimaPromptComposer and AnimaPromptToConditioning
│   │                            node class definitions.
│   ├── composer.py              Pure functions: join_fields(), validate_fields().
│   │                            No I/O; fully unit-testable.
│   ├── validators.py            Individual validation rule functions returning
│   │                            ValidationIssue namedtuples.
│   └── api/
│       ├── __init__.py          Attaches the three aiohttp route handlers to
│       │                        PromptServer.instance.routes at import time.
│       └── routes.py            Async route handlers: get_palette, get_spec,
│                                post_validate; lazy-loads JSON data files.
│
├── web/
│   ├── extensions/
│   │   └── anima_prompt_helper.js   Main extension file loaded by ComfyUI's
│   │                                extension loader (app.registerExtension).
│   │                                Orchestrates palette, composer, persist modules.
│   ├── modules/
│   │   ├── palette.js           PaletteStore singleton; fetches and caches tag data;
│   │   │                        renders tab buttons.
│   │   ├── composer.js          JS-side field join logic and preview assembly;
│   │   │                        addTagToField(), assemblePreview(), validatePreview().
│   │   └── persist.js           Per-node state serialization helpers (selectedTab,
│   │                            searchQuery) via node.serialize / node.onConfigure.
│   └── styles/
│       └── anima_prompt_helper.css  Panel styles (tab strip, search box, tag buttons,
│                                    preview area, badge bar).
│
├── data/
│   ├── tag_palette.json         Tag data by category (built by parallel worker).
│   └── anima_spec.json          Canonical order, presets, validation rule params
│                                (built by parallel worker).
│
├── tests/
│   ├── test_composer.py         Unit tests for join_fields() and validate_fields().
│   ├── test_validators.py       Unit tests for each individual validation rule.
│   └── test_routes.py           Integration tests for the three API route handlers
│                                (uses aiohttp test client; mocks data file reads).
│
├── pyproject.toml               Optional packaging metadata (name, version, deps).
├── README.md                    Install / usage / screenshot.
├── DESIGN.md                    Architecture document (this design).
├── MODULE_TREE.md               This file.
└── api_contract.md              HTTP route contract.
```
