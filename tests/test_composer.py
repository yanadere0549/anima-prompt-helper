"""Unit tests for python/composer.py.

These tests are ComfyUI-independent and run with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow importing python package without installing ComfyUI.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.composer import join_fields, OOO_ANIMA_DEFAULTS, CANONICAL_ORDER, _load_ooo_anima_defaults
from python.nodes import AnimaPromptComposer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_FIELDS = {
    "quality": "masterpiece, best quality",
    "year": "newest",
    "rating": "safe",
    "count": "1girl",
    "character": "hatsune miku",
    "series": "vocaloid",
    "artist": "@wlop",
    "general": "blue hair, smile",
    "natural_language": "She stands in a field.",
}


# ---------------------------------------------------------------------------
# Basic joining
# ---------------------------------------------------------------------------


def test_join_all_fields_no_preset() -> None:
    result = join_fields(_FULL_FIELDS, preset="none")
    # natural_language separated by ". "
    assert "She stands in a field." in result
    assert result.endswith("She stands in a field.")
    assert ". She stands in a field." in result


def test_join_canonical_order() -> None:
    """Field tokens must appear in canonical order."""
    result = join_fields(_FULL_FIELDS, preset="none")
    idx_quality = result.index("masterpiece")
    idx_year = result.index("newest")
    idx_rating = result.index("safe")
    idx_count = result.index("1girl")
    idx_char = result.index("hatsune miku")
    idx_series = result.index("vocaloid")
    idx_artist = result.index("@wlop")
    idx_general = result.index("blue hair")
    idx_nl = result.index("She stands")
    assert idx_quality < idx_year < idx_rating < idx_count < idx_char
    assert idx_char < idx_series < idx_artist < idx_general < idx_nl


def test_join_empty_fields() -> None:
    result = join_fields({}, preset="none")
    assert result == ""


def test_join_only_natural_language() -> None:
    result = join_fields({"natural_language": "Hello world."}, preset="none")
    assert result == "Hello world."


def test_join_missing_keys_treated_as_empty() -> None:
    """Missing keys must not raise; they are treated as empty string."""
    result = join_fields({"quality": "masterpiece"}, preset="none")
    assert result == "masterpiece"


def test_join_strips_whitespace() -> None:
    result = join_fields({"quality": "  masterpiece  "}, preset="none")
    assert result == "masterpiece"


def test_join_drops_empty_comma_tokens() -> None:
    result = join_fields({"general": "blue hair,,smile,"}, preset="none")
    assert ",," not in result
    assert result == "blue hair, smile"


def test_join_natural_language_not_comma_split() -> None:
    nl = "Red, green, and blue."
    result = join_fields({"natural_language": nl}, preset="none")
    # The comma-containing NL string must appear verbatim after ". " separator
    assert result == nl


def test_join_natural_language_separator_with_other_fields() -> None:
    fields = {"quality": "masterpiece", "natural_language": "Nice image."}
    result = join_fields(fields, preset="none")
    assert result == "masterpiece. Nice image."


# ---------------------------------------------------------------------------
# OOO_Anima preset shadowing
# ---------------------------------------------------------------------------


def test_preset_ooo_anima_shadows_quality_year_rating() -> None:
    fields = {
        "quality": "OVERRIDE",
        "year": "OVERRIDE_YEAR",
        "rating": "explicit",
    }
    result = join_fields(fields, preset="ooo_anima_default")
    assert "OVERRIDE" not in result
    assert OOO_ANIMA_DEFAULTS["quality"].split(",")[0].strip() in result
    assert "newest" in result  # from OOO_ANIMA_DEFAULTS year
    assert "safe" in result


def test_preset_ooo_anima_includes_game_cg() -> None:
    """ooo_anima_default must include 'game cg' (default_extra) in the output."""
    result = join_fields({}, preset="ooo_anima_default")
    assert "game cg" in result


def test_preset_ooo_anima_game_cg_after_rating_before_count() -> None:
    """'game cg' must appear after 'safe' and before count/character tokens."""
    fields = {"count": "1girl", "character": "hatsune miku"}
    result = join_fields(fields, preset="ooo_anima_default")
    assert "game cg" in result
    idx_safe = result.index("safe")
    idx_game_cg = result.index("game cg")
    idx_count = result.index("1girl")
    assert idx_safe < idx_game_cg < idx_count, (
        f"Expected safe < game cg < 1girl, got positions {idx_safe}, {idx_game_cg}, {idx_count}"
    )


def test_preset_ooo_anima_does_not_shadow_other_fields() -> None:
    fields = {"general": "cat ears", "count": "2girls"}
    result = join_fields(fields, preset="ooo_anima_default")
    assert "cat ears" in result
    assert "2girls" in result


def test_preset_none_does_not_shadow() -> None:
    fields = {"quality": "low quality", "rating": "explicit"}
    result = join_fields(fields, preset="none")
    assert "low quality" in result
    assert "explicit" in result


def test_preset_custom_uses_field_values() -> None:
    fields = {"quality": "my custom quality", "rating": "nsfw"}
    result = join_fields(fields, preset="custom")
    assert "my custom quality" in result
    assert "nsfw" in result


# ---------------------------------------------------------------------------
# Return type guarantees
# ---------------------------------------------------------------------------


def test_returns_str() -> None:
    result = join_fields({})
    assert isinstance(result, str)


def test_returns_non_none_on_empty() -> None:
    assert join_fields({}) is not None


# ---------------------------------------------------------------------------
# CANONICAL_ORDER sanity
# ---------------------------------------------------------------------------


def test_canonical_order_length() -> None:
    assert len(CANONICAL_ORDER) == 9


def test_canonical_order_contains_natural_language() -> None:
    assert "natural_language" in CANONICAL_ORDER
    assert CANONICAL_ORDER[-1] == "natural_language"


# ---------------------------------------------------------------------------
# prefix_preset with empty quality / year edge cases
# ---------------------------------------------------------------------------


def test_preset_ooo_anima_applies_when_quality_empty() -> None:
    """ooo_anima_default must inject preset quality even when quality is ''."""
    result = join_fields({"quality": "", "rating": "safe"}, preset="ooo_anima_default")
    assert OOO_ANIMA_DEFAULTS["quality"].split(",")[0].strip() in result


def test_preset_ooo_anima_applies_when_year_empty() -> None:
    """ooo_anima_default must inject preset year even when year is ''."""
    result = join_fields({"year": "", "rating": "safe"}, preset="ooo_anima_default")
    assert "newest" in result


def test_preset_ooo_anima_applies_when_both_quality_and_year_empty() -> None:
    """ooo_anima_default must inject both quality and year even when both are ''."""
    result = join_fields({"quality": "", "year": "", "rating": "safe"}, preset="ooo_anima_default")
    assert OOO_ANIMA_DEFAULTS["quality"].split(",")[0].strip() in result
    assert "newest" in result


# ---------------------------------------------------------------------------
# lora_trigger_words argument
# ---------------------------------------------------------------------------


def test_lora_trigger_words_appended_after_general() -> None:
    """lora_trigger_words tokens must appear after general tags."""
    fields = {"general": "blue hair"}
    result = join_fields(fields, preset="none", lora_trigger_words=["flat color"])
    idx_general = result.index("blue hair")
    idx_lora = result.index("flat color")
    assert idx_general < idx_lora


def test_lora_trigger_words_before_natural_language() -> None:
    """lora_trigger_words tokens must appear before natural_language."""
    fields = {"general": "smile", "natural_language": "She looks happy."}
    result = join_fields(fields, preset="none", lora_trigger_words=["flat color"])
    idx_lora = result.index("flat color")
    idx_nl = result.index("She looks happy.")
    assert idx_lora < idx_nl


def test_lora_trigger_words_multiple() -> None:
    """Multiple trigger words are all inserted."""
    result = join_fields({}, preset="none", lora_trigger_words=["flat color", "no lineart"])
    assert "flat color" in result
    assert "no lineart" in result


def test_lora_trigger_words_none_is_noop() -> None:
    """lora_trigger_words=None must produce identical output to not passing it."""
    fields = {"quality": "masterpiece"}
    assert join_fields(fields, preset="none", lora_trigger_words=None) == join_fields(fields, preset="none")


def test_lora_trigger_words_empty_list_is_noop() -> None:
    """Empty list must not add anything to the output."""
    fields = {"quality": "masterpiece"}
    assert join_fields(fields, preset="none", lora_trigger_words=[]) == join_fields(fields, preset="none")


def test_lora_trigger_words_strips_whitespace() -> None:
    """Tokens with surrounding whitespace must be stripped."""
    result = join_fields({}, preset="none", lora_trigger_words=["  flat color  "])
    assert "flat color" in result
    assert "  flat color  " not in result


def test_lora_trigger_words_skips_empty_after_strip() -> None:
    """Tokens that are empty after stripping must not appear."""
    result = join_fields({"quality": "masterpiece"}, preset="none", lora_trigger_words=["   "])
    assert result == "masterpiece"


def test_lora_trigger_words_skips_non_str_elements() -> None:
    """Non-str elements in the list must be silently skipped."""
    result = join_fields({}, preset="none", lora_trigger_words=["valid", 42, None, "also valid"])  # type: ignore[list-item]
    assert "valid" in result
    assert "also valid" in result


def test_lora_trigger_words_type_error_on_non_list() -> None:
    """Passing a non-list, non-None value must raise TypeError."""
    with pytest.raises(TypeError):
        join_fields({}, preset="none", lora_trigger_words="flat color")  # type: ignore[arg-type]


def test_lora_trigger_words_with_ooo_anima_preset() -> None:
    """lora_trigger_words must work correctly together with ooo_anima_default preset."""
    result = join_fields(
        {"count": "1girl"},
        preset="ooo_anima_default",
        lora_trigger_words=["flat color", "no lineart"],
    )
    assert "flat color" in result
    assert "no lineart" in result
    # Must come after general section (1girl is count, comes before general)
    assert "1girl" in result


# ---------------------------------------------------------------------------
# extras argument (artist / general / natural_language append)
# ---------------------------------------------------------------------------


def test_extras_none_is_noop() -> None:
    """extras=None must produce identical output to not passing it."""
    fields = {"general": "1girl"}
    assert join_fields(fields, extras=None) == join_fields(fields)


def test_extras_empty_dict_is_noop() -> None:
    """extras={} must produce identical output to not passing it."""
    fields = {"general": "1girl"}
    assert join_fields(fields, extras={}) == join_fields(fields)


def test_extras_artist_appended_to_artist_field() -> None:
    """extras['artist'] tokens are appended to the artist field, before general."""
    result = join_fields(
        {"artist": "@wlop", "general": "1girl"},
        extras={"artist": "@kantoku"},
    )
    # Both artist tokens must appear, and they must precede the general tokens.
    assert "@wlop" in result and "@kantoku" in result
    assert result.index("@wlop") < result.index("@kantoku") < result.index("1girl")


def test_extras_artist_into_empty_field() -> None:
    """extras['artist'] alone (no base) still produces the artist tokens."""
    result = join_fields({"general": "1girl"}, extras={"artist": "@kantoku"})
    assert "@kantoku" in result
    assert result.index("@kantoku") < result.index("1girl")


def test_extras_general_appended_to_general_field() -> None:
    """extras['general'] tokens are appended to the general field."""
    result = join_fields(
        {"general": "1girl, smile"},
        extras={"general": "blue eyes, long hair"},
    )
    assert "1girl" in result and "smile" in result
    assert "blue eyes" in result and "long hair" in result
    # Base tokens come before extras
    assert result.index("1girl") < result.index("blue eyes")


def test_extras_natural_language_appended_with_period_separator() -> None:
    """extras['natural_language'] is appended to natural_language with '. '."""
    result = join_fields(
        {"general": "1girl", "natural_language": "She is smiling."},
        extras={"natural_language": "Standing in a forest."},
    )
    # The natural_language section is joined to the rest with '. ', and the
    # extra is in turn joined with another '. '.
    assert "She is smiling.. Standing in a forest." in result


def test_extras_natural_language_into_empty_field() -> None:
    """extras['natural_language'] without a base value is used verbatim."""
    result = join_fields(
        {"general": "1girl"},
        extras={"natural_language": "She is dancing."},
    )
    assert result.endswith(". She is dancing.")


def test_extras_skips_empty_and_whitespace_only() -> None:
    """Empty / whitespace-only extras values are dropped silently."""
    result = join_fields(
        {"artist": "@wlop"},
        extras={"artist": "   ", "general": "", "natural_language": "\t\n"},
    )
    # No extra content, no errors
    assert result == "@wlop"


def test_extras_ignores_non_string_values() -> None:
    """Non-string extras values are silently skipped, not raised on."""
    result = join_fields(
        {"general": "1girl"},
        extras={"artist": None, "general": 42, "natural_language": ["x"]},  # type: ignore[dict-item]
    )
    assert result == "1girl"


def test_extras_ignores_unknown_keys() -> None:
    """extras keys outside {'artist','general','natural_language'} are ignored."""
    result = join_fields(
        {"general": "1girl"},
        extras={"character": "asuka", "quality": "masterpiece"},
    )
    # Neither key gets merged.
    assert "asuka" not in result and "masterpiece" not in result
    assert result == "1girl"


def test_extras_type_error_on_non_dict() -> None:
    """Passing a non-dict, non-None extras must raise TypeError."""
    with pytest.raises(TypeError):
        join_fields({}, extras="artist=foo")  # type: ignore[arg-type]


def test_extras_does_not_mutate_caller_dicts() -> None:
    """Caller's fields and extras dicts must not be mutated."""
    fields = {"artist": "@wlop", "general": "1girl"}
    extras = {"artist": "@kantoku", "general": "blue eyes"}
    fields_before = dict(fields)
    extras_before = dict(extras)
    _ = join_fields(fields, extras=extras)
    assert fields == fields_before
    assert extras == extras_before


