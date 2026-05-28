# anima-prompt-helper

Structured prompt composer for Anima / OOO_Anima models in ComfyUI.

<!-- TODO: insert screenshot of node here -->

## What it does

- Decomposes an Anima positive prompt into nine ordered category fields and concatenates them in canonical order.
- Enforces the field ordering that Anima models expect: quality → year → rating → count → character → series → artist → general → natural language.
- Provides a rich in-node tag palette with tabs, search, and click-to-add buttons sourced from a merged palette of 30 categories and 509 tags.
- Provides 49 character presets (Vocaloid, Re:Zero, Genshin Impact, Honkai: Star Rail, Frieren, Spy x Family, Chainsaw Man, Demon Slayer, Lycoris Recoil, SAO, Persona, Hololive, Touhou, Atelier Ryza, Idolmaster, and generic archetypes) that auto-fill the character, series, and general fields.
- Displays a live preview of the assembled prompt and inline validation badges without leaving the node.
- Runs seven validation rules in real time (ARTIST_MISSING_AT, UNDERSCORE_TAG, UPPERCASE_TAG, INVALID_RATING, EMPTY_PROMPT, LONG_PROMPT, DUPLICATE_TAG) to surface problems before you queue a generation.
- Supports round-trip workflow serialization: reopening a saved `.json` workflow restores every field value and palette state.

## Why

Anima and OOO_Anima models (by CircleStone Labs and oron1208) are trained on prompts that follow a specific tag ordering. Placing quality tokens before year tokens before rating tokens, and so on, produces noticeably better results than an arbitrary order. Writing prompts by hand in the correct order is tedious and error-prone — it is easy to forget the `@` prefix on artist names, accidentally use underscores where spaces are expected, or repeat a tag in multiple fields.

This extension makes it easy to compose prompts in the correct order by exposing each category as its own labeled input field on the ComfyUI node, providing a click-to-add tag palette organized by category, and running validation rules in real time so problems are surfaced before you queue a generation.

---

## Installation

