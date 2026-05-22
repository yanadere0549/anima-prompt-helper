"""nodes.py — ComfyUI node classes for anima-prompt-helper.

Defines:
    AnimaPromptComposer          — assembles nine prompt fields into a STRING.
    AnimaPromptToConditioning    — encodes a STRING + CLIP into CONDITIONING.
    AnimaNegativePromptComposer  — assembles six negative-prompt fields into a STRING.
    AnimaTagPalette              — satellite tag palette for 26 additional categories.
"""
from __future__ import annotations

import logging

from . import composer as _composer

logger = logging.getLogger(__name__)

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
                    ["none", "ooo_anima_default", "custom"],
                    {"default": "ooo_anima_default"},
                ),
            },
            "optional": {
                "lora_trigger_words": (
                    "STRING",
                    {"multiline": False, "forceInput": False, "default": ""},
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
    ) -> tuple[str]:
        """Assemble the nine fields into a positive prompt string.

        Preconditions:
            - All required parameters are ``str`` (ComfyUI guarantees this).
            - ``lora_trigger_words`` is a comma-separated ``str`` or ``""``.
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

        # Warn if any artist token lacks @
        for token in [t.strip() for t in artist.split(",") if t.strip()]:
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

        result = _composer.join_fields(fields, preset=prefix_preset, lora_trigger_words=lora_words)

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