def test_extras_combines_with_lora_trigger_words() -> None:
    """extras and lora_trigger_words can be combined; both contribute tokens."""
    result = join_fields(
        {"general": "1girl"},
        extras={"general": "blue eyes"},
        lora_trigger_words=["flat color"],
    )
    # general extra is part of general section; lora trigger words come after.
    assert (
        result.index("1girl")
        < result.index("blue eyes")
        < result.index("flat color")
    )


def test_extras_with_ooo_anima_preset_does_not_touch_quality() -> None:
    """Preset shadowing on quality/year/rating is unaffected by extras."""
    result = join_fields(
        {"count": "1girl"},
        preset="ooo_anima_default",
        extras={"general": "blue eyes", "natural_language": "She is smiling."},
    )
    # Preset still injects quality / year / rating values.
    assert "masterpiece" in result.lower() or "best quality" in result.lower()
    # extras still flow through.
    assert "blue eyes" in result
    assert "She is smiling." in result


# ---------------------------------------------------------------------------
# AnimaPromptComposer node: optional inputs (artist_extra / general_extra /
# natural_language_extra)
# ---------------------------------------------------------------------------


def _compose_defaults() -> dict:
    """Minimal set of required arguments for AnimaPromptComposer.compose."""
    return {
        "quality": "",
        "year": "",
        "rating": "safe",
        "count": "",
        "character": "",
        "series": "",
        "artist": "",
        "general": "",
        "natural_language": "",
        "prefix_preset": "none",
    }


