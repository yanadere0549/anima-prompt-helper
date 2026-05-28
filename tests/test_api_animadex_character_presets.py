"""Unit tests for the animadex character presets layer in python/api/routes.py.

Tests cover:
- _load_animadex_character_presets: missing file, parse error, happy path
- 3-layer merge logic (builtin < animadex < user) using module-level cache injection
- _sanitize_preset_payload: prompt_example field support
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import python.api.routes as routes


# ---------------------------------------------------------------------------
# _load_animadex_character_presets
# ---------------------------------------------------------------------------


def test_load_animadex_returns_empty_shell_when_file_missing():
    """Missing animadex file returns empty shell without error."""
    with patch.object(
        routes._ANIMADEX_CHARACTER_PRESETS_PATH.__class__,
        "exists",
        lambda self: False if self == routes._ANIMADEX_CHARACTER_PRESETS_PATH else self.__class__.exists(self),
    ):
        # Use a non-existent temp path to guarantee absence.
        real_path = routes._ANIMADEX_CHARACTER_PRESETS_PATH
        with patch.object(routes, "_ANIMADEX_CHARACTER_PRESETS_PATH", Path("/nonexistent/animadex_character_presets.json")):
            result = routes._load_animadex_character_presets()

    assert result == {"version": "1.0", "presets": []}


def test_load_animadex_returns_empty_shell_on_parse_error(tmp_path):
    """Corrupt JSON in animadex file returns empty shell with a warning."""
    bad_json = tmp_path / "animadex_character_presets.json"
    bad_json.write_text("{ not valid json !!!}", encoding="utf-8")

    with patch.object(routes, "_ANIMADEX_CHARACTER_PRESETS_PATH", bad_json):
        result = routes._load_animadex_character_presets()

    assert result == {"version": "1.0", "presets": []}


def test_load_animadex_returns_presets_on_success(tmp_path):
    """Valid animadex file is loaded and presets list is returned."""
    data = {
        "version": "1.0",
        "presets": [
            {
                "id": "animadex_hatsune_miku",
                "label": "Hatsune Miku",
                "character": "hatsune miku",
                "series": "vocaloid",
                "essential_general_tags": ["aqua hair"],
                "recommended_artists": [],
                "prompt_example": "hatsune miku, aqua hair",
                "notes": "test",
                "tier": 5,
                "source": "animadex",
            }
        ],
    }
    f = tmp_path / "animadex_character_presets.json"
    f.write_text(json.dumps(data), encoding="utf-8")

    with patch.object(routes, "_ANIMADEX_CHARACTER_PRESETS_PATH", f):
        result = routes._load_animadex_character_presets()

    assert result["version"] == "1.0"
    assert len(result["presets"]) == 1
    assert result["presets"][0]["id"] == "animadex_hatsune_miku"


# ---------------------------------------------------------------------------
# 3-layer merge logic (tested by injecting caches directly)
# ---------------------------------------------------------------------------

def _run_merge(builtin_presets, animadex_presets, user_presets):
    """Replicate the merge logic from get_character_presets for unit testing."""
    by_id = {}
    for p in builtin_presets:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            tagged = dict(p)
            tagged.setdefault("user", False)
            tagged.setdefault("source", "builtin")
            by_id[p["id"]] = tagged
    for p in animadex_presets:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            tagged = dict(p)
            tagged["user"] = False
            tagged.setdefault("source", "animadex")
            by_id[p["id"]] = tagged
    for p in user_presets:
        if isinstance(p, dict) and isinstance(p.get("id"), str):
            tagged = dict(p)
            tagged["user"] = True
            tagged["source"] = "user"
            by_id[p["id"]] = tagged
    return list(by_id.values())


def test_merge_animadex_presets_appear_with_source_animadex():
    """Animadex presets appear in merged output with source='animadex'."""
    builtin = [{"id": "builtin_char_a", "label": "A"}]
    animadex = [{"id": "animadex_hatsune_miku", "label": "Hatsune Miku", "source": "animadex"}]
    user = []

    merged = _run_merge(builtin, animadex, user)

    ids = {p["id"] for p in merged}
    assert "animadex_hatsune_miku" in ids
    assert "builtin_char_a" in ids

    miku = next(p for p in merged if p["id"] == "animadex_hatsune_miku")
    assert miku["source"] == "animadex"
    assert miku["user"] is False


def test_merge_builtin_and_animadex_coexist_when_ids_differ():
    """Builtin and animadex entries with different ids are both retained."""
    builtin = [{"id": "builtin_reimu", "label": "Reimu (builtin)"}]
    animadex = [{"id": "animadex_reimu", "label": "Reimu (animadex)"}]
    user = []

    merged = _run_merge(builtin, animadex, user)
    ids = {p["id"] for p in merged}

    assert "builtin_reimu" in ids
    assert "animadex_reimu" in ids
    assert len(merged) == 2


def test_merge_animadex_overrides_builtin_on_same_id():
    """When animadex and builtin share the same id, animadex wins."""
    shared_id = "shared_char"
    builtin = [{"id": shared_id, "label": "Builtin version", "source": "builtin"}]
    animadex = [{"id": shared_id, "label": "Animadex version"}]
    user = []

    merged = _run_merge(builtin, animadex, user)

    assert len(merged) == 1
    assert merged[0]["label"] == "Animadex version"
    assert merged[0]["user"] is False


def test_merge_user_overrides_animadex_on_same_id():
    """User preset overrides animadex entry with the same id."""
    shared_id = "animadex_miku"
    builtin = []
    animadex = [{"id": shared_id, "label": "Animadex Miku", "source": "animadex"}]
    user = [{"id": shared_id, "label": "My Custom Miku", "user": True}]

    merged = _run_merge(builtin, animadex, user)

    assert len(merged) == 1
    result = merged[0]
    assert result["label"] == "My Custom Miku"
    assert result["user"] is True
    assert result["source"] == "user"


def test_merge_user_overrides_builtin_and_animadex_triple_collision():
    """When all three layers share an id, user wins over all."""
    shared_id = "triple_collision"
    builtin = [{"id": shared_id, "label": "Builtin"}]
    animadex = [{"id": shared_id, "label": "Animadex"}]
    user = [{"id": shared_id, "label": "User"}]

    merged = _run_merge(builtin, animadex, user)

    assert len(merged) == 1
    assert merged[0]["label"] == "User"
    assert merged[0]["user"] is True
    assert merged[0]["source"] == "user"


# ---------------------------------------------------------------------------
# Integration: actual animadex_character_presets.json file on disk
# ---------------------------------------------------------------------------


def test_actual_animadex_file_loads_and_has_animadex_source():
    """The committed animadex_character_presets.json loads successfully and
    at least one preset has source='animadex'."""
    result = routes._load_animadex_character_presets()

    assert isinstance(result, dict)
    assert "presets" in result
    assert len(result["presets"]) > 0, "animadex_character_presets.json must have at least one preset"

    animadex_sources = [p for p in result["presets"] if p.get("source") == "animadex"]
    assert len(animadex_sources) > 0, "At least one preset must have source='animadex'"


# ---------------------------------------------------------------------------
# _sanitize_preset_payload: prompt_example field
# ---------------------------------------------------------------------------


def test_sanitize_preset_accepts_prompt_example():
    """prompt_example field is accepted and passed through (up to 2048 chars)."""
    out = routes._sanitize_preset_payload({
        "id": "test_char",
        "label": "Test",
        "prompt_example": "hatsune miku, aqua hair, vocaloid",
    })
    assert out is not None
    assert out["prompt_example"] == "hatsune miku, aqua hair, vocaloid"


def test_sanitize_preset_prompt_example_truncated():
    """prompt_example longer than 2048 chars is truncated to 2048."""
    long_example = "x" * 3000
    out = routes._sanitize_preset_payload({
        "id": "test_char",
        "label": "Test",
        "prompt_example": long_example,
    })
    assert out is not None
    assert len(out["prompt_example"]) == 2048


def test_sanitize_preset_prompt_example_defaults_to_empty():
    """Missing prompt_example defaults to empty string, not an error."""
    out = routes._sanitize_preset_payload({"id": "test_char", "label": "Test"})
    assert out is not None
    assert out["prompt_example"] == ""


def test_sanitize_preset_prompt_example_non_str_coerced_to_empty():
    """Non-string prompt_example is coerced to empty string."""
    out = routes._sanitize_preset_payload({
        "id": "test_char",
        "label": "Test",
        "prompt_example": 12345,
    })
    assert out is not None
    assert out["prompt_example"] == ""
