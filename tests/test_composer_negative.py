"""Unit tests for join_negative_fields() in python/composer.py.

These tests are ComfyUI-independent and run with plain pytest.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow importing python package without installing ComfyUI.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import python.composer as _composer_module
from python.composer import join_negative_fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_negative_cache() -> None:
    """Reset the lazy-load cache so each test that needs fresh loading can do so."""
    _composer_module._negative_cache = None
    _composer_module._negative_cache_loaded = False


_FULL_NEG_FIELDS: dict[str, str] = {
    "quality_negative": "worst quality, low quality",
    "score_negative": "score_1, score_2, score_3",
    "style_negative": "artifacts, blurry",
    "content_negative": "nsfw",
    "meta_negative": "watermark, signature",
    "extra_negative": "text",
}


# ---------------------------------------------------------------------------
# 1. anima_base_default preset returns exact anima_base default_negative
# ---------------------------------------------------------------------------

def test_preset_anima_base_default_returns_exact_string() -> None:
    """Preset anima_base_default must return the anima_base default_negative exactly."""
    result = join_negative_fields({}, preset="anima_base_default")
    # The value loaded from anima_spec.json (or fallback)
    expected = _composer_module._load_negative_defaults()["anima_base"]
    assert result == expected


# ---------------------------------------------------------------------------
# 2. ooo_anima_default preset returns exact ooo_anima default_negative
# ---------------------------------------------------------------------------

def test_preset_ooo_anima_default_returns_exact_string() -> None:
    """Preset ooo_anima_default must return the ooo_anima default_negative exactly."""
    result = join_negative_fields({}, preset="ooo_anima_default")
    expected = _composer_module._load_negative_defaults()["ooo_anima"]
    assert result == expected


# ---------------------------------------------------------------------------
# 3. preset == "none" with all fields populated joins in order
# ---------------------------------------------------------------------------

def test_preset_none_joins_all_fields_in_order() -> None:
    """preset none must join all 6 fields in canonical order."""
    result = join_negative_fields(_FULL_NEG_FIELDS, preset="none")
    # All tokens present
    for token in ["worst quality", "low quality", "score_1", "artifacts", "blurry",
                  "nsfw", "watermark", "signature", "text"]:
        assert token in result, f"Token '{token}' missing from result: {result!r}"

    # Canonical order: quality_negative < score_negative < style_negative < content_negative < meta_negative < extra_negative
    idx_quality = result.index("worst quality")
    idx_score = result.index("score_1")
    idx_style = result.index("artifacts")
    idx_content = result.index("nsfw")
    idx_meta = result.index("watermark")
    idx_extra = result.index("text")
    assert idx_quality < idx_score < idx_style < idx_content < idx_meta < idx_extra


# ---------------------------------------------------------------------------
# 4. preset == "custom" behaves identically to "none"
# ---------------------------------------------------------------------------

def test_preset_custom_identical_to_none() -> None:
    """preset custom must join fields, not override them."""
    result_none = join_negative_fields(_FULL_NEG_FIELDS, preset="none")
    result_custom = join_negative_fields(_FULL_NEG_FIELDS, preset="custom")
    assert result_none == result_custom


# ---------------------------------------------------------------------------
# 5. ooo_anima_default with user fields still returns only preset default
# ---------------------------------------------------------------------------

def test_preset_ooo_anima_shadows_all_user_fields() -> None:
    """ooo_anima_default must ignore user-supplied field values."""
    result = join_negative_fields(_FULL_NEG_FIELDS, preset="ooo_anima_default")
    expected = _composer_module._load_negative_defaults()["ooo_anima"]
    assert result == expected
    # User-only tokens that are NOT in the preset should not appear
    # (watermark, signature are not in ooo_anima default)
    assert "watermark" not in result


# ---------------------------------------------------------------------------
# 6. Empty fields + preset == "none" returns empty string
# ---------------------------------------------------------------------------

def test_empty_fields_preset_none_returns_empty() -> None:
    """All-empty fields with preset none must produce empty string."""
    result = join_negative_fields({}, preset="none")
    assert result == ""


def test_empty_string_fields_preset_none_returns_empty() -> None:
    """Fields explicitly set to empty strings must produce empty string."""
    empty_fields = {k: "" for k in _FULL_NEG_FIELDS}
    result = join_negative_fields(empty_fields, preset="none")
    assert result == ""


# ---------------------------------------------------------------------------
# 7. Long prompt > 3000 chars logs a warning (via the node's compose_negative)
# ---------------------------------------------------------------------------

def test_long_prompt_logs_warning(caplog: object) -> None:
    """A negative prompt > 3000 chars must trigger a WARNING log in the node."""
    from python.nodes import AnimaNegativePromptComposer
    node = AnimaNegativePromptComposer()
    long_str = "bad token, " * 300  # well over 3000 chars
    with caplog.at_level(logging.WARNING, logger="python.nodes"):
        result = node.compose_negative(
            quality_negative=long_str,
            score_negative="",
            style_negative="",
            content_negative="",
            meta_negative="",
            extra_negative="",
            negative_preset="none",
        )
    assert len(result[0]) > 3000
    assert any("3000" in r.message for r in caplog.records), (
        f"Expected long-prompt warning; got records: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# 8. Dedup empty tokens (e.g. "a,,b" → "a, b")
# ---------------------------------------------------------------------------

def test_dedup_empty_tokens_between_commas() -> None:
    """Double commas (empty tokens) must be stripped."""
    result = join_negative_fields({"style_negative": "a,,b"}, preset="none")
    assert ",," not in result
    assert result == "a, b"


def test_dedup_trailing_comma() -> None:
    """Trailing comma must not produce a trailing empty token."""
    result = join_negative_fields({"quality_negative": "worst quality,"}, preset="none")
    assert not result.endswith(",")
    assert result == "worst quality"


# ---------------------------------------------------------------------------
# Return-type guarantees
# ---------------------------------------------------------------------------

def test_returns_str_type() -> None:
    result = join_negative_fields({})
    assert isinstance(result, str)


def test_returns_non_none() -> None:
    assert join_negative_fields({}) is not None


def test_preset_returns_str_type() -> None:
    result = join_negative_fields({}, preset="ooo_anima_default")
    assert isinstance(result, str)
    assert result is not None


# ---------------------------------------------------------------------------
# Fallback behaviour when spec file is missing
# ---------------------------------------------------------------------------

def test_fallback_when_spec_missing(monkeypatch, tmp_path) -> None:
    """When anima_spec.json is missing, hardcoded fallback values are returned."""
    _reset_negative_cache()
    # Patch Path to a non-existent file
    import python.composer as cm
    original_file = cm.__file__

    # Override _load_negative_defaults to point at a nonexistent path
    def _patched_load():
        import json
        from pathlib import Path
        nonexistent = tmp_path / "nonexistent_spec.json"
        try:
            with nonexistent.open(encoding="utf-8") as fh:
                spec = json.load(fh)
        except FileNotFoundError:
            return dict(cm._NEGATIVE_FALLBACK)

    monkeypatch.setattr(cm, "_load_negative_defaults", _patched_load)
    monkeypatch.setattr(cm, "_negative_cache_loaded", False)
    monkeypatch.setattr(cm, "_negative_cache", None)

    result = join_negative_fields({}, preset="anima_base_default")
    assert result == cm._NEGATIVE_FALLBACK["anima_base"]

    result2 = join_negative_fields({}, preset="ooo_anima_default")
    assert result2 == cm._NEGATIVE_FALLBACK["ooo_anima"]

    # Restore
    monkeypatch.undo()
    _reset_negative_cache()
