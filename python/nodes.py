"""nodes.py — ComfyUI node classes for anima-prompt-helper.

Defines:
    AnimaPromptComposer          — assembles nine prompt fields into a STRING.
    AnimaPromptToConditioning    — encodes a STRING + CLIP into CONDITIONING.
    AnimaNegativePromptComposer  — assembles six negative-prompt fields into a STRING.
    AnimaTagPalette              — satellite tag palette for 26 additional categories.
    AnimaPromptImporter          — extracts prompts from generated images and
                                   pushes selected tags into composer fields.
    AnimaArtistRandomizer        — picks N random artist tags from a saved pool
                                   (seed-reproducible) and outputs them as STRING.
"""
from __future__ import annotations

import logging

from . import artist_pool as _artist_pool
from . import character_pool as _character_pool
from . import situation_pool as _situation_pool
from . import composer as _composer

logger = logging.getLogger(__name__)


def _prefix_preset_choices() -> list[str]:
    """Return the combo-widget choices for ``prefix_preset``.

    The list always starts with the three built-in tokens and is followed
    by any user-defined preset ids loaded from
    ``data/user_prefix_presets.json``. Called by ``INPUT_TYPES`` each time
    the node definition is requested, so newly-saved user presets become
    selectable after a graph refresh without restarting ComfyUI.
    """
    builtin = ["none", "ooo_anima_default", "custom"]
    try:
        user_ids = _composer.get_user_prefix_preset_ids()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Failed to load user prefix preset ids: %s", exc)
        user_ids = []
    # Strip any user id that collides with a built-in token (sanitize_prefix
    # rejects these, but guard against legacy files anyway).
    safe_user_ids = [i for i in user_ids if i not in builtin]
    return builtin + safe_user_ids


# ---------------------------------------------------------------------------
# AnimaPromptComposer
# ---------------------------------------------------------------------------


