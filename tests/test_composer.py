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