def test_node_input_types_exposes_extra_inputs() -> None:
    """INPUT_TYPES advertises the three new optional *_extra widgets."""
    schema = AnimaPromptComposer.INPUT_TYPES()
    optional = schema["optional"]
    assert "artist_extra" in optional
    assert "general_extra" in optional
    assert "natural_language_extra" in optional
    for key in ("artist_extra", "general_extra", "natural_language_extra"):
        assert optional[key][0] == "STRING"
        assert optional[key][1].get("default") == ""
        assert optional[key][1].get("multiline") is True


def test_node_compose_defaults_unchanged_without_extras() -> None:
    """When no *_extra is passed, compose() output matches the baseline."""
    node = AnimaPromptComposer()
    args = _compose_defaults()
    args["general"] = "1girl, smile"
    baseline = node.compose(**args)
    with_blank_extras = node.compose(
        **args,
        artist_extra="",
        general_extra="",
        natural_language_extra="",
    )
    assert baseline == with_blank_extras


def test_node_compose_artist_extra_merges_into_artist() -> None:
    """artist_extra is appended into the artist section of positive_prompt."""
    node = AnimaPromptComposer()
    args = _compose_defaults()
    args["artist"] = "@wlop"
    args["general"] = "1girl"
    out = node.compose(**args, artist_extra="@kantoku, @anmi")
    text = out[0]
    assert "@wlop" in text and "@kantoku" in text and "@anmi" in text
    # Artist tokens precede the general "1girl"
    assert text.index("@kantoku") < text.index("1girl")
    assert text.index("@anmi") < text.index("1girl")


