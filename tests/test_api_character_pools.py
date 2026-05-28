"""Unit tests for the character-pool API helpers in python/api/routes.py.

Exercises sanitisation and the save/load round-trip without an aiohttp server
(matching the style of test_api_artist_pools.py). Requires aiohttp to import the
routes module (CI installs it).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import python.api.routes as routes


# ---------------------------------------------------------------------------
# _sanitize_character_pool_payload
# ---------------------------------------------------------------------------


def test_sanitize_character_pool_valid():
    """Valid character pool payload is sanitized and normalized correctly."""
    out = routes._sanitize_character_pool_payload(
        {"id": "my_chars", "label": "My Characters", "tags": ["hatsune miku", "asuka"], "notes": "n"}
    )
    assert out == {
        "id": "my_chars",
        "label": "My Characters",
        "tags": ["hatsune miku", "asuka"],
        "notes": "n",
        "user": True,
    }


def test_sanitize_character_pool_trims_and_dedupes_tags():
    """Tags are trimmed and deduplicated case-insensitively."""
    out = routes._sanitize_character_pool_payload(
        {"id": "p", "label": "L", "tags": ["hatsune miku", " hatsune miku ", "  ", "Asuka", "asuka"]}
    )
    assert out["tags"] == ["hatsune miku", "Asuka"]


def test_sanitize_character_pool_rejects_reserved_builtin_id():
    """Reserved built-in id (default_animadex_1girl) must be rejected."""
    assert routes._sanitize_character_pool_payload(
        {"id": routes._DEFAULT_CHARACTER_POOL_ID, "label": "x"}
    ) is None


def test_sanitize_character_pool_non_reserved_id_is_accepted():
    """A non-reserved custom id must be accepted."""
    out = routes._sanitize_character_pool_payload({"id": "my_custom_pool", "label": "My Pool"})
    assert out is not None
    assert out["id"] == "my_custom_pool"


def test_sanitize_character_pool_rejects_bad_id():
    """Ids with spaces or special chars, or empty strings, are rejected."""
    assert routes._sanitize_character_pool_payload({"id": "bad id!", "label": "x"}) is None
    assert routes._sanitize_character_pool_payload({"id": "", "label": "x"}) is None


def test_sanitize_character_pool_rejects_empty_label():
    """Empty or whitespace-only label is rejected."""
    assert routes._sanitize_character_pool_payload({"id": "ok", "label": ""}) is None
    assert routes._sanitize_character_pool_payload({"id": "ok", "label": "   "}) is None


def test_sanitize_character_pool_missing_tags_yields_empty_list():
    """Omitting tags field results in an empty tags list (not an error)."""
    out = routes._sanitize_character_pool_payload({"id": "ok", "label": "L"})
    assert out["tags"] == []


def test_sanitize_character_pool_caps_tag_count():
    """Tags list is capped at _MAX_POOL_TAGS."""
    many = [f"char_{i}" for i in range(routes._MAX_POOL_TAGS + 50)]
    out = routes._sanitize_character_pool_payload({"id": "ok", "label": "L", "tags": many})
    assert len(out["tags"]) == routes._MAX_POOL_TAGS


def test_sanitize_character_pool_non_dict():
    """Non-dict inputs (None, str, list) all return None."""
    assert routes._sanitize_character_pool_payload(None) is None
    assert routes._sanitize_character_pool_payload("x") is None
    assert routes._sanitize_character_pool_payload([1, 2]) is None


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


def test_character_pool_save_load_round_trip(tmp_path, monkeypatch):
    """Saved character pools can be read back with identical content."""
    target = tmp_path / "user_character_pools.json"
    monkeypatch.setattr(routes, "_USER_CHARACTER_POOLS_PATH", target)

    # Missing file -> empty shell.
    assert routes._load_user_character_pools() == {"version": "1.0", "pools": []}

    data = {"version": "1.0", "pools": [{"id": "p1", "label": "P1", "tags": ["hatsune miku"]}]}
    routes._save_user_character_pools(data)
    assert target.exists()

    loaded = routes._load_user_character_pools()
    assert loaded["pools"][0]["id"] == "p1"
    assert loaded["pools"][0]["tags"] == ["hatsune miku"]


def test_character_pool_load_corrupt_file_returns_empty_shell(tmp_path, monkeypatch):
    """Corrupted JSON file is handled gracefully — returns empty shell."""
    target = tmp_path / "user_character_pools.json"
    target.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(routes, "_USER_CHARACTER_POOLS_PATH", target)
    assert routes._load_user_character_pools() == {"version": "1.0", "pools": []}


def test_default_character_pool_id_constant():
    """_DEFAULT_CHARACTER_POOL_ID has the expected value."""
    assert routes._DEFAULT_CHARACTER_POOL_ID == "default_animadex_1girl"