1. Clone or copy the `anima-prompt-helper` folder into `ComfyUI/custom_nodes/`.

   <!-- TODO: replace the placeholder repository URL below with the actual GitHub URL once the project is published. -->

   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/anima-prompt-helper/anima-prompt-helper.git
   ```

2. Restart ComfyUI (or use the Manager's "Restart" button if you have ComfyUI-Manager installed).

3. (Optional) Verify the installation by opening the **Add Node** menu. Look for the category **Anima** — it should contain nodes including **Anima Prompt Composer**, **Anima Prompt -> Conditioning**, **Anima Negative Prompt Composer**, **Anima Artist Randomizer**, **Anima Character Randomizer**, and **Anima Situation Randomizer**.

### Install workflow templates (optional)

Three ready-to-use workflow JSON files ship with this extension. Run the installer to copy them into your ComfyUI workflow picker so they appear under their `anima-prompt-helper - ...` names without any manual dragging.

```powershell
# Windows PowerShell
.\scripts\install_templates.ps1
```

```bash
# Bash / WSL
bash scripts/install_templates.sh
```

Pass `-Force` / `--force` to overwrite previously installed copies, or `-DryRun` / `--dry-run` to preview what would be copied.

---

## Nodes provided

| Display name | Class name | Purpose | Output |
|---|---|---|---|
| Anima Prompt Composer | `AnimaPromptComposer` | Compose Anima-canonical positive prompts via 9 ordered fields. | `STRING (positive_prompt)` |
| Anima Tag Palette | `AnimaTagPalette` | Satellite node hosting the full 30-category tag palette with hierarchical UI. | `STRING (tags)` |
| Anima Prompt -> Conditioning | `AnimaPromptToConditioning` | Encode a composed prompt string into a CONDITIONING tensor using a CLIP model. | `CONDITIONING`, `STRING (positive_prompt)` |
| Anima Negative Prompt Composer | `AnimaNegativePromptComposer` | Compose a negative prompt from six structured categories with model-specific preset overrides. | `STRING (negative_prompt)` |
| Anima Artist Randomizer | `AnimaArtistRandomizer` | Pick N random artist tags from a saved pool (built-in or user-defined); wire into the `artist` field of AnimaPromptComposer. | `STRING (artist_tags)` |
| Anima Character Randomizer | `AnimaCharacterRandomizer` | Pick N random character tags from a saved pool (built-in ~3349 animadex.net 1girl entries); wire into the `character` field of AnimaPromptComposer. | `STRING (character_tags)` |
| Anima Situation Randomizer | `AnimaSituationRandomizer` | Pick N random situation/scene tags from a saved pool (built-in ~293 Danbooru general tags); wire into the `general` field of AnimaPromptComposer. | `STRING (situation_tags)` |

---

### Anima Prompt Composer

**Category:** `Anima`
**Display name:** `Anima Prompt Composer`

Accepts nine ordered fields and one preset selector. Joins the fields in canonical order and returns a single prompt string.

| Input field | Type | Default | Description |
|---|---|---|---|
| `quality` | STRING | `"masterpiece, best quality, high quality"` | Quality prefix tokens. Comma-separated. |
| `year` | STRING | `"newest, year 2025, year 2024"` | Year or era tokens. Comma-separated. |
| `rating` | COMBO | `safe` | One of: `safe`, `sensitive`, `nsfw`, `explicit`. |
| `count` | STRING | `"1girl"` | Subject count tag, e.g. `1girl`, `2boys`, `solo`. |
| `character` | STRING | `""` | Character name tags (multiline). |
| `series` | STRING | `""` | Copyright / series tags (multiline). |
| `artist` | STRING | `""` | Artist tokens — each MUST start with `@` (multiline). |
| `general` | STRING | `""` | Free booru-style tags (multiline). |
| `natural_language` | STRING | `""` | Natural-language sentences appended last without comma-splitting (multiline). |
| `prefix_preset` | COMBO | `ooo_anima_default` | `ooo_anima_default` overrides quality/year/rating with OOO_Anima defaults. `none` uses field values as-is. |

**Output:**

| Name | Type | Description |
|---|---|---|
| `positive_prompt` | STRING | Assembled prompt string in canonical field order. |

**Behavior:** When `prefix_preset` is `ooo_anima_default`, the `quality` and `year` field values are replaced with the OOO_Anima defaults before joining. The `rating` is reset to `safe` and `game cg` is injected after the rating field. Fields are joined with `", "`. The `natural_language` field is appended verbatim after a `". "` separator when non-empty.

---

### Anima Prompt -> Conditioning

**Category:** `Anima`
**Display name:** `Anima Prompt -> Conditioning`

Takes a prompt string and a CLIP model and returns a CONDITIONING tensor. This node is a thin wrapper over standard CLIP text encoding; it exists so that the STRING output from **Anima Prompt Composer** can be wired directly to a KSampler without an intermediate CLIPTextEncode node.

| Input | Type | Description |
|---|---|---|
| `positive_prompt` | STRING (forceInput) | Assembled prompt string, typically from Anima Prompt Composer. |
| `clip` | CLIP | CLIP model from a checkpoint loader. |

| Output | Type | Description |
|---|---|---|
| `conditioning` | CONDITIONING | Encoded conditioning tensor. |
| `positive_prompt` | STRING | Pass-through of the input string. |

**Note:** If `clip` is not connected, the node raises a `RuntimeError` and turns red.

---

### Anima Negative Prompt Composer

**Category:** `Anima`
**Display name:** `Anima Negative Prompt Composer`

Assembles six negative-prompt category fields into a single string, with optional model-specific preset overrides that return the canonical negative prompt for Anima Base or OOO_Anima directly.

| Input field | Type | Default | Description |
|---|---|---|---|
| `quality_negative` | STRING | `"worst quality, low quality"` | Quality-level negative tokens. |
| `score_negative` | STRING | `"score_1, score_2, score_3"` | Score-based negative tokens. |
| `style_negative` | STRING | `"artifacts, blurry, jpeg artifacts, sepia"` | Style artifacts to suppress. |
| `content_negative` | STRING | `""` | Subject or content tags to avoid (multiline). |
| `meta_negative` | STRING | `"artist name, watermark, signature, text"` | Metadata artifacts to suppress. |
| `extra_negative` | STRING | `""` | Any additional free-form negative tags (multiline). |
| `negative_preset` | COMBO | `ooo_anima_default` | One of: `none`, `anima_base_default`, `ooo_anima_default`, `custom`. When `anima_base_default` or `ooo_anima_default` is selected, the model's `default_negative` from `data/anima_spec.json` is returned directly, ignoring all field values. |

**Output:**

| Name | Type | Description |
|---|---|---|
| `negative_prompt` | STRING | Assembled negative prompt string. |

**Behavior:** When `negative_preset` is `anima_base_default` or `ooo_anima_default`, the entire assembled string is taken from `model_presets.<id>.default_negative` in `data/anima_spec.json`; user-supplied field values are not used. When `negative_preset` is `none` or `custom`, the six fields are joined in canonical order (`quality_negative → score_negative → style_negative → content_negative → meta_negative → extra_negative`) with `", "` as separator; empty fields are omitted.

---

### Anima Tag Palette (v0.5.0+)

**Class name:** `AnimaTagPalette`
**Category:** `Anima`

Satellite node that hosts the full 30-category tag palette with hierarchical UI. Designed to work alongside **Anima Prompt Composer** on the same graph.

**Panel features (v0.5.0):**

| Feature | Description |
|---|---|
| **Subcategory dropdown** | Filters tags by subgroup within a category (e.g. Hair Color → warm / cool / dark / multi). |
| **Random button (🎲)** | Picks a random tag from the active category/subcategory with tier-weighted probability (tier 5 → 5× weight). |
| **Weight adjustment (+/−)** | Hover a tag chip to reveal `+` / `−` buttons; writes `(tag:1.2)` syntax to the target field. Weight clamped to [0.1, 2.0]. |
| **Favorites tab (★)** | Toggle the star on any tag to add/remove from favorites. Favorites are persisted per-node. |
| **History tab (🕒)** | Last 50 tags used (newest first), persisted per-node. |
| **Right-click to remove** | Right-click a tag chip to delete that tag from the target Composer field. |
| **Character preset dropdown** | 49 character presets at the panel top; select a target Composer first, then apply. |

**Connecting to AnimaPromptComposer:**

- Select the target Composer node from the in-panel dropdown.
- Choose the insertion field (e.g. `general`, `character`).
- Click a tag to toggle it in the target field, or use the **Composerへ挿入** button to batch-commit the buffer.
- Alternatively, connect `AnimaTagPalette.tags` → `AnimaPromptComposer.<field>` for graph-link delivery at execution time.

---

### Anima Artist Randomizer

**Class name:** `AnimaArtistRandomizer`
**Category:** `Anima`

Picks `count` random artist tags from a user-managed or built-in pool and outputs them as a comma-separated `@`-prefixed string ready to wire into `AnimaPromptComposer.artist`.

| Widget | Description |
|---|---|
| `count` | Number of artists to pick per generation. |
| `seed` | RNG seed. Use `control_after_generate` for a fresh pick each queue. |
| `pool_source` | Select a named pool (built-in or user-saved). Falls back to the built-in pool when empty. |
| `picked` | Populated at queue time with the actual picked tags (embedded in image metadata). |

Built-in pool: `data/artist_pool_default.json` — 3,195 artist tags (animadex.net score ≥ 0.5). Regenerable with `scripts/fetch_artist_pool.py`.

User pools are persisted in `data/user_artist_pools.json` (gitignored) and managed via the in-node panel (save / load / delete).

**Connecting:** Wire `artist_tags` → `AnimaPromptComposer.artist`.

---

### Anima Character Randomizer

**Class name:** `AnimaCharacterRandomizer`
**Category:** `Anima`

Picks `count` random character tags from a user-managed or built-in pool and outputs them as a comma-separated string ready to wire into `AnimaPromptComposer.character`.

| Widget | Description |
|---|---|
| `count` | Number of character tags to pick. |
| `seed` | RNG seed. |
| `pool_source` | Select a named pool (built-in or user-saved). |
| `picked` | Populated at queue time with the actual picked tags. |

Built-in pool: `data/character_pool_default.json` — ~3349 character tags sourced from animadex.net 1girl entries. Regenerable with `scripts/fetch_character_pool.py`.

User pools are persisted in `data/user_character_pools.json` (gitignored) and managed via the in-node panel.

**Connecting:** Wire `character_tags` → `AnimaPromptComposer.character`.

---

### Anima Situation Randomizer

**Class name:** `AnimaSituationRandomizer`
**Category:** `Anima`

Picks `count` random situation/scene tags from a user-managed or built-in pool and outputs them as a comma-separated string ready to append to `AnimaPromptComposer.general`.

| Widget | Description |
|---|---|
| `count` | Number of situation tags to pick. |
| `seed` | RNG seed. |
| `pool_source` | Select a named pool (built-in or user-saved). |
| `picked` | Populated at queue time with the actual picked tags. |

Built-in pool: `data/situation_pool_default.json` — ~293 situation/scene tags sourced from Danbooru general tags. Regenerable with `scripts/fetch_situation_pool.py`.

User pools are persisted in `data/user_situation_pools.json` (gitignored) and managed via the in-node panel.

**Connecting:** Wire `situation_tags` → `AnimaPromptComposer.general` (or append to an existing general field value).

---

## Quick start

1. In the ComfyUI graph editor, right-click → **Add Node** → **Anima** → **Anima Prompt Composer**. Drag it onto the canvas.
2. The node defaults to the `ooo_anima_default` preset, which pre-fills the `quality` and `year` fields with OOO_Anima recommended values.
3. (Optional) Click the character preset dropdown and select a character from the list. The `character`, `series`, and `general` fields are filled automatically.
4. Click the **Quality** tab in the palette panel at the bottom of the node. Click **Masterpiece** or **Score 7** — the tag is added to the `quality` field automatically.
5. Click the **Hair Color** tab. Click **Blue** — `blue hair` is added to the `general` field (or whichever field the category maps to).
6. In the `artist` field, type `@wlop` or click it from the **Artists** palette tab.
7. Connect the `positive_prompt` output to one of:
   - A standard **CLIPTextEncode** node (then wire its `CONDITIONING` to KSampler).
   - An **Anima Prompt -> Conditioning** node → wire its `conditioning` output to KSampler.
8. Queue the prompt.

---

## Character Presets

The character preset dropdown provides 49 presets that auto-fill the `character`, `series`, and key `general` tags when selected. Presets are grouped by series below.

### Vocaloid
- Hatsune Miku, Kagamine Rin, Kagamine Len, Megurine Luka, Kasane Teto

### Re:Zero
- Rem, Ram, Emilia, Beatrice

### Genshin Impact
- Hu Tao, Raiden Shogun, Yae Miko, Ganyu, Klee, Nahida, Furina, Mona

### Honkai: Star Rail
- Kafka, Silver Wolf, Bronya, Firefly, Acheron

### Frieren: Beyond Journey's End
- Frieren, Fern, Stark

### Spy x Family
- Anya Forger, Yor Forger

### Chainsaw Man
- Power, Makima, Denji

### Demon Slayer
- Nezuko Kamado, Mitsuri Kanroji

### Lycoris Recoil
- Chisato Nishikigi, Takina Inoue

### Sword Art Online
- Asuna

### Persona 5
- Ann Takamaki

### Hololive
- Gawr Gura, Usada Pekora, Houshou Marine

### Touhou
- Hakurei Reimu, Kirisame Marisa, Remilia Scarlet, Cirno

### Atelier Ryza
- Ryza (Reisalin Stout)

### THE iDOLM@STER Cinderella Girls
- Shibuya Rin, Honda Mio

### Generic Archetypes
- Generic School Girl, Generic Maid, Generic Idol

Selecting a preset populates the `character` and `series` fields with the canonical Danbooru tag values and appends the preset's essential general tags to the `general` field. The `artist` field is not modified by presets.

---

## Field reference

Fields are listed in canonical assembly order. This is the order in which tokens appear in the final output string.

| # | Field | Label | Multiline | Hint / example |
|---|---|---|---|---|
| 1 | `quality` | Quality tags | No | `masterpiece, best quality, high quality, score_7` |
| 2 | `year` | Year / era | No | `newest, year 2025, year 2024` |
| 3 | `rating` | Rating | No (COMBO) | `safe` \| `sensitive` \| `nsfw` \| `explicit` |
| 4 | `count` | Subject count | No | `1girl, solo` |
| 5 | `character` | Character | Yes | `hatsune miku` |
| 6 | `series` | Series | Yes | `vocaloid` |
| 7 | `artist` | Artist (@-prefixed) | Yes | `@wlop, @kantoku` |
| 8 | `general` | General tags | Yes | `long hair, blue eyes, smile, school uniform` |
| 9 | `natural_language` | Natural language description | Yes | `She is standing in a sunlit park...` |

All fields except `natural_language` are comma-split and rejoined with `", "`. Empty tokens are dropped. The `natural_language` field is appended verbatim (no splitting) after a `". "` separator when non-empty.

---

## Tag palette categories

The tag palette is organized into 30 categories (18 base + 12 extra) sourced from `data/tag_palette.json` and `data/tag_palette_extras.json`, totalling 509 tags.

### Base categories (18)

| Category ID | Label |
|---|---|
| `quality` | Quality |
| `year` | Year / Era |
| `rating` | Rating |
| `count` | Subject Count |
| `hair_color` | Hair Color |
| `hair_length` | Hair Length |
| `hair_style` | Hair Style |
| `eye_color` | Eye Color |
| `expression` | Expression |
| `pose` | Pose |
| `composition` | Composition / Angle |
| `clothing` | Clothing |
| `location` | Location / Background |
| `lighting` | Lighting |
| `style` | Style / Medium |
| `effects` | Effects |
| `artist` | Artists |
| `natural_language` | Natural Language Templates |

### Extra categories (12)

| Category ID | Label |
|---|---|
| `accessory` | Accessories |
| `weapon` | Weapons / Equipment |
| `food` | Food / Drink |
| `animal` | Animals / Creatures |
| `situation` | Situation / Activity |
| `camera` | Camera / Shot Type |
| `color_tone` | Color Tone / Palette |
| `weather_atmos` | Weather / Atmosphere |
| `season` | Season |
| `architecture` | Architecture / Buildings |
| `magic_fantasy` | Magic / Fantasy Elements |
| `accessory_floral` | Floral / Botanical |

---

## Validation rules

| Rule ID | Trigger | Severity |
|---|---|---|
| `UPPERCASE_TAG` | Token has an uppercase letter (in non-natural-language fields) | WARNING |
| `UNDERSCORE_TAG` | Token contains `_` and is not in the exempt list (`score_N`, `score_N_up`) | WARNING |
| `ARTIST_MISSING_AT` | Token in the `artist` field does not start with `@` | ERROR |
| `INVALID_RATING` | `rating` value is not one of `safe`, `sensitive`, `nsfw`, `explicit` | ERROR |
| `EMPTY_PROMPT` | Assembled prompt is empty | INFO |
| `LONG_PROMPT` | Assembled prompt exceeds 3000 characters | WARNING |
| `DUPLICATE_TAG` | The same normalized tag appears in two or more fields | WARNING |

Normalization for duplicate detection: lowercase, collapse spaces, strip.

---

## Recommended generation settings

These values come from `data/anima_spec.json` `model_presets`.

### Anima Base v1.0

| Setting | Value |
|---|---|
| Sampler | `er_sde` |
| Scheduler | `simple` |
| Steps | 30 |
| CFG | 4.0 |
| Resolution range | 512 – 1536 px |
| Default quality prefix | `masterpiece, best quality, score_7` |
| Default year prefix | _(empty)_ |
| Default rating | `safe` |
| Suggested negative | `worst quality, low quality, score_1, score_2, score_3, artist name` |

### OOO_Anima v1.0

| Setting | Value |
|---|---|
| Sampler | `euler_ancestral` |
| Scheduler | `simple` |
| Steps | 35 |
| CFG | 4.5 |
| Resolution range | 512 – 1920 px |
| Default quality prefix | `masterpiece, best quality, high quality` |
| Default year prefix | `newest, year 2025, year 2024` |
| Default rating | `safe` |
| Default extra | `game cg` |
| Suggested negative | `worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic` |

---

## API endpoints

All routes are registered on `PromptServer.instance.routes` with the prefix `/anima_prompt_helper/`.

| Route | Method | Purpose |
|---|---|---|
| `/anima_prompt_helper/palette` | GET | Serve the merged tag palette dataset (all 30 categories and 509 tags). Merges base + extras, sorted by order. Cached in memory after the first read. |
| `/anima_prompt_helper/spec` | GET | Serve the Anima spec file (canonical order, model presets, validation rule parameters). Cached in memory after the first read. |
| `/anima_prompt_helper/character_presets` | GET | Serve the 49 character preset list. Cached in memory after the first read. |
| `/anima_prompt_helper/validate` | POST | Run server-side validation rules on the current field values; return a list of issues and the assembled prompt length. |
| `/anima_prompt_helper/artist_pools` | GET | List built-in and user artist pools. |
| `/anima_prompt_helper/user_artist_pools` | POST | Save a new user artist pool. |
| `/anima_prompt_helper/user_artist_pools/{id}` | DELETE | Delete a user artist pool by id. |
| `/anima_prompt_helper/character_pools` | GET | List built-in and user character pools. |
| `/anima_prompt_helper/user_character_pools` | POST | Save a new user character pool. |
| `/anima_prompt_helper/user_character_pools/{id}` | DELETE | Delete a user character pool by id. |
| `/anima_prompt_helper/situation_pools` | GET | List built-in and user situation pools. |
| `/anima_prompt_helper/user_situation_pools` | POST | Save a new user situation pool. |
| `/anima_prompt_helper/user_situation_pools/{id}` | DELETE | Delete a user situation pool by id. |

Full request/response schemas are in [`api_contract.md`](api_contract.md).

---

## Workflow templates

Three ready-to-use workflow JSON files are provided in the `templates/` directory:

| File | Nodes | Description |
|---|---|---|
| `OOO_Anima_simple.json` | 10 | Basic workflow: Composer → Conditioning → KSampler. |
| `OOO_Anima_standard.json` | 11 | Standard workflow with negative prompt node and node groups. |
| `OOO_Anima_highquality.json` | 13 | Two-pass high-resolution workflow with upscale and hires fix. |

Load a template by dragging the JSON file onto the ComfyUI canvas or using **Load** in the workflow menu.

---

## CI / Quality

Run all local checks (py_compile, pytest, data integrity, JSON validation, benchmarks) with:

```powershell
# Windows PowerShell
.\scripts\run_all_checks.ps1
```

```bash
# Linux / macOS
./scripts/run_all_checks.sh
```

GitHub Actions workflows are located in `.github/workflows/`:
- `ci.yml` — runs on every push and pull request.
- `release.yml` — builds and publishes a release on version tags.

Performance baselines (measured on reference hardware): composer assembly ~4 µs per call; `/validate` route round-trip ~1 ms.

---

## Internationalization

A Japanese localization file is available at `i18n/ja.json`. It contains translations for all 509 tag display labels, UI control labels, and validation messages. The frontend does not auto-apply this file in the current release; it is provided for future integration and community translation work.

---

## Troubleshooting

For step-by-step solutions to common issues (palette empty, nodes missing, CLIP errors, preset behavior, serialization problems, and more) see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Credits

- **Anima Base** model by [CircleStone Labs](https://huggingface.co/circlestone-labs/Anima).
- **OOO_Anima** model by [oron1208](https://huggingface.co/oron1208/OOO_Anima).