def test_node_compose_general_extra_merges_into_general() -> None:
    """general_extra is appended into the general section of positive_prompt."""
    node = AnimaPromptComposer()
    args = _compose_defaults()
    args["general"] = "1girl, smile"
    out = node.compose(**args, general_extra="blue eyes, long hair")
    text = out[0]
    for token in ("1girl", "smile", "blue eyes", "long hair"):
        assert token in text


def test_node_compose_natural_language_extra_appended_after_period() -> None:
    """natural_language_extra is joined with ". " to natural_language."""
    node = AnimaPromptComposer()
    args = _compose_defaults()
    args["general"] = "1girl"
    args["natural_language"] = "She is smiling."
    out = node.compose(**args, natural_language_extra="Standing in a forest.")
    text = out[0]
    # nl section is joined to comma-tokens with ". " then extras with ". "
    assert "She is smiling.. Standing in a forest." in text


def test_node_compose_extras_combine_with_lora_trigger_words() -> None:
    """Both optional knobs may be used simultaneously."""
    node = AnimaPromptComposer()
    args = _compose_defaults()
    args["general"] = "1girl"
    out = node.compose(
        **args,
        general_extra="blue eyes",
        lora_trigger_words="flat color",
    )
    text = out[0]
    # canonical order: general (1girl + blue eyes) before lora trigger words
    assert (
        text.index("1girl")
        < text.index("blue eyes")
        < text.index("flat color")
    )
