"""Unit tests for python/validators.py.

These tests are ComfyUI-independent and run with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.validators import (
    ValidationIssue,
    _strip_weight,
    check_artist_at,
    check_duplicate,
    check_empty,
    check_long,
    check_lowercase,
    check_rating,
    check_underscore,
    validate_fields,
)


# ---------------------------------------------------------------------------
# check_lowercase
# ---------------------------------------------------------------------------


def test_lowercase_passes_lowercase() -> None:
    issues = check_lowercase({"general": "blue hair, smile"})
    assert issues == []


def test_lowercase_catches_uppercase() -> None:
    issues = check_lowercase({"quality": "Masterpiece"})
    assert len(issues) == 1
    assert issues[0].rule == "UPPERCASE_TAG"
    assert issues[0].severity == "warning"
    assert issues[0].tag == "Masterpiece"


def test_lowercase_skips_natural_language() -> None:
    issues = check_lowercase({"natural_language": "She Is Walking."})
    assert issues == []


def test_lowercase_skips_character_field() -> None:
    issues = check_lowercase({"character": "Hatsune Miku"})
    assert issues == []


def test_lowercase_skips_series_field() -> None:
    issues = check_lowercase({"series": "Vocaloid"})
    assert issues == []


# ---------------------------------------------------------------------------
# check_underscore
# ---------------------------------------------------------------------------


def test_underscore_passes_no_underscore() -> None:
    issues = check_underscore({"general": "blue hair, cat ears"})
    assert issues == []


def test_underscore_catches_underscore_tag() -> None:
    issues = check_underscore({"general": "cat_ears"})
    assert len(issues) == 1
    assert issues[0].rule == "UNDERSCORE_TAG"
    assert issues[0].tag == "cat_ears"


def test_underscore_exempts_score_n() -> None:
    issues = check_underscore({"quality": "score_7"})
    assert issues == []


def test_underscore_exempts_score_n_up() -> None:
    issues = check_underscore({"quality": "score_7_up"})
    assert issues == []


def test_underscore_skips_natural_language_field() -> None:
    issues = check_underscore({"natural_language": "some_text here"})
    assert issues == []


# ---------------------------------------------------------------------------
# check_artist_at
# ---------------------------------------------------------------------------


def test_artist_at_passes_with_at() -> None:
    issues = check_artist_at({"artist": "@wlop, @kantoku"})
    assert issues == []


def test_artist_at_catches_missing_at() -> None:
    issues = check_artist_at({"artist": "@wlop, bad_artist"})
    assert len(issues) == 1
    assert issues[0].rule == "ARTIST_MISSING_AT"
    assert issues[0].severity == "error"
    assert issues[0].tag == "bad_artist"


def test_artist_at_empty_artist_no_issues() -> None:
    issues = check_artist_at({"artist": ""})
    assert issues == []


def test_artist_at_no_artist_key_no_issues() -> None:
    issues = check_artist_at({"general": "blue hair"})
    assert issues == []


# ---------------------------------------------------------------------------
# check_rating
# ---------------------------------------------------------------------------


def test_rating_passes_valid_values() -> None:
    for val in ("safe", "sensitive", "nsfw", "explicit"):
        assert check_rating({"rating": val}) == []


def test_rating_catches_invalid() -> None:
    issues = check_rating({"rating": "unknown"})
    assert len(issues) == 1
    assert issues[0].rule == "INVALID_RATING"
    assert issues[0].severity == "error"


def test_rating_catches_missing_key() -> None:
    issues = check_rating({})
    assert len(issues) == 1
    assert issues[0].rule == "INVALID_RATING"


# ---------------------------------------------------------------------------
# check_empty
# ---------------------------------------------------------------------------


def test_empty_detects_empty_string() -> None:
    issues = check_empty("")
    assert len(issues) == 1
    assert issues[0].rule == "EMPTY_PROMPT"
    assert issues[0].severity == "info"


def test_empty_passes_non_empty() -> None:
    assert check_empty("masterpiece") == []


def test_empty_whitespace_only_detected() -> None:
    assert len(check_empty("   ")) == 1


# ---------------------------------------------------------------------------
# check_long
# ---------------------------------------------------------------------------


def test_long_passes_short() -> None:
    assert check_long("x" * 3000) == []


def test_long_catches_over_3000() -> None:
    issues = check_long("x" * 3001)
    assert len(issues) == 1
    assert issues[0].rule == "LONG_PROMPT"
    assert issues[0].severity == "warning"


# ---------------------------------------------------------------------------
# check_duplicate
# ---------------------------------------------------------------------------


def test_duplicate_detects_same_tag_in_two_fields() -> None:
    fields = {"quality": "masterpiece", "general": "masterpiece, blue hair"}
    issues = check_duplicate(fields)
    assert any(i.rule == "DUPLICATE_TAG" for i in issues)


def test_duplicate_no_issues_unique_tags() -> None:
    fields = {"quality": "masterpiece", "general": "blue hair"}
    issues = check_duplicate(fields)
    assert issues == []


def test_duplicate_case_insensitive_normalization() -> None:
    fields = {"quality": "Masterpiece", "general": "masterpiece"}
    issues = check_duplicate(fields)
    assert any(i.rule == "DUPLICATE_TAG" for i in issues)


def test_duplicate_same_field_not_reported() -> None:
    # Same tag twice in same field should NOT be a cross-field duplicate.
    fields = {"general": "blue hair, blue hair"}
    issues = check_duplicate(fields)
    assert issues == []


# ---------------------------------------------------------------------------
# validate_fields (composite)
# ---------------------------------------------------------------------------


def test_validate_fields_returns_tuple() -> None:
    issues, length = validate_fields({"quality": "masterpiece", "rating": "safe"})
    assert isinstance(issues, list)
    assert isinstance(length, int)
    assert length >= 0


def test_validate_fields_empty_input_has_empty_prompt_issue() -> None:
    issues, length = validate_fields({})
    rules = {i.rule for i in issues}
    assert "EMPTY_PROMPT" in rules
    assert length == 0


def test_validate_fields_assembled_length_matches() -> None:
    from python.composer import join_fields

    fields = {"quality": "masterpiece", "rating": "safe", "count": "1girl"}
    expected_length = len(join_fields(fields))
    _, length = validate_fields(fields)
    assert length == expected_length


def test_validate_fields_null_values_treated_as_empty() -> None:
    # Should not raise; None values are coerced to "".
    issues, length = validate_fields({"quality": None, "rating": "safe"})  # type: ignore[arg-type]
    assert isinstance(issues, list)


def test_validate_fields_long_prompt_produces_long_prompt_issue() -> None:
    """validate_fields must surface LONG_PROMPT when assembled exceeds 3000 chars."""
    # Build a field value that, when assembled, exceeds 3000 chars.
    # "a" repeated 3001 times is a single token > 3000 chars.
    issues, length = validate_fields({"general": "a" * 3001, "rating": "safe"})
    rules = {i.rule for i in issues}
    assert "LONG_PROMPT" in rules
    assert length > 3000


# ---------------------------------------------------------------------------
# _is_exempt fullmatch safety (no substring bypass)
# ---------------------------------------------------------------------------


def test_underscore_exempt_does_not_match_superstring() -> None:
    """'bad_score_7_tag' must NOT be exempt — only 'score_7' should be."""
    from python.validators import check_underscore

    issues = check_underscore({"quality": "bad_score_7_tag"})
    # The token contains underscore and is NOT a bare score_N pattern.
    assert any(i.tag == "bad_score_7_tag" for i in issues), (
        "_is_exempt must use fullmatch, not search"
    )


# ---------------------------------------------------------------------------
# _strip_weight helper
# ---------------------------------------------------------------------------


def test_strip_weight_extracts_bare_tag() -> None:
    assert _strip_weight("(blonde hair:1.2)") == "blonde hair"


def test_strip_weight_passthrough_plain_tag() -> None:
    assert _strip_weight("blue eyes") == "blue eyes"


def test_strip_weight_passthrough_integer_weight() -> None:
    assert _strip_weight("(smile:2)") == "smile"


def test_strip_weight_passthrough_malformed() -> None:
    # No closing paren → treated as plain tag
    assert _strip_weight("(smile:1.2") == "(smile:1.2"


# ---------------------------------------------------------------------------
# check_lowercase — weighted tag exemption
# ---------------------------------------------------------------------------


def test_lowercase_weighted_uppercase_bare_tag_flagged() -> None:
    """(BlondeHair:1.2) should be flagged because the bare tag has uppercase."""
    issues = check_lowercase({"general": "(BlondeHair:1.2)"})
    assert len(issues) == 1
    assert issues[0].rule == "UPPERCASE_TAG"
    assert issues[0].tag == "(BlondeHair:1.2)"


def test_lowercase_weighted_lowercase_bare_tag_passes() -> None:
    """(blonde hair:1.2) should pass because the bare tag is all lowercase."""
    issues = check_lowercase({"general": "(blonde hair:1.2)"})
    assert issues == []


# ---------------------------------------------------------------------------
# check_underscore — weighted tag exemption
# ---------------------------------------------------------------------------


def test_underscore_weighted_tag_with_underscore_exempt() -> None:
    """(blonde_hair:1.2) must be exempt because the whole token matches the weight pattern."""
    issues = check_underscore({"general": "(blonde_hair:1.2)"})
    assert issues == [], f"Expected no issues but got: {issues}"


def test_underscore_weighted_tag_without_underscore_passes() -> None:
    """(blonde hair:1.2) has no underscore in the bare tag → no issue."""
    issues = check_underscore({"general": "(blonde hair:1.2)"})
    assert issues == []
