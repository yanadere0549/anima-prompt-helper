# anima-prompt-helper — User Guide

This guide covers everything you need to know to use the anima-prompt-helper extension effectively. It assumes you have already installed it following the steps in [README.md](README.md).

---

## Contents

1. [Anatomy of a great Anima prompt](#1-anatomy-of-a-great-anima-prompt)
2. [Walkthrough 1: Quick start with OOO_Anima preset](#2-walkthrough-1-quick-start-with-ooo_anima-preset)
3. [Walkthrough 2: Custom prompt composition](#3-walkthrough-2-custom-prompt-composition)
4. [Walkthrough 3: Using the tag palette efficiently](#4-walkthrough-3-using-the-tag-palette-efficiently)
5. [Walkthrough 4: Wiring to KSampler](#5-walkthrough-4-wiring-to-ksampler)
6. [Walkthrough 5: Using character presets](#6-walkthrough-5-using-character-presets)
7. [Walkthrough 6: Negative prompt composition](#7-walkthrough-6-negative-prompt-composition)
8. [Walkthrough 7: Using Anima Tag Palette](#8-walkthrough-7-using-anima-tag-palette)
9. [Walkthrough 8: Using the randomizer nodes](#9-walkthrough-8-using-the-randomizer-nodes)
10. [Tips and tricks](#10-tips-and-tricks)
11. [Pitfalls to avoid](#11-pitfalls-to-avoid)
12. [Frequently asked questions](#12-frequently-asked-questions)

---

## 1. Anatomy of a great Anima prompt

Anima and OOO_Anima models are trained on Danbooru-style tag datasets in which tags consistently appear in a specific order. The model has seen this ordering so often during training that deviating from it — even with the same tags — can reduce output quality. The canonical order is:

```
quality → year → rating → count → character → series → artist → general → natural_language
```

Here is what each field contributes and why it belongs where it is.

### Field 1: Quality

Quality tags anchor the aesthetic level of the generation. Anima Base uses score-based prefixes (`score_7`, `score_7_up`). OOO_Anima uses label-based prefixes (`masterpiece, best quality, high quality`). Placing these first ensures the model interprets all subsequent tags in the context of high-quality output.

Example:
```
masterpiece, best quality, high quality
```

For Anima Base:
```
masterpiece, best quality, score_7
```

### Field 2: Year / Era

Year tags bias the model toward artwork styles associated with that period. Newer years tend to produce cleaner linework and more on-model anatomy. Stacking multiple years (e.g. `newest, year 2025, year 2024`) broadens the effective style window slightly.

Example:
```
newest, year 2025, year 2024
```

Omitting the year field entirely is valid — the model will use its average style.

### Field 3: Rating

A single token from the set `safe`, `sensitive`, `nsfw`, `explicit`. This is a COMBO widget rather than a free-text field, so only valid values are accepted. For most workflows, leave this at `safe`.

### Field 4: Count

The subject count token. Anima follows Danbooru conventions: `1girl`, `2girls`, `1boy`, `solo`, etc. This tag has strong influence on composition, so it belongs early in the prompt.

Example:
```
1girl
```

Or for a group:
```
2girls
```

### Field 5: Character

Named character tags. When you are generating a specific character, place their canonical Danbooru name here.

Example:
```
hatsune miku
```

Leave empty when generating an original character.

### Field 6: Series

The copyright or series the character belongs to. This helps the model activate series-specific style knowledge.

Example:
```
vocaloid
```

For an original character without a known series, leave empty.

### Field 7: Artist

Artist influence tags. Anima requires these to be prefixed with `@`. Multiple artists can be listed; their styles blend.

Example:
```
@wlop, @kantoku
```

Always use the `@` prefix. Omitting it produces an `ARTIST_MISSING_AT` validation error. The palette's **Artists** tab always inserts tags with the correct prefix.

### Field 8: General

The main body of booru-style descriptive tags. This is where you describe hair color, eye color, expression, clothing, pose, composition, background, lighting, and effects.

Example:
```
blue hair, long hair, blue eyes, smile, school uniform, pleated skirt, thigh highs, standing, looking at viewer, classroom, soft lighting, depth of field
```

Keep tags in spaces rather than underscores. The validation system will flag `blue_hair` and suggest `blue hair`.

### Field 9: Natural language

Optional natural-language sentences appended verbatim at the end of the prompt. Unlike the other fields, this content is not comma-split. Use it for compositional descriptions that are difficult to express as tags.

Example:
```
She is standing by a rain-streaked window, her expression distant and contemplative.
```

### Complete example

```
masterpiece, best quality, high quality, newest, year 2025, year 2024, safe, 1girl,
hatsune miku, vocaloid, @wlop,
blue hair, very long hair, twintails, blue eyes, smile, school uniform, pleated skirt, thigh highs,
standing, looking at viewer, classroom, soft lighting, depth of field.
She is reaching toward the viewer with one hand.
```

The assembled output from the node would be a single line with all fields joined by `", "` and the natural language appended after `". "`.

---

## 2. Walkthrough 1: Quick start with OOO_Anima preset

This walkthrough produces a generation-ready prompt in under two minutes using the bundled OOO_Anima preset.

### Step 1: Load a checkpoint

Add a **Load Checkpoint** node. Select an OOO_Anima checkpoint (`.safetensors` file). This node outputs `MODEL`, `CLIP`, and `VAE`.

<!-- TODO: insert screenshot: Load Checkpoint node -->

### Step 2: Add the Anima Prompt Composer node

Right-click on the canvas → **Add Node** → **Anima** → **Anima Prompt Composer**.

The node appears with the `prefix_preset` widget set to `ooo_anima_default` by default. The `quality` field shows `masterpiece, best quality, high quality` and the `year` field shows `newest, year 2025, year 2024`. These values are applied by the preset at compose time — you can leave the field widgets as-is.

<!-- TODO: insert screenshot: Anima Prompt Composer node with default preset -->

### Step 3: Fill in the subject fields

In the `count` widget, type `1girl` (it may already be pre-filled).

In the `character` widget, type the character name, for example: `hatsune miku`.

In the `series` widget, type the series name: `vocaloid`.

### Step 4: Pick an artist from the palette

At the bottom of the node, click the **Artists** tab. Find `@wlop` in the list and click it. The tag is inserted into the `artist` field automatically.

<!-- TODO: insert screenshot: Artists palette tab with @wlop highlighted -->

### Step 5: Add general tags from the palette

Click the **Hair Color** tab. Click **Blue**. The tag `blue hair` is added to the `general` field.

Click the **Expression** tab. Click **Smile**.

Click the **Composition / Angle** tab. Click **Looking at Viewer** and **Full Body**.

At any point you can look at the **Live Preview** area (below the palette) to see the current assembled prompt string.

### Step 6: Check validation badges

Below the live preview, validation badges appear in real time. A green badge with no issues means the prompt is clean. If you see an orange WARNING or red ERROR badge, read the message and correct the relevant field.

### Step 7: Wire to KSampler

Connect the `positive_prompt` output (orange STRING socket) from the Anima Prompt Composer node to one of:

- A standard **CLIPTextEncode** node → wire its `CONDITIONING` to the `positive` input of a **KSampler**.
- An **Anima Prompt -> Conditioning** node (see [Walkthrough 4](#5-walkthrough-4-wiring-to-ksampler)).

Set KSampler to: sampler `euler_ancestral`, scheduler `simple`, steps `35`, cfg `4.5`. Queue the prompt.

<!-- TODO: insert screenshot: full workflow with Composer → AnimaPromptToConditioning → KSampler -->

> **Tip:** If you ran `scripts/install_templates.ps1` (or `scripts/install_templates.sh` on Unix), the three bundled templates appear in your ComfyUI workflow picker under their `anima-prompt-helper - ...` names. Open the workflow picker and select one to load a pre-wired graph instantly instead of building from scratch.

---

## 3. Walkthrough 2: Custom prompt composition

Use this approach when you want full manual control over every field, including quality and year, without the preset overriding your values.

### Step 1: Change the preset

On the **Anima Prompt Composer** node, find the `prefix_preset` widget (COMBO). Change it from `ooo_anima_default` to `none`.

With `none` selected, the `quality` and `year` fields are used exactly as you type them. No overriding occurs.

### Step 2: Set quality tokens for Anima Base

If you are using an Anima Base checkpoint, clear the `quality` field and type:
```
masterpiece, best quality, score_7
```

Leave the `year` field empty if you want the model's default era.

### Step 3: Set the rating

Use the `rating` COMBO to select `safe`, `sensitive`, `nsfw`, or `explicit` according to your intended output.

### Step 4: Fill remaining fields as needed

Fill `count`, `character`, `series`, `artist`, and `general` as described in [Anatomy of a great Anima prompt](#1-anatomy-of-a-great-anima-prompt).

### Step 5: Add a natural language description

In the `natural_language` field, type a sentence or two describing composition or mood:
```
The early morning light filters through curtains, casting long shadows across the room.
```

This text is appended verbatim at the end of the assembled prompt.

### Step 6: Verify the assembled output

The **Live Preview** textarea shows the exact string that will be passed to the next node. Verify the field order looks correct before queuing.

---

## 4. Walkthrough 3: Using the tag palette efficiently

The tag palette is the main tool for building the `general` field (and others) without typing. This walkthrough covers the features that make it faster to use.

### The tab strip

Each tab corresponds to a category in the merged palette (`data/tag_palette.json` + `data/tag_palette_extras.json`). Tabs are ordered by their `order` value in the file. There are 30 categories in total, 509 tags.

**Base categories (18):** Quality · Year / Era · Rating · Subject Count · Hair Color · Hair Length · Hair Style · Eye Color · Expression · Pose · Composition / Angle · Clothing · Location / Background · Lighting · Style / Medium · Effects · Artists · Natural Language Templates

**Extra categories (12):** Accessories · Weapons / Equipment · Food / Drink · Animals / Creatures · Situation / Activity · Camera / Shot Type · Color Tone / Palette · Weather / Atmosphere · Season · Architecture / Buildings · Magic / Fantasy Elements · Floral / Botanical

Click any tab to see its tags as clickable buttons.

### The search box

Type in the search box above the tag grid to filter buttons across all categories. The filter is case-insensitive and matches against tag text and aliases. For example, typing `braid` shows `braid`, `single braid`, `twin braids`, and `drill hair` (which has `ringlet` as an alias, but the primary tag matches).

The search query is persisted in the workflow JSON, so if you save and reopen a workflow, the same filter is restored.

### Clicking tags to add them

Clicking a tag button calls `addTagToField`, which:

1. Finds the appropriate target widget (based on the active category mapping).
2. Splits the current widget value by comma.
3. Checks for duplicates (case-insensitive normalized comparison).
4. Appends the tag if it is not already present.
5. Updates the widget value and fires an `input` event to trigger live preview update.

Duplicate tags are silently skipped — clicking the same button twice has no effect.

### How categories map to fields

The palette categories map to prompt fields as follows:

| Palette category | Writes to field |
|---|---|
| Quality | `quality` |
| Year / Era | `year` |
| Rating | `rating` (selects the COMBO value) |
| Subject Count | `count` |
| Hair Color, Hair Length, Hair Style, Eye Color, Expression, Pose, Composition / Angle, Clothing, Location / Background, Lighting, Style / Medium, Effects | `general` |
| Artists | `artist` |
| Natural Language Templates | `natural_language` |

### Clearing a field

Click directly into the widget text box and edit it by hand. You can delete all text to empty the field, or remove individual tokens.

### Palette state across sessions

The active tab and search query are saved in the workflow JSON file. Other palette state (the rendered button grid) is reconstructed from the palette API on each load.

---

## 5. Walkthrough 4: Wiring to KSampler

There are two ways to connect the Anima Prompt Composer output to a KSampler.

### Option A: Via CLIPTextEncode (standard path)

This is the most compatible approach. Any CLIPTextEncode-based node in your workflow works.

```
[Load Checkpoint] --CLIP--> [CLIPTextEncode] --CONDITIONING--> [KSampler] positive
[Anima Prompt Composer] --positive_prompt (STRING)--> [CLIPTextEncode] text
```

Steps:
1. Add a **CLIPTextEncode** node.
2. Wire the `CLIP` output from **Load Checkpoint** to the `clip` input of CLIPTextEncode.
3. Wire the `positive_prompt` STRING output from **Anima Prompt Composer** to the `text` input of CLIPTextEncode.
4. Wire the `CONDITIONING` output from CLIPTextEncode to the `positive` input of KSampler.

This is the approach to use when you already have a CLIPTextEncode in your workflow or when you need maximum compatibility with other custom nodes.

### Option B: Via Anima Prompt -> Conditioning (direct path)

This shorter path skips the CLIPTextEncode node.

```
[Load Checkpoint] --CLIP--> [Anima Prompt -> Conditioning] --CONDITIONING--> [KSampler] positive
[Anima Prompt Composer] --positive_prompt--> [Anima Prompt -> Conditioning] positive_prompt
```

Steps:
1. Add an **Anima Prompt -> Conditioning** node (category: Anima).
2. Wire the `CLIP` output from **Load Checkpoint** to the `clip` input.
3. Wire the `positive_prompt` STRING output from **Anima Prompt Composer** to the `positive_prompt` input.
4. Wire the `conditioning` output from **Anima Prompt -> Conditioning** to the `positive` input of KSampler.
5. The `positive_prompt` pass-through output can be connected to a **Show Text** or **Display String** node if you want to see the final prompt in the graph.

**Important:** The `clip` input is required. If it is not connected, the node raises a `RuntimeError` and the node turns red. You must connect a CLIP before queuing.

### Negative prompt

Use the **Anima Negative Prompt Composer** node (category: Anima) to build the negative prompt. Set `negative_preset` to `ooo_anima_default` or `anima_base_default` for the recommended model defaults, or use `none`/`custom` to fill the six fields manually. See [Walkthrough 6](#7-walkthrough-6-negative-prompt-composition) for the full wiring guide.

For reference, the model defaults sourced from `data/anima_spec.json` are:

OOO_Anima:
```
worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic
```

Anima Base:
```
worst quality, low quality, score_1, score_2, score_3, artist name
```

---

## 6. Walkthrough 5: Using character presets

The character preset dropdown provides 49 pre-configured character entries. Selecting one auto-fills the `character`, `series`, and essential `general` tags so you do not have to look up Danbooru tag spellings manually.

### Step 1: Open the node

Add an **Anima Prompt Composer** node to the canvas. The character preset dropdown appears at the top of the node panel, labeled **Character Preset**.

### Step 2: Select a character

Click the dropdown. Presets are listed by display name, for example: `Hatsune Miku (Vocaloid)`, `Rem (Re:Zero)`, `Hu Tao (Genshin Impact)`. Select the character you want.

After selecting, the following fields update automatically:
- `character` — set to the canonical Danbooru character tag (e.g. `hatsune miku`).
- `series` — set to the canonical Danbooru series tag (e.g. `vocaloid`).
- `general` — the preset's essential tags are appended (e.g. `long hair, very long hair, twintails, blue hair, blue eyes, necktie, thigh highs, headphones, hair ornament`).

The `artist`, `quality`, `year`, `rating`, `count`, and `natural_language` fields are not modified by the preset.

### Step 3: Review and adjust

Check the `general` field. The preset supplies the character's canonical design tags, but you can freely add or remove tags. For example, if you want the character in an alternate outfit, remove the preset's clothing tags and add your own.

### Step 4: Proceed normally

Fill the remaining fields and queue as normal. The live preview updates as soon as the preset is applied.

### Notes on Danbooru tag names

Some presets use Danbooru's inverted name order. For example, **Nezuko Kamado** maps to `kamado nezuko` and **Yor Forger** maps to `yor briar`. These are the canonical forms the model was trained on. The preset handles this automatically — you do not need to know the internal tag name.

Generic archetypes (Generic School Girl, Generic Maid, Generic Idol) leave `character` and `series` blank and only populate `general` with archetype-appropriate tags. Use them as a starting point for original characters.

---

## 7. Walkthrough 6: Negative prompt composition

The **Anima Negative Prompt Composer** node assembles a structured negative prompt from six ordered categories and supports model-specific preset overrides for Anima Base and OOO_Anima.

### Step 1: Add an Anima Negative Prompt Composer node

Right-click on the canvas → **Add Node** → **Anima** → **Anima Negative Prompt Composer**. Drag it onto the canvas.

### Step 2: Select the negative_preset

Use the `negative_preset` COMBO widget to select the appropriate preset:

- `ooo_anima_default` — recommended for OOO_Anima checkpoints. Returns the model's canonical negative string from `data/anima_spec.json` directly (`worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic`), ignoring all field values.
- `anima_base_default` — recommended for Anima Base checkpoints. Returns `worst quality, low quality, score_1, score_2, score_3, artist name`.
- `none` or `custom` — the six fields below are joined in canonical order and used as the negative prompt.

### Step 3: (Optional) Fill the six fields when using none or custom preset

When `negative_preset` is `none` or `custom`, the assembled output is built from these six fields in order:

| Field | Default | Purpose |
|---|---|---|
| `quality_negative` | `worst quality, low quality` | Quality-level suppressors. |
| `score_negative` | `score_1, score_2, score_3` | Score-level suppressors. |
| `style_negative` | `artifacts, blurry, jpeg artifacts, sepia` | Style artifacts to suppress. |
| `content_negative` | _(empty)_ | Subject or content tags to avoid. |
| `meta_negative` | `artist name, watermark, signature, text` | Metadata and overlay suppressors. |
| `extra_negative` | _(empty)_ | Any additional free-form negative tags. |

Empty fields are skipped in the assembled output.

### Step 4: Connect to a CLIP encoder and wire to KSampler

The `negative_prompt` STRING output must be passed through a CLIP encoder before it can be connected to KSampler's `negative` input. There are two options:

**Option A — via CLIPTextEncode:**

```
[Anima Negative Prompt Composer] --negative_prompt--> [CLIPTextEncode] text
[Load Checkpoint] --CLIP--> [CLIPTextEncode] clip
[CLIPTextEncode] --CONDITIONING--> [KSampler] negative
```

**Option B — via Anima Prompt -> Conditioning (for symmetry with the positive path):**

```
[Anima Negative Prompt Composer] --negative_prompt--> [Anima Prompt -> Conditioning] positive_prompt
[Load Checkpoint] --CLIP--> [Anima Prompt -> Conditioning] clip
[Anima Prompt -> Conditioning] --conditioning--> [KSampler] negative
```

### Step 5: Sample workflow (pseudo-JSON)

```json
{
  "nodes": [
    { "type": "AnimaNegativePromptComposer", "widgets_values": ["worst quality, low quality", "score_1, score_2, score_3", "artifacts, blurry, jpeg artifacts, sepia", "", "artist name, watermark, signature, text", "", "ooo_anima_default"] },
    { "type": "CLIPTextEncode", "inputs": { "text": "<negative_prompt output>", "clip": "<CLIP from checkpoint>" } }
  ]
}
```

The `negative_prompt` STRING output carries the assembled or preset-overridden negative string unchanged to the downstream CLIP encoder.

---

## 9. Walkthrough 8: Using the randomizer nodes

Three randomizer nodes let you pull random tags from curated pools and wire them directly into an `AnimaPromptComposer` field. They are independent nodes — separate from the character presets and the tag palette — and designed for exploration and batch variety.

### The three randomizer nodes

| Node | Class | Output widget | Default target field | Built-in pool source |
|---|---|---|---|---|
| Anima Artist Randomizer | `AnimaArtistRandomizer` | `artist_tags` | `artist` | animadex.net score ≥ 0.5 (3,195 tags) |
| Anima Character Randomizer | `AnimaCharacterRandomizer` | `character_tags` | `character` | animadex.net 1girl characters (~3,349 tags) |
| Anima Situation Randomizer | `AnimaSituationRandomizer` | `situation_tags` | `general` | Danbooru general tags (~293 tags) |

### Pool types: built-in vs user pools

Each randomizer ships with a built-in default pool stored in `data/` (e.g. `data/character_pool_default.json`). You can also create, name, save, and delete your own pools via the in-node panel. User pools are stored in `data/user_character_pools.json` (and the equivalent files for artist and situation pools); these files are gitignored so they stay local to your machine.

The `pool_source` widget lists all available pools for that node type. When the selected pool is empty or has been deleted, the node automatically falls back to the built-in default pool.

### Step 1: Add a randomizer node

Right-click the canvas → **Add Node** → **Anima** → choose **Anima Character Randomizer**, **Anima Situation Randomizer**, or **Anima Artist Randomizer**.

### Step 2: Configure count and seed

- Set `count` to the number of tags you want picked per generation (e.g. `1` for a single character, `3` for three situation tags).
- Set `seed` to a fixed integer for reproducible results, or enable `control_after_generate` → `randomize` so each queue uses a fresh seed.

### Step 3: Select a pool

Use the `pool_source` dropdown to pick a pool. To use the built-in defaults, leave it set to `default`. To use your own pool, build one in the panel (add tags, then click **Save**) and select it by name.

### Step 4: Wire the output into AnimaPromptComposer

Connect the output STRING from the randomizer to the matching field on an `AnimaPromptComposer`:

```
[Anima Character Randomizer] --character_tags--> [AnimaPromptComposer] character
[Anima Situation Randomizer] --situation_tags--> [AnimaPromptComposer] general
[Anima Artist Randomizer]    --artist_tags-----> [AnimaPromptComposer] artist
```

When a Composer field is connected this way, the widget for that field becomes a `forceInput` port and the randomizer's output value flows through at queue time.

### Step 5: Preview before queuing

Each randomizer panel has a **試し引き** (preview pick) button that runs the seeded selection immediately so you can see which tags would be picked without queuing a generation.

### Managing user pools

In the randomizer panel:
- **Add tags** — type a tag name into the input box and press Enter or click **Add**. For artist pools, the `@` prefix is required.
- **Remove tags** — click the `x` on any tag chip in the list.
- **Save** — click the **Save** (💾) button, enter a pool name, and confirm. The pool is written to the user pools JSON file.
- **Load** — select an existing pool from the `pool_source` dropdown.
- **Delete** — select a pool and click the **Delete** (🗑) button. The built-in pool cannot be deleted.

### Data sources

- **AnimaCharacterRandomizer built-in pool** (`data/character_pool_default.json`): character tags sourced from animadex.net 1girl entries. Regenerable with `scripts/fetch_character_pool.py`.
- **AnimaSituationRandomizer built-in pool** (`data/situation_pool_default.json`): situation/scene tags sourced from Danbooru general tags. Regenerable with `scripts/fetch_situation_pool.py`.
- **AnimaArtistRandomizer built-in pool** (`data/artist_pool_default.json`): artist tags from animadex.net with quality score ≥ 0.5. Regenerable with `scripts/fetch_artist_pool.py`.

### Note on character presets vs character randomizer

The **character presets** (available in the AnimaTagPalette panel dropdown) are curated fixed entries that fill `character`, `series`, and `general` fields simultaneously from a hand-picked list of 49 characters. The **Anima Character Randomizer** is a separate node that randomly selects from a larger pool of character tags and outputs only to the `character` field. Use presets when you want a specific known character with all associated tags pre-filled; use the randomizer when you want to explore a wide variety of characters unpredictably.

---

## 10. Tips and tricks

### Artist `@` rule

Every token in the `artist` field must begin with `@`. The validation engine checks each comma-separated token individually. If you type `wlop, @kantoku`, the token `wlop` will produce an `ARTIST_MISSING_AT` ERROR badge. The correct form is `@wlop, @kantoku`.

The **Artists** palette tab always inserts tags with the `@` prefix, so using the palette avoids this error entirely.

Artist tags without `@` are not blocked from generation — the prompt is still produced and passed to the next node — but the model was trained with `@` prefixes and dropping them reduces artist influence.

### `score_N` exception to the underscore rule

Anima models use `score_7`, `score_7_up`, `score_8`, etc. as quality indicators. These tags contain underscores, which normally triggers the `UNDERSCORE_TAG` WARNING. These specific patterns are exempted from the rule and will not produce a validation badge.

The exempt patterns are: `score_N` and `score_N_up` (where N is one or more digits, e.g. `score_7`, `score_9_up`).

All other underscored tags — `blue_hair`, `long_hair`, `school_uniform` — are flagged. Use spaces instead.

### Year tag stacking

Stacking multiple year tags is intentional and encouraged for OOO_Anima:

```
newest, year 2025, year 2024
```

This broadens the effective training-data window the model draws from, typically producing a balanced modern style. You can also narrow it to a single year if you want a more specific aesthetic.

Mixing very distant years (e.g. `year 2025, year 2018`) can produce style blending artifacts. Use years within two to three years of each other for stable results.

### Combining palette tags with typed tags

The palette and the text widgets are not separate systems — clicking a palette button simply appends text to the widget's current value. You can freely mix palette-inserted tags with hand-typed text in the same field. The dedup check runs on normalized (lowercase, space-collapsed) comparison, so if you have already typed `blue hair` and then click **Blue** in the Hair Color tab, the duplicate is not inserted.

### Live preview reflects assembly logic exactly

The live preview textarea in the palette panel mirrors the Python `join_fields()` function exactly (the JS `assemblePreview()` function replicates the same logic). If the preview looks correct, the STRING output from the node will match. You do not need to queue a generation to check the assembled prompt.

### Search is fast for large categories

The **Clothing** and **General** categories have many tags. Type a few letters in the search box to filter quickly. For example, type `skirt` to see `miniskirt`, `pleated skirt`, and other skirt variants. The search matches the `tag` field and all `aliases` entries, so `mini skirt` in aliases is also found.

---

## 11. Validation cheatsheet

Each rule fires under a specific condition. The examples below show the exact input that triggers each badge.

| Rule | Severity | Example input that fires it | Fix |
|---|---|---|---|
| `ARTIST_MISSING_AT` | ERROR | `artist` field: `wlop` | Change to `@wlop` |
| `INVALID_RATING` | ERROR | `rating` field: `sfw` (via API only) | Use `safe`, `sensitive`, `nsfw`, or `explicit` |
| `UPPERCASE_TAG` | WARNING | `quality` field: `Masterpiece` | Change to `masterpiece` |
| `UNDERSCORE_TAG` | WARNING | `general` field: `blue_hair` | Change to `blue hair` |
| `LONG_PROMPT` | WARNING | Assembled prompt exceeds 3000 characters | Remove low-priority tags from `general` |
| `DUPLICATE_TAG` | WARNING | `character`: `hatsune miku`; `general`: `hatsune miku` | Remove from one field |
| `EMPTY_PROMPT` | INFO | All fields empty | Add at least one tag |

Rules that are exempt from specific fields:
- `UPPERCASE_TAG` does not fire in `character`, `series`, or `natural_language`.
- `UNDERSCORE_TAG` does not fire in `natural_language`.
- `score_7`, `score_7_up`, `score_8`, `score_9`, etc. are exempt from `UNDERSCORE_TAG`.

---

## 12. API examples

All routes are served at `http://localhost:8188` by default. Adjust the host/port if ComfyUI is running elsewhere.

### GET /anima_prompt_helper/palette

```bash
curl http://localhost:8188/anima_prompt_helper/palette
```

Returns the merged palette JSON with all 30 categories and 509 tags.

### GET /anima_prompt_helper/spec

```bash
curl http://localhost:8188/anima_prompt_helper/spec
```

Returns canonical field order, model presets, and validation rule parameters.

### GET /anima_prompt_helper/character_presets

```bash
curl http://localhost:8188/anima_prompt_helper/character_presets
```

Returns the 49 character preset list with character, series, essential_general_tags, and notes for each preset.

### POST /anima_prompt_helper/validate

```bash
curl -X POST http://localhost:8188/anima_prompt_helper/validate \
  -H "Content-Type: application/json" \
  -d '{"fields": {"quality": "masterpiece", "rating": "safe", "count": "1girl", "artist": "wlop"}}'
```

Returns:
```json
{
  "issues": [
    {
      "field": "artist",
      "tag": "wlop",
      "rule": "ARTIST_MISSING_AT",
      "severity": "error",
      "message": "Artist tag 'wlop' must start with '@'"
    }
  ],
  "assembled_length": 28
}
```

A clean prompt returns `"issues": []` with only `assembled_length` present.

---

## 13. Pitfalls to avoid

### Using underscored tags (except `score_N`)

The most common mistake is copying tags from Danbooru URLs or autocomplete tools that use underscores as word separators. Anima models are trained on the space-separated Danbooru tag text, not the URL-encoded form.

| Wrong | Correct |
|---|---|
| `blue_hair` | `blue hair` |
| `school_uniform` | `school uniform` |
| `long_hair` | `long hair` |
| `looking_at_viewer` | `looking at viewer` |
| `score_7` | `score_7` (exempt) |

### Missing `@` on artist tags

```
# Wrong — no @ prefix
wlop, kantoku

# Correct
@wlop, @kantoku
```

### Uppercase letters in tags

Booru tags are always lowercase. Typing `Blue Hair` instead of `blue hair` triggers the `UPPERCASE_TAG` WARNING. The model may still understand the tag, but it may not activate the correct tag embedding.

Exceptions: the `character`, `series`, and `natural_language` fields are exempt from the lowercase validation rule, because proper nouns and natural-language sentences reasonably contain uppercase letters.

### Duplicate tags across fields

The `DUPLICATE_TAG` WARNING fires when the same normalized tag appears in more than one field. For example, if you add `smile` to the `character` field and also to the `general` field, the duplicate check will catch it. While duplicates do not prevent generation, they clutter the prompt and can occasionally produce unexpected emphasis behavior.

### Putting artist tags in the `general` field

Artist tokens belong in the `artist` field (with `@`). Placing them in `general` without `@` means the `ARTIST_MISSING_AT` rule will not fire (because it only checks the `artist` field), but the artist influence will be weak or absent because the model expects artist tags in the artist position.

### Leaving `clip` disconnected on AnimaPromptToConditioning

The **Anima Prompt -> Conditioning** node requires a CLIP input. If you use this node and do not connect it, the node will error at queue time with `RuntimeError: CLIP input is None`. Connect CLIP before queuing.

### Assuming the preset fills all fields

The `ooo_anima_default` preset overrides only `quality`, `year`, and `rating`. The `count`, `character`, `series`, `artist`, `general`, and `natural_language` fields are always taken from the widget values. The preset does not pre-fill character or artist information.

---

## 14. Frequently asked questions

**Q: Do I need to fill all nine fields?**

No. Every field except `rating` can be left empty. Empty fields are simply skipped in the assembled output. A prompt with only `quality`, `rating`, `count`, and `general` is perfectly valid.

**Q: What is the difference between `none` and `ooo_anima_default` for `prefix_preset`?**

With `ooo_anima_default`, the `quality` field is set to `masterpiece, best quality, high quality` and the `year` field is set to `newest, year 2025, year 2024` regardless of what you type into those widget fields. Your typed values are ignored for those two fields only. The `rating` widget is also reset to `safe`.

With `none` (or `custom`), the widget values are used exactly as typed.

**Q: Can I use this with models other than Anima and OOO_Anima?**

The node is a general prompt composer with ordered fields. Nothing technically prevents you from using it with other models. However, the canonical field ordering and validation rules (especially the `@` requirement) are specific to Anima-family models. With other models, the ordering may not matter and the artist `@` rule will produce spurious errors. In that case, switch `prefix_preset` to `none` and ignore the validation badges.

**Q: Where does the tag palette data come from? Can I add my own tags?**

The palette is loaded from `data/tag_palette.json`. This file is read-only at runtime. To add custom tags, edit `tag_palette.json` directly (add entries to an existing category or create a new category object) and restart ComfyUI. The file format is documented in `DESIGN.md`.

**Q: How is the assembled prompt different from what CLIPTextEncode receives?**

It is the same string. The `positive_prompt` STRING output of the Anima Prompt Composer is passed unchanged through the wire to any downstream node. CLIPTextEncode receives the exact string you see in the live preview textarea.

**Q: The live preview says my prompt is over 3000 characters. Is that a problem?**

Standard CLIP tokenizes at 77 tokens per chunk. A 3000-character prompt at roughly 4 characters per token is approximately 750 tokens, which exceeds the base CLIP window. Most ComfyUI CLIP encoders automatically handle this with chunked encoding, so generation will not fail. However, tokens beyond the first 77 receive progressively less weight. If the distant tags seem to have no effect, trim the prompt.

**Q: Can I have the same tag in both `quality` and `general`?**

Technically yes, but the `DUPLICATE_TAG` WARNING will fire. The dedup check normalizes both fields and compares across all nine fields. If you intentionally want to emphasize a tag by repeating it, you can ignore the warning — it is advisory, not blocking.

**Q: The validation badges show in the node but the generation still runs. Are errors fatal?**

No validation issue blocks generation. `ERROR` severity issues (like `ARTIST_MISSING_AT`) produce a red badge to indicate that something important is likely wrong, but the node will still output the assembled prompt and ComfyUI will queue the generation normally. Only a missing required CLIP input on the AnimaPromptToConditioning node actually prevents execution.

**Q: What is the difference between using AnimaPromptComposer + CLIPTextEncode versus Composer + AnimaPromptToConditioning?**

Both paths produce identical CONDITIONING output — the difference is the number of nodes. `AnimaPromptToConditioning` is a thin wrapper around the same CLIP encode call that `CLIPTextEncode` performs; it exists purely for convenience so you can wire `positive_prompt` directly without an intermediate node. Use `CLIPTextEncode` when you need maximum compatibility with other custom nodes that expect that specific node type in the graph. Use `AnimaPromptToConditioning` for a cleaner graph with fewer wires. The `STRING` pass-through output on `AnimaPromptToConditioning` is an added bonus — you can tee it to a Show Text node to display the final prompt string without touching the conditioning wire.

**Q: Can I use this extension with non-Anima models?**

Yes, with caveats. The node is a general-purpose ordered prompt composer; it outputs a plain STRING that any downstream node can consume. However, the canonical field ordering (`quality → year → rating → count → character → series → artist → general → natural_language`) and validation rules (`@` prefix on artists, no underscores) are designed specifically for Anima-family models. When using other models: set `prefix_preset` to `none` so the OOO_Anima defaults are not applied; ignore or work around the artist `@` rule (artist tags in other models typically do not use this convention); the UNDERSCORE and UPPERCASE warnings are still useful reminders for standard Danbooru-style models.

**Q: Why does the preset replace my quality field even though I typed something there?**

When `prefix_preset` is `ooo_anima_default`, the `quality`, `year`, and `rating` fields are overridden with the values from `data/anima_spec.json` (`model_presets.ooo_anima`) at compose time. Your widget text is displayed in the field but is not used in the assembled output. This is by design — it ensures the OOO_Anima recommended prefix is always used correctly without requiring you to remember the exact strings. To use your own quality and year values, change `prefix_preset` to `none` or `custom`.

**Q: How do I add my own tags to the palette?**

Edit `data/tag_palette.json` directly. To add a tag to an existing category, append an object to the category's `tags` array:
```json
{ "tag": "your tag here", "aliases": ["optional", "search", "aliases"], "count": 0 }
```
To add a new category, append a new category object to the `categories` array with a unique `id`, `label`, `order` (integer), and `tags` list. You can also add tags to `data/tag_palette_extras.json` if you prefer to keep customizations separate from the base data. After editing, restart ComfyUI (the file is cached in memory after the first read).

**Q: How do I add custom character presets?**

Edit `data/character_presets.json`. Each preset entry requires at minimum: `id` (unique string), `label` (display name), `character` (canonical character tag or `""`), `series` (canonical series tag or `""`), and `essential_general_tags` (array of strings). Example:
```json
{
  "id": "my_custom_oc",
  "label": "My OC",
  "character": "",
  "series": "",
  "essential_general_tags": ["silver hair", "red eyes", "ahoge"]
}
```
Restart ComfyUI after editing the file.

**Q: Can I disable the validation badges?**

There is no UI toggle to disable badges in the current release. The validation call is made via `validateRemote` in `composer.js`, which posts to `/anima_prompt_helper/validate` 400 ms after any field change. To suppress specific badge types you would need to edit `composer.js` to filter out issues by `rule` before passing them to `renderBadges`. Alternatively, you can simply ignore badges you find unimportant — none of them block generation.

**Q: Does the extension send any data to external servers?**

No. The extension is fully local. All API calls are made to `http://localhost:8188` (or whichever host/port ComfyUI is running on). The palette data, spec data, character presets, and validation all run on your local ComfyUI process. No telemetry, no analytics, no external network requests.

**Q: How do I report a bug?**

Open an issue on the GitHub repository. Include:
- ComfyUI version (shown in the terminal on startup).
- The extension version or git commit hash (`git log --oneline -1` inside the extension folder).
- The exact error message from the ComfyUI terminal or browser DevTools Console.
- Steps to reproduce the issue.
- The workflow JSON if the bug is related to serialization or node behavior.

**Q: Is the extension compatible with ComfyUI-Manager?**

Yes. If ComfyUI-Manager is installed, you can use its **Restart** button instead of stopping and restarting the ComfyUI process manually. The extension follows the standard ComfyUI custom node layout (`NODE_CLASS_MAPPINGS`, `NODE_DISPLAY_NAME_MAPPINGS`, `WEB_DIRECTORY` exported from `__init__.py`), which ComfyUI-Manager understands natively. Install and update via Manager's install-from-git or custom-nodes list as with any other extension.

**Q: Why are there two composer nodes — one for positive and one for negative prompts?**

The positive and negative prompts for Anima models have different field structures. The positive prompt has nine ordered fields anchored by the canonical Danbooru tag order (`quality → year → rating → count → character → series → artist → general → natural_language`). The negative prompt has six fields that reflect different concern categories (`quality_negative → score_negative → style_negative → content_negative → meta_negative → extra_negative`). Keeping them as separate nodes makes each node's input interface clear and appropriately sized for its purpose. It also means you can use the positive composer with a standard `CLIPTextEncode` for the negative side, or use only one of the two composer nodes if your workflow only needs structured composition on one side.

**Q: How does the OOO_Anima preset differ from anima_base?**

The `ooo_anima_default` prefix preset overrides `quality` with `masterpiece, best quality, high quality`, `year` with `newest, year 2025, year 2024`, and injects `game cg` after the `rating` field. The OOO_Anima recommended sampler settings are also different: `euler_ancestral`, `simple`, 35 steps, CFG 4.5. The `anima_base` model uses `masterpiece, best quality, score_7` for quality (no year prefix, no `game cg`), and its recommended settings are `er_sde`, `simple`, 30 steps, CFG 4.0. For negative prompts, `ooo_anima_default` includes `artifacts, early, old, nsfw, realistic` while `anima_base_default` uses only `worst quality, low quality, score_1, score_2, score_3, artist name`. When switching models, always change the `prefix_preset` and `negative_preset` to match.

**Q: Can I run this on macOS or Linux?**

Yes. The extension is cross-platform. The Python backend has no Windows-specific dependencies. The CI scripts include both `scripts/run_all_checks.sh` (bash) and `scripts/run_all_checks.ps1` (PowerShell) variants. The frontend is standard browser JavaScript with no OS-specific code. On macOS or Linux, install as you would any other ComfyUI custom node — clone the repository into `ComfyUI/custom_nodes/` and restart ComfyUI.

---

## 15. Reference: complete tag palette contents

This section lists all tags available in the palette at the time of writing. The palette is loaded dynamically from `data/tag_palette.json` at runtime, so this list reflects the bundled data file.

### Quality

| Tag | Notes |
|---|---|
| `masterpiece` | Anima recommended quality prefix |
| `best quality` | |
| `high quality` | |
| `good quality` | |
| `normal quality` | |
| `low quality` | Negative use |
| `worst quality` | Negative use |
| `score_9` | Numeric quality score |
| `score_8` | |
| `score_7` | |
| `score_6` | |
| `score_5` | |
| `score_4` | |
| `score_3` | |
| `score_2` | |
| `score_1` | |

### Year / Era

| Tag | Notes |
|---|---|
| `newest` | Most recent style |
| `recent` | |
| `year 2025` | |
| `year 2024` | |
| `year 2023` | |
| `year 2022` | |
| `year 2021` | |
| `year 2020` | |
| `year 2019` | |
| `year 2018` | |
| `mid` | Mid era |
| `early` | Early era |
| `old` | Old era |

### Rating

| Tag | Notes |
|---|---|
| `safe` | Danbooru: general/safe |
| `sensitive` | Danbooru: sensitive |
| `nsfw` | Danbooru: questionable/nsfw |
| `explicit` | Danbooru: explicit |

### Subject Count

| Tag |
|---|
| `1girl` |
| `2girls` |
| `3girls` |
| `multiple girls` |
| `1boy` |
| `2boys` |
| `multiple boys` |
| `solo` |
| `1other` |

### Hair Color

`blonde hair`, `brown hair`, `black hair`, `white hair`, `silver hair`, `blue hair`, `red hair`, `pink hair`, `purple hair`, `green hair`, `grey hair`, `orange hair`, `two-tone hair`, `gradient hair`

### Hair Length

`very short hair`, `short hair`, `medium hair`, `long hair`, `very long hair`, `absurdly long hair`, `hair down to ankles`

### Hair Style

`twintails`, `ponytail`, `side ponytail`, `low ponytail`, `braid`, `single braid`, `twin braids`, `drill hair`, `hime cut`, `bob cut`, `bowl cut`, `ahoge`, `hair ribbon`, `hair ornament`, `bangs`, `blunt bangs`, `side bangs`, `swept bangs`, `hair between eyes`, `hair bun`, `double bun`, `messy hair`, `wavy hair`, `curly hair`

### Eye Color

`blue eyes`, `green eyes`, `red eyes`, `yellow eyes`, `gold eyes`, `brown eyes`, `black eyes`, `purple eyes`, `pink eyes`, `grey eyes`, `heterochromia`, `gradient eyes`

### Expression

`smile`, `grin`, `smirk`, `light smile`, `open mouth`, `closed mouth`, `parted lips`, `frown`, `pout`, `sad`, `crying`, `tearing up`, `angry`, `embarrassed`, `blush`, `light blush`, `surprised`, `shocked`, `sleepy`, `serious`, `evil smile`, `fang`, `fangs`, `tongue out`, `wink`, `one eye closed`, `closed eyes`, `half-closed eyes`

### Pose

`standing`, `sitting`, `lying`, `kneeling`, `crouching`, `leaning forward`, `leaning back`, `arms up`, `arms behind back`, `hand on hip`, `hands on hips`, `hand on chin`, `head tilt`, `arched back`, `jumping`, `running`, `walking`, `dancing`, `holding object`, `peace sign`, `salute`, `waving`

### Composition / Angle

`looking at viewer`, `looking away`, `looking back`, `looking up`, `looking down`, `from above`, `from below`, `from behind`, `from side`, `profile`, `three-quarter view`, `full body`, `upper body`, `lower body`, `cowboy shot`, `portrait`, `close-up`, `dynamic angle`, `dutch angle`

### Clothing

`school uniform`, `sailor uniform`, `gym uniform`, `dress`, `sundress`, `long dress`, `miniskirt`, `pleated skirt`, `shorts`, `denim shorts`, `jeans`, `pants`, `hoodie`, `sweater`, `t-shirt`, `blouse`, `suit`, `kimono`, `yukata`, `hakama`, `swimsuit`, `bikini`, `one-piece swimsuit`, `lingerie`, `pajamas`, `jacket`, `coat`, `cardigan`, `vest`, `hat`, `beret`, `cap`, `hairband`, `ribbon`, `gloves`, `fingerless gloves`, `knee socks`, `thigh highs`, `stockings`, `boots`, `sneakers`, `heels`

### Location / Background

`indoors`, `outdoors`, `classroom`, `bedroom`, `kitchen`, `living room`, `library`, `school`, `hallway`, `rooftop`, `beach`, `ocean`, `mountain`, `forest`, `garden`, `park`, `street`, `city`, `cafe`, `restaurant`, `train`, `train station`, `shrine`, `temple`, `sky`, `clouds`, `sunset`, `sunrise`, `night`, `day`, `starry sky`, `cherry blossoms`, `snow`, `rain`

### Lighting

`cinematic lighting`, `soft lighting`, `hard lighting`, `backlight`, `rim light`, `golden hour`, `sunlight`, `moonlight`, `lens flare`, `god rays`, `dim lighting`, `dramatic lighting`, `ambient occlusion`, `volumetric lighting`

### Style / Medium

`illustration`, `anime`, `manga`, `cel shading`, `line art`, `sketch`, `watercolor`, `oil painting`, `painterly`, `monochrome`, `sepia`, `pastel colors`, `vibrant colors`, `muted colors`, `official art`, `game cg`

### Effects

`depth of field`, `bokeh`, `motion blur`, `lens flare`, `particles`, `sparkles`, `light particles`, `glow`, `dust`, `fog`, `mist`, `reflection`, `ray tracing`, `chromatic aberration`, `film grain`

### Artists

All artist tags include the required `@` prefix:

`@wlop`, `@sakimichan`, `@yoneyama mai`, `@kantoku`, `@huke`, `@range murata`, `@yoh yoshinari`, `@bkub`, `@pochi`, `@tony taka`, `@redjuice`, `@lack`, `@fuzichoco`, `@ke-ta`, `@ayami kojima`, `@yoshida akihiko`, `@carnelian`, `@tiv`, `@nishiide kengorou`, `@misaki kurehito`

### Natural Language Templates

These are sentence-length template strings inserted verbatim into the `natural_language` field:

| Display name | Template |
|---|---|
| Sunlit field | `She is standing in a sunlit field.` |
| Close-up face | `A close-up shot of her face.` |
| Wind blowing hair | `The wind is gently blowing her hair.` |
| Rain window | `She is looking out a rain-streaked window.` |
| Falling petals | `Soft petals are falling around her.` |
| Sunset glow | `The setting sun casts a warm glow on her face.` |

---

## 16. Reference: prompt assembly algorithm

Understanding the exact assembly logic helps when debugging unexpected output.

### Python implementation summary

The `join_fields()` function in `python/composer.py` performs the following steps:

1. If `preset == "ooo_anima_default"`, replace `quality`, `year`, and `rating` in the working copy with the OOO_Anima defaults before any further processing. The caller's dict is not mutated.

2. Iterate over the canonical field order: `quality`, `year`, `rating`, `count`, `character`, `series`, `artist`, `general` (skip `natural_language` in this pass).

3. For each field:
   a. Read the value from the working dict. Missing keys default to `""`.
   b. Strip leading/trailing whitespace from the value.
   c. If the value is empty after stripping, skip the field entirely.
   d. Split by comma.
   e. Strip each resulting token.
   f. Drop tokens that are empty after stripping.
   g. Rejoin remaining tokens with `", "`.
   h. Append the result to the running list of parts.

4. Join all parts with `", "`.

5. Read `natural_language` from the working dict. Strip it. If non-empty:
   - If the running assembled string is non-empty, append `". "` followed by the natural language text.
   - If the running assembled string is empty, set the result to just the natural language text.

6. Return the assembled string. Never returns `None`; returns `""` if all fields were empty.

### JavaScript implementation

The frontend `assemblePreview()` function in `web/modules/composer.js` mirrors this logic exactly for the purpose of the live preview. It reads current widget values from the node's widget list, applies the same tokenization and joining rules, and writes the result to the preview textarea. The result should always match the Python output for the same field values.

Validation is separate: `validatePreview()` sends the field values via HTTP POST to `/anima_prompt_helper/validate` and receives an array of issues. This is debounced to 400 ms after the last keystroke to avoid flooding the server during fast typing.

### Preset behavior in detail

When `prefix_preset` is `ooo_anima_default`:

- `quality` is overridden with `"masterpiece, best quality, high quality"` regardless of the widget value.
- `year` is overridden with `"newest, year 2025, year 2024"` regardless of the widget value.
- `rating` is overridden with `"safe"`.
- Additionally, `"game cg"` is included in the OOO_Anima `default_extra` field (defined in `data/anima_spec.json`), though the exact implementation of `extra_prefix` injection is determined by the Python node.
- All other fields (`count`, `character`, `series`, `artist`, `general`, `natural_language`) use the widget values as-is.

When `prefix_preset` is `none`:

- All nine widget values are used exactly as provided.

---

## 17. Reference: validation rule details

This section expands on the validation rules with additional context for each rule.

### UPPERCASE_TAG

**Trigger:** Any token in a validated field that contains at least one uppercase ASCII letter (A–Z).

**Exempt fields:** `character`, `series`, `natural_language` — these fields are excluded from the lowercase check because proper nouns and natural-language text reasonably contain uppercase letters.

**Why it matters:** Danbooru tag embeddings in CLIP are trained on lowercase strings. `Blue Hair` and `blue hair` may activate different (or weaker) embeddings than the canonical lowercase form.

**Fix:** Convert the tag to lowercase: `Blue Hair` → `blue hair`.

### UNDERSCORE_TAG

**Trigger:** Any token that contains the `_` character and does not match the exempt patterns.

**Exempt patterns:** `score_N` and `score_N_up` (regular expressions `^score_\d+$` and `^score_\d+_up$`).

**Exempt fields:** `natural_language` is exempt from the underscore check.

**Why it matters:** Anima is trained on space-separated tag forms. The underscore form comes from URL encoding (`blue_hair` is the URL-safe form of the tag `blue hair`). Using underscores may produce a miss or weaker activation.

**Fix:** Replace underscores with spaces: `blue_hair` → `blue hair`.

### ARTIST_MISSING_AT

**Trigger:** Any comma-separated token in the `artist` field that does not start with `@`.

**Why it matters:** Anima model training data encodes artist tags with the `@` prefix as a special marker. Without `@`, the token is treated as a generic booru tag rather than an artist influencer.

**Fix:** Add `@` prefix: `wlop` → `@wlop`.

### INVALID_RATING

**Trigger:** The `rating` field value is not one of `safe`, `sensitive`, `nsfw`, `explicit`.

**Note:** In normal use this rule should never fire because `rating` is a COMBO widget with fixed options. It applies when validating field values programmatically (e.g. via the `/validate` API with a manually constructed request body).

### EMPTY_PROMPT

**Trigger:** The assembled prompt string is empty (all fields were empty or contained only whitespace/empty tokens).

**Severity:** INFO — not a problem per se, but unusual.

### LONG_PROMPT

**Trigger:** The assembled prompt length exceeds 3000 characters.

**Why it matters:** The standard CLIP encoder has a 77-token context window. Long prompts are chunked by most ComfyUI CLIP encoders, but tokens in later chunks receive diminishing attention weight. Prompts over 3000 characters are a signal that the `general` field may have unnecessary tags.

**Fix:** Remove lower-priority tags from the `general` field. Consider whether the `natural_language` description can be shortened.

### DUPLICATE_TAG

**Trigger:** The same normalized tag appears in two or more different fields.

**Normalization:** Lowercase, collapse consecutive spaces to one, strip leading/trailing whitespace.

**Example:** `hatsune miku` in `character` and `hatsune miku` in `general` would trigger this rule.

**Why it matters:** Duplicate tags waste context space and may cause odd emphasis in the output. Keeping each tag in its correct canonical field is both tidier and more effective.

**Fix:** Remove the tag from all but one field. The correct field for most tags is determined by the tag's category.

---

## 18. Reference: HTTP API

For users who want to interact with the extension programmatically (e.g. from scripts, other custom nodes, or testing), here is a condensed reference for the three HTTP routes.

### GET /anima_prompt_helper/palette

Returns the merged tag palette (base + extras) as JSON. Contains 30 categories and 509 tags. Cached in memory after the first request; the cache is cleared only on ComfyUI server restart.

```bash
curl http://localhost:8188/anima_prompt_helper/palette
```

Response structure:
```json
{
  "version": "1.0",
  "categories": [
    {
      "id": "quality",
      "label": "Quality",
      "order": 10,
      "tags": [
        {
          "tag": "masterpiece",
          "display": "Masterpiece",
          "tier": 5,
          "aliases": [],
          "notes": "Anima recommended quality prefix"
        }
      ]
    }
  ]
}
```

Error cases:
- `503 {"error":"palette_not_found"}` — `data/tag_palette.json` is missing.
- `500 {"error":"palette_parse_error"}` — `data/tag_palette.json` contains invalid JSON.

### GET /anima_prompt_helper/spec

Returns the Anima spec (canonical field order, model presets, validation rule parameters).

```bash
curl http://localhost:8188/anima_prompt_helper/spec
```

Response structure:
```json
{
  "version": "1.0",
  "canonical_order": ["quality","year","rating","count","character","series","artist","general","natural_language"],
  "model_presets": { ... },
  "field_specs": { ... },
  "validation_rules": { ... }
}
```

Error cases:
- `503 {"error":"spec_not_found"}` — `data/anima_spec.json` is missing.
- `500 {"error":"spec_parse_error"}` — invalid JSON.

### GET /anima_prompt_helper/character_presets

Returns the 49 character preset list. Cached in memory after the first request.

```bash
curl http://localhost:8188/anima_prompt_helper/character_presets
```

Response structure:
```json
{
  "version": "1.0",
  "presets": [
    {
      "id": "hatsune_miku",
      "label": "Hatsune Miku (Vocaloid)",
      "character": "hatsune miku",
      "series": "vocaloid",
      "essential_general_tags": ["long hair", "very long hair", "twintails", "blue hair", "blue eyes"],
      "recommended_artists": [],
      "notes": "...",
      "tier": 5
    }
  ]
}
```

Error cases:
- `503 {"error":"character_presets_not_found"}` — `data/character_presets.json` is missing.
- `500 {"error":"character_presets_parse_error"}` — invalid JSON.

### POST /anima_prompt_helper/validate

Runs all validation rules on a set of field values and returns issues plus the assembled prompt length. This is the same endpoint the frontend calls after each debounced keystroke.

```bash
curl -X POST http://localhost:8188/anima_prompt_helper/validate \
  -H "Content-Type: application/json" \
  -d '{"fields": {"quality": "masterpiece", "rating": "safe", "count": "1girl", "artist": "wlop"}}'
```

Response structure:
```json
{
  "issues": [
    {
      "field": "artist",
      "tag": "wlop",
      "rule": "ARTIST_MISSING_AT",
      "severity": "error",
      "message": "Artist tag 'wlop' must start with '@'"
    }
  ],
  "assembled_length": 28
}
```

`assembled_length` is always present even when `issues` is empty. A response with `"issues": []` means the prompt passed all validation rules.

Error cases:
- `400 {"error":"invalid_request"}` — malformed request body (not JSON or missing `fields` key).
- `500 {"error":"internal_error"}` — unexpected server-side exception.

The endpoint is read-only and deterministic: identical input always produces identical output. It has no side effects.

---

## 19. Reference: workflow serialization

Saving and loading a ComfyUI workflow JSON file preserves the full Anima Prompt Composer state.

### What is serialized by ComfyUI automatically

ComfyUI serializes `widgets_values` for every node. For Anima Prompt Composer, this captures:
- The string values of all nine text fields (`quality`, `year`, `count`, `character`, `series`, `artist`, `general`, `natural_language`).
- The selected value of the `rating` COMBO.
- The selected value of the `prefix_preset` COMBO.

These values are restored automatically when the workflow is reopened.

### What is serialized by the extension

The extension adds extra state to the node's JSON via a `node.serialize` override:

| Key | Type | Description |
|---|---|---|
| `anima_state.selectedTab` | string | The currently active palette category tab ID. |
| `anima_state.searchQuery` | string | The current search filter string. |

These are restored via `node.onConfigure` when the workflow loads.

### What is not serialized

The rendered button DOM elements and the live preview textarea content are not serialized. They are reconstructed on load: the palette data is re-fetched from the API, buttons are re-rendered, and the preview is recomputed from the restored field values.

### Backward compatibility

If a workflow JSON does not contain `anima_state` (e.g. it was created before this extension or with an older version), `selectedTab` defaults to the first category tab and `searchQuery` defaults to empty. No error is raised.

---

## 20. Reference: model preset data

The following values are taken directly from `data/anima_spec.json` `model_presets`. Use them when configuring KSampler nodes.

### anima_base (Anima Base v1.0)

```json
{
  "id": "anima_base",
  "label": "Anima Base v1.0",
  "default_prefix_quality": "masterpiece, best quality, score_7",
  "default_prefix_year": "",
  "default_rating": "safe",
  "default_extra": "",
  "default_negative": "worst quality, low quality, score_1, score_2, score_3, artist name",
  "recommended": {
    "sampler": "er_sde",
    "scheduler": "simple",
    "steps": 30,
    "cfg": 4.0,
    "resolution_range": [512, 1536]
  }
}
```

**Notes for Anima Base:**
- The `er_sde` sampler is specific to Anima Base and produces better results than `euler_ancestral` for this checkpoint.
- `score_7` in the quality field is a numeric score prefix (not `masterpiece`-style). Use at least `score_7` for good output. `score_9` and `score_8` can be stacked for higher-quality output.
- The year field is intentionally left empty for Anima Base — the model was trained without consistent year tags in the prefix.
- Resolution range is 512–1536 px on the longer side. 768×1024 or 1024×768 are common starting points.
- The `er_sde` sampler is available in ComfyUI if you have the necessary sampler extensions. If it is not available, `euler_ancestral` is the closest alternative.

### ooo_anima (OOO_Anima v1.0)

```json
{
  "id": "ooo_anima",
  "label": "OOO_Anima v1.0",
  "default_prefix_quality": "masterpiece, best quality, high quality",
  "default_prefix_year": "newest, year 2025, year 2024",
  "default_rating": "safe",
  "default_extra": "game cg",
  "default_negative": "worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic",
  "recommended": {
    "sampler": "euler_ancestral",
    "scheduler": "simple",
    "steps": 35,
    "cfg": 4.5,
    "resolution_range": [512, 1920]
  }
}
```

**Notes for OOO_Anima:**
- `euler_ancestral` with `simple` scheduler and 35 steps is the recommended baseline. The model is stable at these settings.
- CFG 4.5 is lower than many SD 1.5 or SDXL workflows. Anima models are sensitive to high CFG — values above 7 tend to produce over-saturation and loss of fine detail.
- `game cg` is the `default_extra` tag for OOO_Anima. When using the `ooo_anima_default` preset, this tag is injected into the assembled prompt. Its placement depends on the `extra_prefix` implementation in the Python node — check the live preview to verify.
- Resolution range extends to 1920 px, allowing landscape or portrait aspect ratios at high resolution. Common sizes: 832×1216 (portrait), 1216×832 (landscape), 1024×1024 (square).
- The negative prompt includes `early`, `old`, and `realistic` to keep outputs in the modern anime-CG style the model was trained for.

---

## 21. Worked examples

This section shows three complete prompt sets from field values through to final assembled string.

### Example 1: OOO_Anima — single character, school setting

**Node settings:**
- `prefix_preset`: `ooo_anima_default`
- `count`: `1girl`
- `character`: `hatsune miku`
- `series`: `vocaloid`
- `artist`: `@wlop`
- `general`: `blue hair, very long hair, twintails, blue eyes, smile, school uniform, pleated skirt, thigh highs, standing, looking at viewer, classroom, soft lighting, depth of field`
- `natural_language`: `She is reaching toward the viewer with one hand.`

**Assembly steps:**
1. Preset overrides quality → `masterpiece, best quality, high quality`
2. Preset overrides year → `newest, year 2025, year 2024`
3. Preset overrides rating → `safe`
4. Fields joined in order: quality, year, rating, count, character, series, artist, general
5. natural_language appended with `. ` separator

**Assembled output:**
```
masterpiece, best quality, high quality, newest, year 2025, year 2024, safe, 1girl, hatsune miku, vocaloid, @wlop, blue hair, very long hair, twintails, blue eyes, smile, school uniform, pleated skirt, thigh highs, standing, looking at viewer, classroom, soft lighting, depth of field. She is reaching toward the viewer with one hand.
```

**Recommended KSampler settings:**
- Sampler: `euler_ancestral`
- Scheduler: `simple`
- Steps: 35
- CFG: 4.5
- Size: 832×1216

---

### Example 2: OOO_Anima — two characters, outdoor scene

**Node settings:**
- `prefix_preset`: `ooo_anima_default`
- `count`: `2girls`
- `character`: _(empty — original characters)_
- `series`: _(empty)_
- `artist`: `@kantoku, @misaki kurehito`
- `general`: `blonde hair, long hair, brown hair, short hair, red eyes, blue eyes, smile, summer dress, sundress, outdoors, beach, sky, sunset, golden hour, bokeh`
- `natural_language`: `The two girls are laughing together as the sun sets over the ocean.`

**Assembled output:**
```
masterpiece, best quality, high quality, newest, year 2025, year 2024, safe, 2girls, @kantoku, @misaki kurehito, blonde hair, long hair, brown hair, short hair, red eyes, blue eyes, smile, summer dress, sundress, outdoors, beach, sky, sunset, golden hour, bokeh. The two girls are laughing together as the sun sets over the ocean.
```

**Notes:** Character and series fields were empty, so they are omitted from the output. The `2girls` count tag signals to the model that two subjects should be present in the composition.

---

### Example 3: Anima Base — solo character, no preset

**Node settings:**
- `prefix_preset`: `none`
- `quality`: `masterpiece, best quality, score_7`
- `year`: _(empty)_
- `rating`: `safe`
- `count`: `1girl, solo`
- `character`: _(empty)_
- `series`: _(empty)_
- `artist`: `@lack`
- `general`: `purple hair, long hair, purple eyes, wink, kimono, hair ornament, indoors, tatami, soft lighting, cinematic lighting`
- `natural_language`: _(empty)_

**Assembled output:**
```
masterpiece, best quality, score_7, safe, 1girl, solo, @lack, purple hair, long hair, purple eyes, wink, kimono, hair ornament, indoors, tatami, soft lighting, cinematic lighting
```

**Notes:** Year field was empty, so it is skipped. Natural language field was empty, so no `. ` separator is added. The output ends after the last general tag.

**Recommended KSampler settings:**
- Sampler: `er_sde`
- Scheduler: `simple`
- Steps: 30
- CFG: 4.0
- Size: 768×1024

---

## 22. Extension architecture for advanced users

This section is for users who want to understand how the extension fits into ComfyUI's architecture, for example when debugging issues or extending the extension.

### Entry point

ComfyUI discovers the extension through `__init__.py` at the extension root. This file:
1. Sets `WEB_DIRECTORY = "./web"` so ComfyUI serves the `web/` directory as static files accessible to the browser.
2. Imports `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS` from `python/nodes.py` and re-exports them so ComfyUI registers the three nodes.
3. Triggers API route registration by importing `python/api/__init__.py`.

### Python node classes

`python/nodes.py` defines three classes:

**AnimaPromptComposer:**
- `INPUT_TYPES` declares ten inputs (nine fields plus `prefix_preset`).
- `RETURN_TYPES = ("STRING",)` and `RETURN_NAMES = ("positive_prompt",)`.
- `FUNCTION = "compose"` — the method called at queue time.
- `CATEGORY = "Anima"`.
- The `compose()` method calls `python/composer.py:join_fields()` with the field values and preset.

**AnimaPromptToConditioning:**
- `INPUT_TYPES` declares `positive_prompt` (STRING, `forceInput=True`) and `clip` (CLIP).
- `RETURN_TYPES = ("CONDITIONING", "STRING")`.
- `FUNCTION = "encode"`.
- `CATEGORY = "Anima"`.
- The `encode()` method calls `clip.encode()` and returns the conditioning plus the pass-through string.

**AnimaNegativePromptComposer:**
- `INPUT_TYPES` declares seven inputs (six category fields plus `negative_preset`).
- `RETURN_TYPES = ("STRING",)` and `RETURN_NAMES = ("negative_prompt",)`.
- `FUNCTION = "compose_negative"` — the method called at queue time.
- `CATEGORY = "Anima"`.
- The `compose_negative()` method calls `python/composer.py:join_negative_fields()` with the field values and preset.

### Frontend modules

The frontend is split into three ES module files under `web/modules/`:

**palette.js** — `PaletteStore` singleton:
- On first use, fetches `/anima_prompt_helper/palette` and caches the result in module scope.
- `renderTabButtons(category, query, container)` renders filtered tag buttons into a container DOM element.
- Tag button click handlers call `composer.addTagToField()`.

**composer.js** — field assembly and validation:
- `getFieldWidget(node, fieldName)` returns the LiteGraph widget object for a given field name.
- `addTagToField(node, category, tag)` appends a tag to the appropriate field, with dedup.
- `assemblePreview(node)` reads all field widgets, applies the canonical join algorithm, and updates the live preview textarea.
- `validatePreview(node)` POSTs field values to `/anima_prompt_helper/validate` (debounced 400 ms) and renders validation badges.

**persist.js** — workflow serialization:
- `serializeState(node)` returns `{ selectedTab, searchQuery }`.
- `restoreState(node, data)` restores these values after workflow load.
- These functions are hooked into `node.serialize` and `node.onConfigure`.

### Backend API modules

`python/api/routes.py` contains three async aiohttp handler coroutines:
- `get_palette(request)` — reads `data/tag_palette.json`, caches it, returns JSON.
- `get_spec(request)` — reads `data/anima_spec.json`, caches it, returns JSON.
- `post_validate(request)` — parses the request body, calls `python/composer.validate_fields()`, returns issues list and assembled length.

`python/api/__init__.py` registers these handlers on `PromptServer.instance.routes` at import time using aiohttp's `RouteTableDef`.

### Data flow summary

```
User types in widget or clicks palette button
  -> composer.addTagToField() updates widget value
  -> composer.assemblePreview() updates live preview textarea
  -> composer.validatePreview() (debounced) POSTs to /validate
       -> python/api/routes.py:post_validate()
            -> python/composer.validate_fields()
                 -> python/validators.py individual rule functions
            <- issues list + assembled_length
       <- JSON response
  -> badge bar updated with issue count and severity

User clicks "Queue Prompt"
  -> ComfyUI calls AnimaPromptComposer.compose()
       -> python/composer.join_fields(fields, preset)
       <- assembled STRING
  -> STRING passed to downstream node (CLIPTextEncode or AnimaPromptToConditioning)
```

---

## 23. Troubleshooting guide (extended)

This section supplements the quick troubleshooting in README.md with additional diagnosis steps.

### Extension not appearing in the node menu

1. Confirm the directory structure. The root `__init__.py` must be at exactly `ComfyUI/custom_nodes/anima-prompt-helper/__init__.py`. If the folder is nested one level deeper (e.g. `custom_nodes/anima-prompt-helper/anima-prompt-helper/__init__.py`), ComfyUI will not find it.

2. Check the ComfyUI terminal for Python errors on startup. Common causes:
   - Syntax error in `__init__.py` (unlikely if you did not modify it, but worth checking after an update).
   - Missing import: if `python/nodes.py` imports a package that is not installed, the entire extension fails to load. Check for `ImportError` or `ModuleNotFoundError`.

3. Verify that the extension directory name does not contain spaces. Some operating systems and ComfyUI versions handle spaces in path names differently.

4. If you installed via `git clone`, run `git status` to confirm all files were checked out. A partial clone or interrupted download can leave files missing.

### Palette shows "palette unavailable" banner

1. Confirm `data/tag_palette.json` exists and is valid JSON. Open it in a text editor and check that it starts with `{` and ends with `}`.

2. From a terminal, test the route directly:
   ```bash
   curl http://localhost:8188/anima_prompt_helper/palette
   ```
   A 503 response confirms the file is missing. A 500 response with `palette_parse_error` means the file is present but malformed.

3. If the file was accidentally deleted, re-clone the repository or restore from a backup. The file is not generated at runtime.

### Validation badges do not appear

Validation badges are populated by a POST to `/anima_prompt_helper/validate`. If they never appear:

1. Open the browser developer tools (F12) → Network tab. Look for a request to `/anima_prompt_helper/validate`. If no request is made, the debounce timer may not be triggering — try typing into a field and waiting 1–2 seconds.

2. If the request returns a non-200 status, check the ComfyUI terminal for Python tracebacks.

3. If the request succeeds but badges still do not render, check the browser console for JavaScript errors related to `composer.js`.

### The live preview does not update

The live preview is updated by `assemblePreview()` on every `input` event fired by any field widget. If it is not updating:

1. Check the browser console for JavaScript errors.
2. Verify that the palette panel DOM was injected correctly: inspect the node in the browser developer tools and look for an element with class or id matching `anima_palette_panel`.
3. Try closing and reopening the workflow.

### The `rating` COMBO reverts to `safe` unexpectedly

When `prefix_preset` is `ooo_anima_default`, the `rating` is overridden to `safe` at compose time. This override does not change the widget's displayed value — the COMBO shows whatever you last set it to — but the actual output string will always contain `safe` when using this preset. To use a different rating, set `prefix_preset` to `none` and then set `rating` to the desired value.

### Prompt output does not include `game cg`

The OOO_Anima model benefits from `game cg` as part of the style prefix. This tag is defined in `data/anima_spec.json` as `default_extra` for the `ooo_anima` preset. The exact mechanism by which it is injected into the prompt depends on the Python node implementation — if it is not appearing in the live preview or assembled output, check whether `python/nodes.py` applies the `extra_prefix` from the spec. As a workaround, you can manually add `game cg` to the `general` field.

### After workflow load, the palette tab is on the wrong category

The `selectedTab` is restored from `anima_state` in the workflow JSON. If the workflow was saved with one tab active, it will restore to that tab. This is the intended behavior. If you want a different default tab, switch to it manually and re-save the workflow.

### ComfyUI reports an error about `PromptServer.instance.routes`

This error can occur if the extension is loaded before PromptServer is initialized. In rare cases this can happen during ComfyUI startup ordering. The extension's API module defers route registration to import time of `python/api/__init__.py`, which is called from the root `__init__.py`. If ComfyUI reports this error consistently, file a bug report with the full traceback and ComfyUI version number.

---

## 24. Quick reference card

A condensed one-page reference for experienced users.

### Canonical field order
```
quality → year → rating → count → character → series → artist → general → natural_language
```

### OOO_Anima preset defaults
| Field | Value |
|---|---|
| quality | `masterpiece, best quality, high quality` |
| year | `newest, year 2025, year 2024` |
| rating | `safe` |
| extra | `game cg` |

### OOO_Anima KSampler settings
`euler_ancestral` · `simple` · steps 35 · CFG 4.5 · 512–1920 px

### Anima Base KSampler settings
`er_sde` · `simple` · steps 30 · CFG 4.0 · 512–1536 px

### Artist tag format
```
@wlop, @kantoku, @lack
```
Every artist token MUST start with `@`.

### Valid rating values
`safe` · `sensitive` · `nsfw` · `explicit`

### Underscore exceptions (not flagged)
`score_7`, `score_8`, `score_9`, `score_7_up`, `score_9_up` etc.

### Validation severities
- **ERROR** (red) — `ARTIST_MISSING_AT`, `INVALID_RATING`
- **WARNING** (orange) — `UPPERCASE_TAG`, `UNDERSCORE_TAG`, `LONG_PROMPT`, `DUPLICATE_TAG`
- **INFO** (grey) — `EMPTY_PROMPT`

### API routes
| Route | Purpose |
|---|---|
| `GET /anima_prompt_helper/palette` | Merged tag palette (30 categories, 509 tags) |
| `GET /anima_prompt_helper/spec` | Spec, presets, validation params |
| `GET /anima_prompt_helper/character_presets` | 49 character preset list |
| `POST /anima_prompt_helper/validate` | Validate field values, return issues |
| `GET /anima_prompt_helper/artist_pools` | List built-in and user artist pools |
| `POST/DELETE /anima_prompt_helper/user_artist_pools[/{id}]` | Save or delete a user artist pool |
| `GET /anima_prompt_helper/character_pools` | List built-in and user character pools |
| `POST/DELETE /anima_prompt_helper/user_character_pools[/{id}]` | Save or delete a user character pool |
| `GET /anima_prompt_helper/situation_pools` | List built-in and user situation pools |
| `POST/DELETE /anima_prompt_helper/user_situation_pools[/{id}]` | Save or delete a user situation pool |

### Fields exempt from validation rules
| Rule | Exempt fields |
|---|---|
| Lowercase check | `character`, `series`, `natural_language` |
| Underscore check | `natural_language` |
| Artist @ check | All fields except `artist` |

---

## 8. Walkthrough 7: Using Anima Tag Palette

`AnimaTagPalette` is a satellite node that offloads the 26 character/scene
detail category tabs from `AnimaPromptComposer`, keeping the Composer compact.

### What is in the Palette vs the Composer?

| Node | Categories |
|---|---|
| AnimaPromptComposer | quality, year, rating, count (4 tabs) |
| AnimaTagPalette | hair_color, hair_length, hair_style, eye_color, expression, pose, composition, clothing, location, lighting, style, effects, artist, natural_language, accessory, weapon, food, animal, situation, camera, color_tone, weather_atmos, season, architecture, magic_fantasy, accessory_floral (26 tabs) |

### Path A — Connection path (recommended for batch workflows)

1. Add an `AnimaTagPalette` node to your graph.
2. Click through the category tabs and build your tag list in the `tags_buffer` widget.
3. Connect the `tags` output port to any `AnimaPromptComposer` field input (e.g. `general`).
4. When connected, the Composer's `general` widget disappears (forceInput mode) and the palette's `tags_buffer` value is passed directly at queue time.

### Path B — DOM injection path (recommended for interactive exploration)

1. Add both an `AnimaTagPalette` node and an `AnimaPromptComposer` node.
2. Leave the `tags` output unconnected.
3. In the AnimaTagPalette panel:
   - Select the target Composer from the **対象 Composer** dropdown (auto-selects if only one exists).
   - Select the destination field from the **挿入先フィールド** dropdown (auto-updates when you switch tabs).
   - Click tags to accumulate them in `tags_buffer`.
   - Click **Composerへ挿入** to write all buffered tags into the selected Composer field widget.
4. If the selected field is already connected (widget absent), the panel shows a warning and blocks the insertion — use Path A in that case.

### Notes

- Tag deduplication applies in both paths (lowercase comparison).
- `tags_buffer` persists its value as a normal STRING widget — it survives graph save/load.
- Switching category tabs automatically updates the **挿入先フィールド** dropdown to the category's default target (e.g. `hair_color` → `general`, `artist` → `artist`).