class AnimaPromptComposer:
    """ComfyUI node that assembles the nine Anima prompt fields into a STRING.

    Preconditions (enforced by ComfyUI):
        - All STRING inputs are ``str``.
        - ``rating`` is one of ``{"safe","sensitive","nsfw","explicit"}``.
        - ``prefix_preset`` is one of ``{"none","ooo_anima_default","custom"}``.

    Postconditions:
        - Returns a 1-tuple ``(str,)``.
        - Result may be ``""`` when all fields are empty.

    Invariants:
        - Field order in output: quality→year→rating→count→character→series→
          artist→general→natural_language.
        - Artist tokens lacking ``@`` prefix are NOT silently fixed; a warning
          is logged.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "quality": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "masterpiece, best quality, high quality",
                    },
                ),
                "year": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "newest, year 2025, year 2024",
                    },
                ),
                "rating": (
                    ["safe", "sensitive", "nsfw", "explicit"],
                    {"default": "safe"},
                ),
                "count": (
                    "STRING",
                    {"multiline": False, "default": "1girl"},
                ),
                "character": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "series": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "artist": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "general": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "natural_language": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
                "prefix_preset": (
                    _prefix_preset_choices(),
                    {"default": "ooo_anima_default"},
                ),
            },
            "optional": {
                "lora_trigger_words": (
                    "STRING",
                    {"multiline": False, "forceInput": False, "default": ""},
                ),
                # *_extra inputs mirror the lora_trigger_words pattern: optional
                # STRING widgets that accept both typed text and wired input
                # (e.g. from AnimaCharacterRandomizer). Their content is
                # appended to the matching widget value before the canonical
                # join, so randomizer-supplied tags flow into positive_prompt
                # WITHOUT overwriting whatever the user typed in the main
                # widget.
                "artist_extra": (
                    "STRING",
                    {"multiline": True, "forceInput": False, "default": ""},
                ),
                "general_extra": (
                    "STRING",
                    {"multiline": True, "forceInput": False, "default": ""},
                ),
                "natural_language_extra": (
                    "STRING",
                    {"multiline": True, "forceInput": False, "default": ""},
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("positive_prompt",)
    FUNCTION = "compose"
    CATEGORY = "Anima"
    OUTPUT_NODE = False

    def compose(
        self,
        quality: str,
        year: str,
        rating: str,
        count: str,
        character: str,
        series: str,
        artist: str,
        general: str,
        natural_language: str,
        prefix_preset: str,
        lora_trigger_words: str = "",
        artist_extra: str = "",
        general_extra: str = "",
        natural_language_extra: str = "",
    ) -> tuple[str]:
        """Assemble the nine fields into a positive prompt string.

        Preconditions:
            - All required parameters are ``str`` (ComfyUI guarantees this).
            - ``lora_trigger_words`` is a comma-separated ``str`` or ``""``.
            - ``artist_extra`` / ``general_extra`` / ``natural_language_extra``
              are ``str`` or ``""``. Each is appended to the matching widget
              field via :func:`composer.join_fields`'s ``extras`` parameter.
        Postconditions:
            - Returns ``(str,)``; never raises unless an internal bug occurs.
        """
        fields = {
            "quality": quality,
            "year": year,
            "rating": rating,
            "count": count,
            "character": character,
            "series": series,
            "artist": artist,
            "general": general,
            "natural_language": natural_language,
        }

        # Warn if any artist token lacks @ (check the merged artist + extra so
        # randomizer-supplied tokens are validated too).
        combined_artist = artist
        if isinstance(artist_extra, str) and artist_extra.strip():
            combined_artist = (
                artist + ", " + artist_extra if artist.strip() else artist_extra
            )
        for token in [t.strip() for t in combined_artist.split(",") if t.strip()]:
            if not token.startswith("@"):
                logger.warning(
                    "Artist token '%s' does not start with '@'; "
                    "this may produce unexpected results.",
                    token,
                )

        # Parse comma-separated lora_trigger_words string into list.
        lora_words: list[str] | None = None
        if isinstance(lora_trigger_words, str) and lora_trigger_words.strip():
            lora_words = [
                t.strip()
                for t in lora_trigger_words.split(",")
                if t.strip()
            ]

        # Per-field extras: only include keys whose value is a non-empty str.
        extras_map: dict[str, str] = {}
        for key, value in (
            ("artist", artist_extra),
            ("general", general_extra),
            ("natural_language", natural_language_extra),
        ):
            if isinstance(value, str) and value.strip():
                extras_map[key] = value

        result = _composer.join_fields(
            fields,
            preset=prefix_preset,
            lora_trigger_words=lora_words,
            extras=extras_map or None,
        )

        if len(result) > 3000:
            logger.warning(
                "Assembled prompt is %d chars (> 3000). "
                "Passing through without truncation.",
                len(result),
            )

        return (result,)


# ---------------------------------------------------------------------------
# AnimaPromptToConditioning
# ---------------------------------------------------------------------------


class AnimaPromptToConditioning:
    """ComfyUI node that encodes a positive prompt STRING + CLIP into CONDITIONING.

    Preconditions:
        - ``clip`` must not be ``None``; raises ``RuntimeError`` otherwise.
        - ``positive_prompt`` is ``str``.

    Postconditions:
        - Returns ``(conditioning, positive_prompt)`` 2-tuple.

    Invariants:
        - Delegates all CLIP encoding to the clip model's own methods,
          matching the CLIPTextEncode pattern in ComfyUI core.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "positive_prompt": ("STRING", {"forceInput": True}),
                "clip": ("CLIP",),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "positive_prompt")
    FUNCTION = "encode"
    CATEGORY = "Anima"

    def encode(self, positive_prompt: str, clip: object) -> tuple:
        """Encode the prompt string into a CONDITIONING tensor.

        Preconditions:
            - ``clip`` is not ``None``.
            - ``positive_prompt`` is ``str``.
        Postconditions:
            - Returns ``(conditioning, positive_prompt)`` 2-tuple.
        """
        if clip is None:
            raise RuntimeError("CLIP input is None")

        tokens = clip.tokenize(positive_prompt)
        conditioning = clip.encode_from_tokens_scheduled(tokens)
        return (conditioning, positive_prompt)


