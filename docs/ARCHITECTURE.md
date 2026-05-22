# anima-prompt-helper — Architecture Diagrams

Visual reference for contributors. All diagrams are Mermaid-formatted and
render natively in GitHub's markdown viewer. Cross-references use relative
paths (e.g. `../DESIGN.md`, `../api_contract.md`).

See also: [`../DESIGN.md`](../DESIGN.md) · [`../api_contract.md`](../api_contract.md) · [`../MODULE_TREE.md`](../MODULE_TREE.md)

---

## Diagram 1: System Overview

Top-level map of the entire extension. Shows how Python nodes, API routes,
JavaScript modules, and data files are wired together inside the ComfyUI
process.

```mermaid
graph TD
    subgraph ComfyUI["ComfyUI Process"]
        subgraph Nodes["Python Nodes (python/nodes.py)"]
            APC["AnimaPromptComposer"]
            ATC["AnimaPromptToConditioning"]
            ANC["AnimaNegativePromptComposer"]
        end

        subgraph API["API Layer (python/api/)"]
            R1["GET /palette"]
            R2["GET /spec"]
            R3["GET /character_presets"]
            R4["POST /validate"]
        end

        subgraph PY["Python Logic"]
            COMP["composer.py\njoin_fields()"]
            VALI["validators.py\nvalidate_fields()"]
        end

        subgraph Data["data/"]
            TP["tag_palette.json"]
            TE["tag_palette_extras.json"]
            AS["anima_spec.json"]
            CP["character_presets.json"]
            I18N["i18n/ja.json"]
        end

        subgraph Web["web/ (WEB_DIRECTORY)"]
            EXT["anima_prompt_helper.js\n(registerExtension)"]
            subgraph Modules["modules/"]
                PAL["palette.js\nPaletteStore"]
                COM["composer.js\nassemblePreview"]
                NCOM["negative_composer.js"]
                PAN["panel.js\ninjectPalettePanel"]
                NPAN["negative_panel.js"]
                CPRE["character_presets.js\nCharacterPresetStore"]
                PER["persist.js\nattachPersistence"]
            end
        end
    end

    APC --> COMP
    ANC --> COMP
    ATC --> APC

    R1 --> TP
    R1 --> TE
    R2 --> AS
    R3 --> CP
    R4 --> COMP
    R4 --> VALI

    EXT --> PAN
    EXT --> NPAN
    EXT --> PAL
    EXT --> PER
    EXT --> CPRE

    PAL -- "GET /palette" --> R1
    COM -- "GET /spec" --> R2
    CPRE -- "GET /character_presets" --> R3
    COM -- "POST /validate" --> R4
```

---

## Diagram 2: Tag Palette Click Flow

Runtime sequence when a user clicks a tag button in the palette panel. Shows
the full event chain including the 400 ms debounce before remote validation.

```mermaid
sequenceDiagram
    actor User
    participant TB as TagButton (DOM)
    participant COM as composer.js
    participant W as Widget (LiteGraph)
    participant PV as Preview Textarea
    participant API as POST /validate
    participant BB as Badge Bar

    User->>TB: click "cat ears"
    TB->>COM: addTagToField(node, fieldName, tag)
    COM->>W: read widget.value
    COM->>COM: split / dedup / push tag
    COM->>W: widget.value = newVal
    COM->>W: dispatchEvent(input)
    W->>PV: panel.refreshPreview()
    PV->>COM: assemblePreview(node, spec)
    COM-->>PV: assembled string
    Note over COM,API: 400 ms debounce
    COM->>API: validateRemote(fields, callback)
    API-->>COM: {issues, assembled_length}
    COM->>BB: renderBadges(result)
```

---

## Diagram 3: Character Preset Apply Flow

Sequence when a user selects an entry from the character preset dropdown.
Shows how the preset data populates multiple field widgets and triggers a
preview refresh.

