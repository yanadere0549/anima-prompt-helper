"""Unit tests for AnimaArtistRandomizer node and python/artist_pool.py.

ComfyUI-independent; runs with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python import artist_pool as ap
from python.nodes import AnimaArtistRandomizer


# ---------------------------------------------------------------------------
# parse_pool
# ---------------------------------------------------------------------------


def test_parse_pool_basic():
    assert ap.parse_pool("@a, @b, @c") == ["@a", "@b", "@c"]


def test_parse_pool_newlines_and_blanks():
    assert ap.parse_pool("@a,\n@b ,  , @c\n") == ["@a", "@b", "@c"]


def test_parse_pool_dedupes_case_insensitive():
    assert ap.parse_pool("@Dairi, @dairi, @DAIRI") == ["@Dairi"]


def test_parse_pool_empty_and_nonstr():
    assert ap.parse_pool("") == []
    assert ap.parse_pool("   ") == []
    assert ap.parse_pool(None) == []  # type: ignore[arg-type]
    assert ap.parse_pool(123) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# pick_artists — determinism, sizing, edge cases
# ---------------------------------------------------------------------------

_POOL = ["@a", "@b", "@c", "@d", "@e"]


def test_pick_is_deterministic_for_same_seed():
    assert ap.pick_artists(_POOL, 3, 42) == ap.pick_artists(_POOL, 3, 42)


def test_pick_returns_requested_count():
    assert len(ap.pick_artists(_POOL, 3, 7)) == 3


def test_pick_no_duplicates():
    picked = ap.pick_artists(_POOL, 5, 99)
    assert len(picked) == len(set(picked))


def test_pick_caps_at_pool_size():
    assert len(ap.pick_artists(_POOL, 100, 7)) == len(_POOL)


def test_pick_zero_or_negative_count():
    assert ap.pick_artists(_POOL, 0, 7) == []
    assert ap.pick_artists(_POOL, -3, 7) == []


def test_pick_empty_pool():
    assert ap.pick_artists([], 3, 7) == []


def test_pick_different_seeds_usually_differ():
    # Across many seeds, at least one ordering must differ (sanity, not strict).
    results = {tuple(ap.pick_artists(_POOL, 3, s)) for s in range(20)}
    assert len(results) > 1


def test_join_artists():
    assert ap.join_artists(["@a", "@b"]) == "@a, @b"
    assert ap.join_artists([]) == ""
    assert ap.join_artists(["@a", "@b"], " | ") == "@a | @b"


# ---------------------------------------------------------------------------
# Built-in default pool
# ---------------------------------------------------------------------------


def test_default_pool_loads_and_nonempty():
    pool = ap.load_default_pool()
    assert isinstance(pool, list)
    assert len(pool) > 100  # the shipped high-score pool is sizeable
    assert all(isinstance(t, str) and t.startswith("@") for t in pool[:50])


# ---------------------------------------------------------------------------
# Node class contract
# ---------------------------------------------------------------------------


def test_node_category_and_io():
    assert AnimaArtistRandomizer.CATEGORY == "Anima"
    assert AnimaArtistRandomizer.FUNCTION == "randomize"
    assert AnimaArtistRandomizer.RETURN_TYPES == ("STRING",)
    assert AnimaArtistRandomizer.RETURN_NAMES == ("artist_tags",)


def test_node_input_types():
    schema = AnimaArtistRandomizer.INPUT_TYPES()
    req = schema["required"]
    assert set(req) == {"count", "seed", "pool", "picked"}
    assert req["count"][0] == "INT"
    assert req["seed"][0] == "INT"
    # seed must expose the control_after_generate combo so re-queuing reshuffles
    assert req["seed"][1].get("control_after_generate") is True
    assert req["pool"][0] == "STRING"
    assert req["pool"][1].get("multiline") is True
    assert req["picked"][0] == "STRING"


def test_randomize_returns_picked_verbatim_when_present():
    """GUI path: a pre-populated ``picked`` value is returned unchanged,
    regardless of count / seed / pool (so output matches image metadata)."""
    node = AnimaArtistRandomizer()
    out = node.randomize(2, 999, "@a, @b, @c", picked="@chosen_one, @and_two")
    assert out == ("@chosen_one, @and_two",)


def test_randomize_ignores_blank_picked_and_falls_back():
    """Whitespace-only ``picked`` is treated as absent -> seeded selection."""
    node = AnimaArtistRandomizer()
    out = node.randomize(1, 0, "@only", picked="   ")
    assert out == ("@only",)


# ---------------------------------------------------------------------------
# randomize() behaviour
# ---------------------------------------------------------------------------


def test_randomize_uses_explicit_pool_and_is_deterministic():
    node = AnimaArtistRandomizer()
    r1 = node.randomize(2, 123, "@x, @y, @z")
    r2 = node.randomize(2, 123, "@x, @y, @z")
    assert r1 == r2
    assert isinstance(r1, tuple) and isinstance(r1[0], str)
    picked = [t.strip() for t in r1[0].split(",")]
    assert len(picked) == 2
    assert set(picked) <= {"@x", "@y", "@z"}


def test_randomize_falls_back_to_default_pool_when_empty():
    node = AnimaArtistRandomizer()
    out = node.randomize(3, 5, "")
    assert out[0]
    assert len(out[0].split(",")) == 3


def test_randomize_empty_pool_and_no_default(monkeypatch):
    """When pool is empty and the default pool is unavailable -> empty string."""
    monkeypatch.setattr(ap, "load_default_pool", lambda: [])
    node = AnimaArtistRandomizer()
    assert node.randomize(3, 1, "") == ("",)


def test_randomize_count_one():
    node = AnimaArtistRandomizer()
    out = node.randomize(1, 0, "@only_a, @only_b")
    assert "," not in out[0]
    assert out[0] in ("@only_a", "@only_b")