# ---------------------------------------------------------------------------
# AnimaNegativePromptComposer
# ---------------------------------------------------------------------------


class AnimaNegativePromptComposer:
    """ComfyUI node that assembles six negative-prompt fields into a STRING.

    Preconditions (enforced by ComfyUI):
        - All STRING inputs are ``str``.
        - ``negative_preset`` is one of
          ``{"none","anima_base_default","ooo_anima_default","custom"}``.

    Postconditions:
        - Returns a 1-tuple ``(str,)``. Never ``None``.

    Invariants:
        - When preset is ``"anima_base_default"`` or ``"ooo_anima_default"``,
          the model default negative string from anima_spec.json is returned
          directly, overriding all field values.
        - Field order: quality_negative → score_negative → style_negative →
          content_negative → meta_negative → extra_negative.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "quality_negative": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "worst quality, low quality",
                    },
                ),
                "score_negative": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "score_1, score_2, score_3",
                    },
                ),
                "style_negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "artifacts, blurry, jpeg artifacts, sepia",
                    },
                ),
                "content_negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                    },
                ),
                "meta_negative": (
                    "STRING",
                    {
                        "multiline": False,
                        "default": "artist name, watermark, signature, text",
                    },
                ),
                "extra_negative": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                    },
                ),
                "negative_preset": (
                    ["none", "anima_base_default", "ooo_anima_default", "custom"],
                    {"default": "ooo_anima_default"},
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("negative_prompt",)
    FUNCTION = "compose_negative"
    CATEGORY = "Anima"
    OUTPUT_NODE = False

    def compose_negative(
        self,
        quality_negative: str,
        score_negative: str,
        style_negative: str,
        content_negative: str,
        meta_negative: str,
        extra_negative: str,
        negative_preset: str,
    ) -> tuple[str]:
        """Assemble the six negative-prompt fields into a single string.

        Preconditions:
            - All parameters are ``str`` (ComfyUI guarantees this).
            - ``negative_preset`` is one of the four allowed values.
        Postconditions:
            - Returns ``(str,)``; never raises unless an internal bug occurs.
        """
        fields = {
            "quality_negative": quality_negative,
            "score_negative": score_negative,
            "style_negative": style_negative,
            "content_negative": content_negative,
            "meta_negative": meta_negative,
            "extra_negative": extra_negative,
        }

        result = _composer.join_negative_fields(fields, preset=negative_preset)

        if len(result) > 3000:
            logger.warning(
                "Assembled negative prompt is %d chars (> 3000). "
                "Passing through without truncation.",
                len(result),
            )

        return (result,)


# ---------------------------------------------------------------------------
# AnimaTagPalette
# ---------------------------------------------------------------------------


class AnimaTagPalette:
    """Tag palette satellite node.

    Provides 26 additional category tabs (hair_color and below) that are
    intentionally moved out of AnimaPromptComposer to keep the composer
    compact.  This node has:

      * A free-form STRING widget ``tags_buffer`` that accumulates the
        comma-separated tag list collected from the panel UI.
      * The same STRING value is also exposed as the node's only return,
        so users can either:
          (a) Connect ``tags`` -> any AnimaPromptComposer field input
              (forceInput style; the connected widget disappears).
          (b) Leave it unconnected and use the in-panel "Composerへ挿入"
              button to write into a same-graph composer's widget directly
              via DOM.

    Preconditions:
        - ``tags_buffer`` is a comma-separated str (may be empty).
    Postconditions:
        - Returns ``(tags_buffer,)`` verbatim.
    """

    CATEGORY = "Anima"
    FUNCTION = "passthrough"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tags",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        # tags_buffer is an internal state widget driven entirely by the panel UI;
        # multiline=False keeps LiteGraph from auto-expanding the widget row as
        # the comma-separated string grows. The JS side additionally hides the
        # widget via computeSize=[0,-4] and display:none for builds that still
        # render single-line text widgets.
        return {
            "required": {
                "tags_buffer": ("STRING", {"multiline": False, "default": ""}),
            },
        }

    def passthrough(self, tags_buffer: str) -> tuple[str]:
        """Return ``tags_buffer`` unchanged.

        Preconditions:
            - ``tags_buffer`` is ``str``.
        Postconditions:
            - Returns ``(tags_buffer,)`` 1-tuple.
        Raises:
            TypeError: if ``tags_buffer`` is not ``str``.
        """
        if not isinstance(tags_buffer, str):
            raise TypeError(
                f"tags_buffer must be str, got {type(tags_buffer).__name__!r}"
            )
        return (tags_buffer,)


# ---------------------------------------------------------------------------
# AnimaPromptImporter
# ---------------------------------------------------------------------------


class AnimaPromptImporter:
    """Prompt-from-image importer satellite node.

    The user drops a generated image onto the panel; the panel calls the
    ``/anima_prompt_helper/extract_metadata`` endpoint to pull the embedded
    positive / negative prompts, classifies the tokens by category (artist /
    quality / year / count / character / series / general / natural_language /
    rating), and offers chip-style UI to push selected tokens into a
    same-graph AnimaPromptComposer's widgets.

    The node itself only carries two internal STRING widgets that mirror the
    last extracted prompts, so the panel state persists across workflow
    save/load. These are also exposed as outputs for users who prefer wiring
    the values into downstream nodes instead of clicking buttons.
    """

    CATEGORY = "Anima"
    FUNCTION = "passthrough"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive_prompt", "negative_prompt")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "positive_buffer": ("STRING", {"multiline": True, "default": ""}),
                "negative_buffer": ("STRING", {"multiline": True, "default": ""}),
            },
        }

    def passthrough(
        self, positive_buffer: str, negative_buffer: str
    ) -> tuple[str, str]:
        """Return the two buffer strings unchanged.

        Preconditions:
            - both arguments are str.
        Postconditions:
            - Returns ``(positive_buffer, negative_buffer)``.
        """
        if not isinstance(positive_buffer, str):
            raise TypeError("positive_buffer must be str")
        if not isinstance(negative_buffer, str):
            raise TypeError("negative_buffer must be str")
        return (positive_buffer, negative_buffer)


# ---------------------------------------------------------------------------
# AnimaArtistRandomizer
# ---------------------------------------------------------------------------


class AnimaArtistRandomizer:
    """Random artist-tag picker satellite node.

    Picks ``count`` distinct artist tags at random from a saved pool and emits
    them as a comma-separated STRING (insert-ready, e.g. ``"@dairi, @neme"``)
    that can be wired into an ``AnimaPromptComposer`` ``artist`` input, or
    injected into a same-graph composer via the panel's "Composerへ挿入" button.

    The ``pool`` is a comma/newline-separated buffer managed by the side panel
    (autocomplete suggest + locally-saved named pools). When it is empty the
    node falls back to the built-in high-score pool shipped in
    ``data/artist_pool_default.json``, so a freshly-dropped node works
    immediately.

    Selection is fully determined by ``seed`` — the same seed + pool always
    yields the same artists (reproducible). Pair ``seed`` with
    ``control_after_generate`` (increment / randomize) and ComfyUI's batch
    count to run "j times" and get j different artist sets in one queue.

    In the GUI the chosen artists are written into the ``picked`` widget at
    queue time, so they are serialized into the workflow / prompt and embedded
    in the saved image's metadata — you can always see which artists produced
    an image. ``randomize`` returns ``picked`` verbatim when present.

    Preconditions (enforced by ComfyUI):
        - ``count`` is an int >= 1.
        - ``seed`` is a non-negative int.
        - ``pool`` is a str.
    Postconditions:
        - Returns a 1-tuple ``(str,)``; ``""`` only when both the pool and the
          built-in default are empty.
    """

    CATEGORY = "Anima"
    FUNCTION = "randomize"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("artist_tags",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "count": (
                    "INT",
                    {"default": 1, "min": 1, "max": 50, "step": 1},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                # pool is an internal buffer driven by the panel UI; multiline
                # keeps the saved tag list readable. Empty -> built-in pool.
                "pool": ("STRING", {"multiline": True, "default": ""}),
                # picked holds the artists chosen for THIS run. In the GUI the
                # panel JS fills it at queue time (via the graphToPrompt hook),
                # so the actual selection is serialized into the workflow / API
                # prompt and therefore embedded in the saved image's metadata —
                # making it possible to see which artists produced an image.
                # Left empty for headless / API callers, in which case Python
                # falls back to its own seeded selection below.
                "picked": ("STRING", {"multiline": False, "default": ""}),
            },
        }

    def randomize(
        self, count: int, seed: int, pool: str, picked: str = ""
    ) -> tuple[str]:
        """Return the artist tags for this run (seed-reproducible).

        Preconditions:
            - ``count`` and ``seed`` are ints; ``pool`` and ``picked`` are str.
        Postconditions:
            - Returns ``(str,)``; never raises for valid ComfyUI inputs.
            - When ``picked`` is non-empty (GUI path) it is returned verbatim so
              the output matches exactly what was recorded in the image metadata.
            - Otherwise (headless / API) a fresh seeded selection from ``pool``
              (or the built-in default pool) is returned.
        """
        # GUI path: the panel already chose and recorded the artists.
        if isinstance(picked, str) and picked.strip():
            return (picked.strip(),)

        tags = _artist_pool.parse_pool(pool)
        if not tags:
            tags = _artist_pool.load_default_pool()
            if tags:
                logger.debug(
                    "AnimaArtistRandomizer: pool empty, using built-in "
                    "default pool (%d tags)",
                    len(tags),
                )

        if not tags:
            logger.warning(
                "AnimaArtistRandomizer: no artist tags available (pool empty "
                "and default pool missing); returning empty string."
            )
            return ("",)

        chosen = _artist_pool.pick_artists(tags, count, seed)
        return (_artist_pool.join_artists(chosen),)


# ---------------------------------------------------------------------------
# AnimaCharacterRandomizer
# ---------------------------------------------------------------------------


class AnimaCharacterRandomizer:
    """Random character-tag picker satellite node.

    Picks ``count`` distinct character tags at random from a saved pool and
    emits four STRING outputs:
        - ``character_tags``: comma-separated picked characters (wired into a
          composer's ``character`` input, or injected via the panel).
        - ``series``: comma-separated unique series names looked up from
          ``animadex_character_presets.json`` for the picked characters.
        - ``general``: comma-separated unique ``essential_general_tags`` from
          all matched presets.
        - ``prompt_example``: newline-separated ``prompt_example`` strings from
          all matched presets (useful for the composer's natural_language
          field).

    The ``pool`` is a comma/newline-separated buffer managed by the side panel
    (autocomplete suggest + locally-saved named pools). When it is empty the
    node falls back to the built-in pool shipped in
    ``data/character_pool_default.json``, so a freshly-dropped node works
    immediately.

    Selection is fully determined by ``seed`` — the same seed + pool always
    yields the same characters (reproducible). Pair ``seed`` with
    ``control_after_generate`` (increment / randomize) and ComfyUI's batch
    count to run "j times" and get j different character sets in one queue.

    In the GUI the chosen characters and their aggregated meta are written
    into ``picked`` / ``picked_series`` / ``picked_general`` /
    ``picked_prompt_example`` at queue time, so they are serialized into the
    workflow / prompt and embedded in the saved image's metadata. ``randomize``
    returns the GUI-recorded values verbatim when ``picked`` is non-empty;
    otherwise (headless / API) it seed-picks and aggregates meta from
    ``animadex_character_presets.json`` itself.

    Preconditions (enforced by ComfyUI):
        - ``count`` is an int >= 1.
        - ``seed`` is a non-negative int.
        - ``pool``, ``picked``, ``picked_series``, ``picked_general``,
          ``picked_prompt_example`` are strings.
    Postconditions:
        - Returns a 4-tuple ``(character_tags, series, general,
          prompt_example)``. Each element may be ``""`` (e.g. no matching
          preset). ``character_tags`` is ``""`` only when both the pool and
          the built-in default are empty.
    """

    CATEGORY = "Anima"
    FUNCTION = "randomize"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("character_tags", "series", "general", "prompt_example")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "count": (
                    "INT",
                    {"default": 1, "min": 1, "max": 50, "step": 1},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                # pool is an internal buffer driven by the panel UI; multiline
                # keeps the saved tag list readable. Empty -> built-in pool.
                "pool": ("STRING", {"multiline": True, "default": ""}),
                # picked holds the characters chosen for THIS run. In the GUI
                # the panel JS fills it at queue time (via the graphToPrompt
                # hook), so the actual selection is serialized into the
                # workflow / API prompt and therefore embedded in the saved
                # image's metadata. Left empty for headless / API callers, in
                # which case Python falls back to its own seeded selection.
                "picked": ("STRING", {"multiline": False, "default": ""}),
                # picked_* widgets carry the meta the GUI panel resolved
                # against CharacterPresetStore (which knows about user
                # presets), so the workflow records exactly what the GUI
                # surfaced. Headless callers leave them empty; Python then
                # aggregates meta from data/animadex_character_presets.json.
                "picked_series": ("STRING", {"multiline": False, "default": ""}),
                "picked_general": ("STRING", {"multiline": True, "default": ""}),
                "picked_prompt_example": (
                    "STRING",
                    {"multiline": True, "default": ""},
                ),
            },
        }

    def randomize(
        self,
        count: int,
        seed: int,
        pool: str,
        picked: str = "",
        picked_series: str = "",
        picked_general: str = "",
        picked_prompt_example: str = "",
    ) -> tuple[str, str, str, str]:
        """Return the picked characters and aggregated meta for this run.

        Preconditions:
            - ``count`` and ``seed`` are ints; remaining args are str.
        Postconditions:
            - Returns ``(character_tags, series, general, prompt_example)``.
              Never raises for valid ComfyUI inputs.
            - When ``picked`` is non-empty (GUI path) the four GUI-recorded
              widgets are returned verbatim so output matches exactly what
              was recorded in the image metadata.
            - Otherwise (headless / API) a fresh seeded selection from
              ``pool`` (or the built-in default pool) is returned, with meta
              aggregated from ``data/animadex_character_presets.json``.
        """
        # GUI path: the panel already chose characters AND resolved meta
        # against its own preset store (which includes user presets), so
        # trust those widgets verbatim — empty values mean no match was
        # found by the GUI, which is authoritative.
        if isinstance(picked, str) and picked.strip():
            return (
                picked.strip(),
                picked_series.strip() if isinstance(picked_series, str) else "",
                picked_general.strip() if isinstance(picked_general, str) else "",
                picked_prompt_example.strip()
                if isinstance(picked_prompt_example, str)
                else "",
            )

        tags = _character_pool.parse_pool(pool)
        if not tags:
            tags = _character_pool.load_default_pool()
            if tags:
                logger.debug(
                    "AnimaCharacterRandomizer: pool empty, using built-in "
                    "default pool (%d tags)",
                    len(tags),
                )

        if not tags:
            logger.warning(
                "AnimaCharacterRandomizer: no character tags available (pool "
                "empty and default pool missing); returning empty strings."
            )
            return ("", "", "", "")

        chosen = _character_pool.pick_tags(tags, count, seed)
        series, general, prompt_example = _character_pool.aggregate_meta(chosen)
        return (
            _character_pool.join_tags(chosen),
            series,
            general,
            prompt_example,
        )


# ---------------------------------------------------------------------------
# AnimaSituationRandomizer
# ---------------------------------------------------------------------------


class AnimaSituationRandomizer:
    """Random situation-tag picker satellite node.

    Picks ``count`` distinct situation tags at random from a saved pool and
    emits them as a comma-separated STRING intended for the ``general`` input
    of an ``AnimaPromptComposer`` node (situation-related general tags such as
    locations, lighting conditions, weather, and scene compositions).

    The ``pool`` is a comma/newline-separated buffer managed by the side panel
    (autocomplete suggest + locally-saved named pools). When it is empty the
    node falls back to the built-in Danbooru situation pool shipped in
    ``data/situation_pool_default.json``, so a freshly-dropped node works
    immediately.

    Selection is fully determined by ``seed`` — the same seed + pool always
    yields the same situations (reproducible). Pair ``seed`` with
    ``control_after_generate`` (increment / randomize) and ComfyUI's batch
    count to run "j times" and get j different situation sets in one queue.

    In the GUI the chosen situations are written into the ``picked`` widget at
    queue time, so they are serialized into the workflow / prompt and embedded
    in the saved image's metadata. ``randomize`` returns ``picked`` verbatim
    when present.

    Preconditions (enforced by ComfyUI):
        - ``count`` is an int >= 1.
        - ``seed`` is a non-negative int.
        - ``pool`` is a str.
    Postconditions:
        - Returns a 1-tuple ``(str,)``; ``""`` only when both the pool and the
          built-in default are empty.
    """

    CATEGORY = "Anima"
    FUNCTION = "randomize"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("situation_tags",)
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls) -> dict:  # type: ignore[override]
        return {
            "required": {
                "count": (
                    "INT",
                    {"default": 1, "min": 1, "max": 50, "step": 1},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                # pool is an internal buffer driven by the panel UI; multiline
                # keeps the saved tag list readable. Empty -> built-in pool.
                "pool": ("STRING", {"multiline": True, "default": ""}),
                # picked holds the situations chosen for THIS run. In the GUI
                # the panel JS fills it at queue time (via the graphToPrompt
                # hook), so the actual selection is serialized into the
                # workflow / API prompt and therefore embedded in the saved
                # image's metadata. Left empty for headless / API callers, in
                # which case Python falls back to its own seeded selection.
                "picked": ("STRING", {"multiline": False, "default": ""}),
            },
        }

    def randomize(
        self, count: int, seed: int, pool: str, picked: str = ""
    ) -> tuple[str]:
        """Return the situation tags for this run (seed-reproducible).

        Preconditions:
            - ``count`` and ``seed`` are ints; ``pool`` and ``picked`` are str.
        Postconditions:
            - Returns ``(str,)``; never raises for valid ComfyUI inputs.
            - When ``picked`` is non-empty (GUI path) it is returned verbatim so
              the output matches exactly what was recorded in the image metadata.
            - Otherwise (headless / API) a fresh seeded selection from ``pool``
              (or the built-in default pool) is returned.
        """
        # GUI path: the panel already chose and recorded the situations.
        if isinstance(picked, str) and picked.strip():
            return (picked.strip(),)

        tags = _situation_pool.parse_pool(pool)
        if not tags:
            tags = _situation_pool.load_default_pool()
            if tags:
                logger.debug(
                    "AnimaSituationRandomizer: pool empty, using built-in "
                    "default pool (%d tags)",
                    len(tags),
                )

        if not tags:
            logger.warning(
                "AnimaSituationRandomizer: no situation tags available (pool "
                "empty and default pool missing); returning empty string."
            )
            return ("",)

        chosen = _situation_pool.pick_tags(tags, count, seed)
        return (_situation_pool.join_tags(chosen),)