```mermaid
sequenceDiagram
    actor User
    participant DD as Dropdown (select)
    participant CPS as CharacterPresetStore
    participant AP as applyPreset()
    participant W as Node Widgets
    participant PV as Preview Textarea
    participant VR as validateRemote

    User->>DD: select preset label
    DD->>CPS: getById(selectedId)
    CPS-->>DD: preset object
    DD->>AP: applyPreset(node, preset, onRefresh)
    AP->>W: _setField(node, "character", preset.character)
    AP->>W: _setField(node, "series", preset.series)
    AP->>W: addTagToField(node, "general", tag) x N
    AP->>W: addTagToField(node, "artist", artist) x N
    AP->>AP: animaUiState.lastPresetId = preset.id
    AP->>PV: onRefresh() -> refreshPreview()
    PV-->>PV: assemblePreview updated
    AP->>VR: scheduleValidation()
    Note over AP,VR: 400 ms debounce
```

---

## Diagram 4: Backend Compose Logic

Internal control flow of `join_fields()` in `composer.py`. Illustrates how
the `prefix_preset` parameter branches the assembly path before fields are
tokenized and joined.

```mermaid
flowchart TD
    A([join_fields called]) --> B{prefix_preset?}

    B -- ooo_anima_default --> C[Load OOO_Anima defaults\nfrom anima_spec.json]
    C --> D[Shadow quality / year / rating\nwith preset values]
    D --> E[Set extra_prefix = default_extra\ne.g. 'game cg']
    E --> F

    B -- none / custom --> F[Use effective field values as-is]

    F --> G[Iterate CANONICAL_ORDER\nexcl. natural_language]
    G --> H[Strip + tokenize each field\nskip empty fields]
    H --> I{field == rating\nAND extra_prefix set?}
    I -- yes --> J[Append extra_prefix token\nafter rating part]
    J --> K
    I -- no --> K[Continue to next field]
    K --> G
    G --> L[Join all parts with ', ']
    L --> M{natural_language\nnon-empty?}
    M -- yes --> N[Append '. ' + natural_language]
    M -- no --> O([Return STRING])
    N --> O
```

---

## Diagram 5: Validation Pipeline

Control flow through the POST `/validate` route and all seven rule checks.
Each check is independent; results are collected and returned as a single
issues array.

```mermaid
flowchart TD
    A([POST /validate]) --> B[Parse JSON body]
    B --> C{body valid?}
    C -- no --> ERR400([400 invalid_request])
    C -- yes --> D[validators.validate_fields]

    D --> E[join_fields to get assembled]
    E --> F[Run rule checks]

    F --> R1[check_lowercase\nUPPERCASE_TAG]
    F --> R2[check_underscore\nUNDERSCORE_TAG]
    F --> R3[check_artist_at\nARTIST_MISSING_AT]
    F --> R4[check_rating\nINVALID_RATING]
    F --> R5[check_empty\nEMPTY_PROMPT]
    F --> R6[check_long\nLONG_PROMPT]
    F --> R7[check_duplicate\nDUPLICATE_TAG]

    R1 --> COL[Collect all issues]
    R2 --> COL
    R3 --> COL
    R4 --> COL
    R5 --> COL
    R6 --> COL
    R7 --> COL

    COL --> RES([Return JSON\nissues + assembled_length])
```

---

## Diagram 6: Module Dependency Graph

Static import relationships across all Python and JavaScript modules. Use
this diagram to trace where a change in one file may require updates
elsewhere.

```mermaid
graph LR
    subgraph PySide["Python"]
        RINIT["__init__.py\n(root)"]
        PINIT["python/__init__.py"]
        NODES["python/nodes.py"]
        COMPY["python/composer.py"]
        VALID["python/validators.py"]
        AINIT["python/api/__init__.py"]
        ROUTE["python/api/routes.py"]
        DSPEC["data/anima_spec.json"]
        DPAL["data/tag_palette.json"]
        DCP["data/character_presets.json"]
    end

    subgraph JSSide["JavaScript"]
        MAIN["anima_prompt_helper.js"]
        PAL["palette.js"]
        COMJS["composer.js"]
        NCOM["negative_composer.js"]
        PAN["panel.js"]
        NPAN["negative_panel.js"]
        CPRE["character_presets.js"]
        PER["persist.js"]
    end

    RINIT --> PINIT
    RINIT --> AINIT
    PINIT --> NODES
    NODES --> COMPY
    COMPY --> VALID
    COMPY --> DSPEC
    ROUTE --> COMPY
    ROUTE --> VALID
    ROUTE --> DPAL
    ROUTE --> DCP
    AINIT --> ROUTE

    MAIN --> PAN
    MAIN --> NPAN
    MAIN --> PAL
    MAIN --> CPRE
    MAIN --> PER
    PAN --> COMJS
    PAN --> PAL
    PAN --> PER
    PAN --> CPRE
    NPAN --> NCOM
    NPAN --> PAL
    NPAN --> PER
    CPRE --> COMJS
```

