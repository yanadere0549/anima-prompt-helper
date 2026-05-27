"""Unit tests for the artist-pool API helpers in python/api/routes.py.

Exercises sanitisation and the save/load round-trip without an aiohttp server
(matching the style of test_api_health.py). Requires aiohttp to import the
routes module (CI installs it).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import python.api.routes as routes


# ---------------------------------------------------------------------------
# _sanitize_pool_payload
# ---------------------------------------------------------------------------


def test_sanitize_valid_pool():
    out = routes._sanitize_pool_payload(
        {"id": "my_pool", "label": "My Pool", "tags": ["@a", "@b"], "notes": "n"}
    )
    assert out == {
        "id": "my_pool",
        "label": "My Pool",
        "tags": ["@a", "@b"],
        "notes": "n",
        "user": True,
    }


def test_sanitize_trims_and_dedupes_tags():
    out = routes._sanitize_pool_payload(
        {"id": "p", "label": "L", "tags": ["@a", " @a ", "  ", "@B", "@b"]}
    )
    assert out["tags"] == ["@a", "@B"]


def test_sanitize_rejects_reserved_builtin_id():
    assert routes._sanitize_pool_payload(
        {"id": routes._DEFAULT_ARTIST_POOL_ID, "label": "x"}
    ) is None


def test_sanitize_rejects_bad_id():
    assert routes._sanitize_pool_payload({"id": "bad id!", "label": "x"}) is None
    assert routes._sanitize_pool_payload({"id": "", "label": "x"}) is None


def test_sanitize_rejects_empty_label():
    assert routes._sanitize_pool_payload({"id": "ok", "label": ""}) is None
    assert routes._sanitize_pool_payload({"id": "ok", "label": "   "}) is None


def test_sanitize_missing_tags_yields_empty_list():
    out = routes._sanitize_pool_payload({"id": "ok", "label": "L"})
    assert out["tags"] == []


def test_sanitize_caps_tag_count():
    many = [f"@artist_{i}" for i in range(routes._MAX_POOL_TAGS + 50)]
    out = routes._sanitize_pool_payload({"id": "ok", "label": "L", "tags": many})
    assert len(out["tags"]) == routes._MAX_POOL_TAGS


def test_sanitize_non_dict():
    assert routes._sanitize_pool_payload(None) is None
    assert routes._sanitize_pool_payload("x") is None
    assert routes._sanitize_pool_payload([1, 2]) is None


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


def test_save_load_round_trip(tmp_path, monkeypatch):
    target = tmp_path / "user_artist_pools.json"
    monkeypatch.setattr(routes, "_USER_ARTIST_POOLS_PATH", target)

    # Missing file -> empty shell.
    assert routes._load_user_artist_pools() == {"version": "1.0", "pools": []}

    data = {"version": "1.0", "pools": [{"id": "p1", "label": "P1", "tags": ["@a"]}]}
    routes._save_user_artist_pools(data)
    assert target.exists()

    loaded = routes._load_user_artist_pools()
    assert loaded["pools"][0]["id"] == "p1"
    assert loaded["pools"][0]["tags"] == ["@a"]


def test_load_corrupt_file_returns_empty_shell(tmp_path, monkeypatch):
    target = tmp_path / "user_artist_pools.json"
    target.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(routes, "_USER_ARTIST_POOLS_PATH", target)
    assert routes._load_user_artist_pools() == {"version": "1.0", "pools": []}


def test_default_pool_id_constant():
    assert routes._DEFAULT_ARTIST_POOL_ID == "default_highscore"
