"""Unit tests for AnimaSituationRandomizer node and python/situation_pool.py.

ComfyUI-independent; runs with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python import situation_pool as sp
from python.nodes import AnimaSituationRandomizer


# ---------------------------------------------------------------------------
# parse_pool
# ---------------------------------------------------------------------------


def test_parse_pool_basic():
    """parse_pool splits comma-separated tags into a list."""
    assert sp.parse_pool("outdoor, night sky, city lights") == [
        "outdoor",
        "night sky",
        "city lights",
    ]


def test_parse_pool_newlines_and_blanks():
    """parse_pool handles newlines and blank entries gracefully."""
    assert sp.parse_pool("outdoor,\nnight sky ,  , city lights\n") == [
        "outdoor",
        "night sky",
        "city lights",
    ]


def test_parse_pool_dedupes_case_insensitive():
    """parse_pool deduplicates case-insensitively, retaining first occurrence."""
    assert sp.parse_pool("Outdoor, outdoor, OUTDOOR") == ["Outdoor"]


def test_parse_pool_empty_and_nonstr():
    """parse_pool returns [] for empty, whitespace-only, None, or non-str input."""
    assert sp.parse_pool("") == []
    assert sp.parse_pool("   ") == []
    assert sp.parse_pool(None) == []  # type: ignore[arg-type]
    assert sp.parse_pool(123) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# pick_tags — determinism, sizing, edge cases
# ---------------------------------------------------------------------------

_POOL = ["outdoor", "night sky", "city lights", "forest", "beach"]


def test_pick_is_deterministic_for_same_seed():
    """Same pool + count + seed always yields the same result (reproducible)."""
    assert sp.pick_tags(_POOL, 3, 42) == sp.pick_tags(_POOL, 3, 42)


def test_pick_returns_requested_count():
    """pick_tags returns exactly count tags when count <= len(pool)."""
    assert len(sp.pick_tags(_POOL, 3, 7)) == 3


def test_pick_no_duplicates():
    """pick_tags never returns duplicate tags within one call."""
    picked = sp.pick_tags(_POOL, 5, 99)
    assert len(picked) == len(set(picked))


def test_pick_caps_at_pool_size():
    """pick_tags caps silently at pool size when count > len(pool)."""
    assert len(sp.pick_tags(_POOL, 100, 7)) == len(_POOL)


def test_pick_zero_or_negative_count():
    """pick_tags returns [] for count <= 0."""
    assert sp.pick_tags(_POOL, 0, 7) == []
    assert sp.pick_tags(_POOL, -3, 7) == []


def test_pick_empty_pool():
    """pick_tags returns [] when pool is empty, regardless of count."""
    assert sp.pick_tags([], 3, 7) == []


def test_pick_different_seeds_usually_differ():
    """Different seeds should produce at least two distinct orderings across 20 runs."""
    results = {tuple(sp.pick_tags(_POOL, 3, s)) for s in range(20)}
    assert len(results) > 1


def test_join_tags():
    """join_tags joins with ', ' by default; supports custom delimiter."""
    assert sp.join_tags(["outdoor", "night sky"]) == "outdoor, night sky"
    assert sp.join_tags([]) == ""
    assert sp.join_tags(["outdoor", "night sky"], " | ") == "outdoor | night sky"


# ---------------------------------------------------------------------------
# Built-in default pool
# ---------------------------------------------------------------------------


def test_default_pool_loads_and_nonempty():
    """load_default_pool returns a non-empty list of strings from the data file."""
    pool = sp.load_default_pool()
    assert isinstance(pool, list)
    assert len(pool) > 10  # the shipped situation pool has many tags
    assert all(isinstance(t, str) for t in pool[:20])


def test_default_pool_cache_returns_same_instance():
    """load_default_pool returns the same list object on repeated calls (cached)."""
    a = sp.load_default_pool()
    b = sp.load_default_pool()
    assert a is b


# ---------------------------------------------------------------------------
# Node class contract
# ---------------------------------------------------------------------------


def test_node_category_and_io():
    """AnimaSituationRandomizer declares expected category, function, and return types."""
    assert AnimaSituationRandomizer.CATEGORY == "Anima"
    assert AnimaSituationRandomizer.FUNCTION == "randomize"
    assert AnimaSituationRandomizer.RETURN_TYPES == ("STRING",)
    assert AnimaSituationRandomizer.RETURN_NAMES == ("situation_tags",)


def test_node_input_types():
    """INPUT_TYPES exposes count, seed, pool, picked with correct widget config."""
    schema = AnimaSituationRandomizer.INPUT_TYPES()
    req = schema["required"]
    assert set(req) == {"count", "seed", "pool", "picked"}
    assert req["count"][0] == "INT"
    assert req["seed"][0] == "INT"
    # seed must expose control_after_generate so re-queuing reshuffles
    assert req["seed"][1].get("control_after_generate") is True
    assert req["pool"][0] == "STRING"
    assert req["pool"][1].get("multiline") is True
    assert req["picked"][0] == "STRING"


# ---------------------------------------------------------------------------
# randomize() behaviour
# ---------------------------------------------------------------------------


def test_randomize_returns_picked_verbatim_when_present():
    """GUI path: non-empty picked is returned unchanged (output matches metadata)."""
    node = AnimaSituationRandomizer()
    out = node.randomize(2, 999, "outdoor, night sky, beach", picked="forest, city lights")
    assert out == ("forest, city lights",)


def test_randomize_ignores_blank_picked_and_falls_back():
    """Whitespace-only picked is treated as absent -> seeded selection from pool."""
    node = AnimaSituationRandomizer()
    out = node.randomize(1, 0, "outdoor", picked="   ")
    assert out == ("outdoor",)


def test_randomize_uses_explicit_pool_and_is_deterministic():
    """Two calls with same args (and no picked) return identical results."""
    node = AnimaSituationRandomizer()
    r1 = node.randomize(2, 123, "outdoor, night sky, beach")
    r2 = node.randomize(2, 123, "outdoor, night sky, beach")
    assert r1 == r2
    assert isinstance(r1, tuple) and isinstance(r1[0], str)
    picked = [t.strip() for t in r1[0].split(",")]
    assert len(picked) == 2
    assert set(picked) <= {"outdoor", "night sky", "beach"}


def test_randomize_falls_back_to_default_pool_when_empty():
    """Empty pool causes fallback to built-in default pool (returns non-empty result)."""
    node = AnimaSituationRandomizer()
    out = node.randomize(3, 5, "")
    assert out[0]
    assert len(out[0].split(",")) == 3


def test_randomize_empty_pool_and_no_default(monkeypatch):
    """When pool is empty and default pool is unavailable, returns empty string."""
    monkeypatch.setattr(sp, "load_default_pool", lambda: [])
    node = AnimaSituationRandomizer()
    assert node.randomize(3, 1, "") == ("",)


def test_randomize_count_one():
    """count=1 returns a single tag with no comma."""
    node = AnimaSituationRandomizer()
    out = node.randomize(1, 0, "outdoor, night sky")
    assert "," not in out[0]
    assert out[0] in ("outdoor", "night sky")