---

## Diagram 7: State Persistence

Sequence covering a full save-and-reload cycle of a ComfyUI workflow. Shows
how `anima_state` is injected into the serialized node JSON and then restored
when the workflow is reopened.

```mermaid
sequenceDiagram
    participant UI as ComfyUI App
    participant NODE as LiteGraph Node
    participant PER as persist.js
    participant WF as Workflow JSON

    Note over UI,WF: Save workflow
    UI->>NODE: node.serialize()
    NODE->>PER: wrapped serialize hook
    PER->>PER: read animaUiState\n(selectedTab, searchQuery, lastPresetId)
    PER-->>NODE: data.properties.anima_state = state
    NODE-->>UI: serialized node data
    UI->>WF: write to .json file\n(widgets_values + anima_state)

    Note over UI,WF: Load workflow
    UI->>WF: read .json file
    WF-->>UI: node data
    UI->>NODE: node.onConfigure(data)
    NODE->>PER: wrapped onConfigure hook
    PER->>PER: restore animaUiState\nfrom data.properties.anima_state
    PER-->>NODE: animaUiState updated
    NODE->>UI: panel._aphInitPanel()
    UI-->>UI: re-render with restored\ntab, query, lastPresetId
```

---

## Diagram 8: HTTP Routes

All four routes served by `python/api/routes.py`, the data sources each
reads, and the shape of the response returned to the browser.

```mermaid
graph LR
    BR([Browser])

    BR -- GET --> R1["GET /palette"]
    BR -- GET --> R2["GET /spec"]
    BR -- GET --> R3["GET /character_presets"]
    BR -- POST fields --> R4["POST /validate"]

    R1 --> TP[("tag_palette.json")]
    R1 --> TE[("tag_palette_extras.json")]
    R1 --> RS1["{version, categories\n[{id,label,tags}]}"]

    R2 --> AS[("anima_spec.json")]
    R2 --> RS2["{version,\ncanonical_order,\nmodel_presets,\nvalidation_rules}"]

    R3 --> CP[("character_presets.json")]
    R3 --> RS3["{version, presets\n[{id,label,character,\nseries,...}]}"]

    R4 --> COMP["composer.py\n+ validators.py"]
    R4 --> RS4["{issues[],\nassembled_length}"]
```

---

## Reading Guide

| Diagram | Purpose |
|---------|---------|
| **1 — System Overview** | Top-level map; start here to orient yourself |
| **2 — Tag Click Flow** | Runtime sequence when a user adds a tag |
| **3 — Character Preset Flow** | Runtime sequence when a preset is applied |
| **7 — State Persistence** | Runtime sequence for save/load round-trip |
| **4 — Compose Logic** | Internal Python assembly logic (`composer.py`) |
| **5 — Validation Pipeline** | Internal Python validation logic (`validators.py`) |
| **6 — Module Dependencies** | Static import graph; use for refactoring impact analysis |
| **8 — HTTP Routes** | Route-to-data-file mapping and response shapes |

**How the diagrams relate:**
Diagram 1 is the top-level map of the whole system.
Diagrams 2, 3, and 7 are runtime event flows — read them when tracing a
specific user action through the code.
Diagrams 4 and 5 drill into backend Python logic that has no JS equivalent.
Diagrams 6 and 8 are static structural references useful during refactoring
or when adding a new module or route.
