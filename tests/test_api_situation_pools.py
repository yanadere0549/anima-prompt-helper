"""Unit tests for the situation-pool API helpers in python/api/routes.py.

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
# _sanitize_situation_pool_payload
# ---------------------------------------------------------------------------


def test_sanitize_situation_pool_valid():
    """Valid situation pool payload is sanitized and normalized correctly."""
    out = routes._sanitize_situation_pool_payload(
        {"id": "my_situations", "label": "My Situations", "tags": ["outdoor", "night sky"], "notes": "n"}
    )
    assert out == {
        "id": "my_situations",
        "label": "My Situations",
        "tags": ["outdoor", "night sky"],
        "notes": "n",
        "user": True,
    }


def test_sanitize_situation_pool_trims_and_dedupes_tags():
    """Tags are trimmed and deduplicated case-insensitively."""
    out = routes._sanitize_situation_pool_payload(
        {"id": "p", "label": "L", "tags": ["outdoor", " outdoor ", "  ", "Beach", "beach"]}
    )
    assert out["tags"] == ["outdoor", "Beach"]


def test_sanitize_situation_pool_rejects_reserved_builtin_id():
    """Reserved built-in id (default_danbooru_situations) must be rejected."""
    assert routes._sanitize_situation_pool_payload(
        {"id": routes._DEFAULT_SITUATION_POOL_ID, "label": "x"}
    ) is None


def test_sanitize_situation_pool_non_reserved_id_is_accepted():
    """A non-reserved custom id must be accepted."""
    out = routes._sanitize_situation_pool_payload({"id": "my_custom_situations", "label": "My Pool"})
    assert out is not None
    assert out["id"] == "my_custom_situations"


def test_sanitize_situation_pool_rejects_bad_id():
    """Ids with spaces or special chars, or empty strings, are rejected."""
    assert routes._sanitize_situation_pool_payload({"id": "bad id!", "label": "x"}) is None
    assert routes._sanitize_situation_pool_payload({"id": "", "label": "x"}) is None


def test_sanitize_situation_pool_rejects_empty_label():
    """Empty or whitespace-only label is rejected."""
    assert routes._sanitize_situation_pool_payload({"id": "ok", "label": ""}) is None
    assert routes._sanitize_situation_pool_payload({"id": "ok", "label": "   "}) is None


def test_sanitize_situation_pool_missing_tags_yields_empty_list():
    """Omitting tags field results in an empty tags list (not an error)."""
    out = routes._sanitize_situation_pool_payload({"id": "ok", "label": "L"})
    assert out["tags"] == []


def test_sanitize_situation_pool_caps_tag_count():
    """Tags list is capped at _MAX_POOL_TAGS."""
    many = [f"situation_{i}" for i in range(routes._MAX_POOL_TAGS + 50)]
    out = routes._sanitize_situation_pool_payload({"id": "ok", "label": "L", "tags": many})
    assert len(out["tags"]) == routes._MAX_POOL_TAGS


def test_sanitize_situation_pool_non_dict():
    """Non-dict inputs (None, str, list) all return None."""
    assert routes._sanitize_situation_pool_payload(None) is None
    assert routes._sanitize_situation_pool_payload("x") is None
    assert routes._sanitize_situation_pool_payload([1, 2]) is None


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


def test_situation_pool_save_load_round_trip(tmp_path, monkeypatch):
    """Saved situation pools can be read back with identical content."""
    target = tmp_path / "user_situation_pools.json"
    monkeypatch.setattr(routes, "_USER_SITUATION_POOLS_PATH", target)

    # Missing file -> empty shell.
    assert routes._load_user_situation_pools() == {"version": "1.0", "pools": []}

    data = {"version": "1.0", "pools": [{"id": "p1", "label": "P1", "tags": ["outdoor"]}]}
    routes._save_user_situation_pools(data)
    assert target.exists()

    loaded = routes._load_user_situation_pools()
    assert loaded["pools"][0]["id"] == "p1"
    assert loaded["pools"][0]["tags"] == ["outdoor"]


def test_situation_pool_load_corrupt_file_returns_empty_shell(tmp_path, monkeypatch):
    """Corrupted JSON file is handled gracefully — returns empty shell."""
    target = tmp_path / "user_situation_pools.json"
    target.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(routes, "_USER_SITUATION_POOLS_PATH", target)
    assert routes._load_user_situation_pools() == {"version": "1.0", "pools": []}


def test_default_situation_pool_id_constant():
    """_DEFAULT_SITUATION_POOL_ID has the expected value."""
    assert routes._DEFAULT_SITUATION_POOL_ID == "default_danbooru_situations"
