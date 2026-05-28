"""Unit tests for AnimaCharacterRandomizer node and python/character_pool.py.

ComfyUI-independent; runs with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python import character_pool as cp
from python.nodes import AnimaCharacterRandomizer


# ---------------------------------------------------------------------------
# parse_pool
# ---------------------------------------------------------------------------


def test_parse_pool_basic():
    """parse_pool splits comma-separated tags into a list."""
    assert cp.parse_pool("hatsune miku, hakurei reimu, asuka") == [
        "hatsune miku",
        "hakurei reimu",
        "asuka",
    ]


def test_parse_pool_newlines_and_blanks():
    """parse_pool handles newlines and blank entries gracefully."""
    assert cp.parse_pool("hatsune miku,\nhakurei reimu ,  , asuka\n") == [
        "hatsune miku",
        "hakurei reimu",
        "asuka",
    ]


def test_parse_pool_dedupes_case_insensitive():
    """parse_pool deduplicates case-insensitively, retaining first occurrence."""
    assert cp.parse_pool("Miku, miku, MIKU") == ["Miku"]


def test_parse_pool_empty_and_nonstr():
    """parse_pool returns [] for empty, whitespace-only, None, or non-str input."""
    assert cp.parse_pool("") == []
    assert cp.parse_pool("   ") == []
    assert cp.parse_pool(None) == []  # type: ignore[arg-type]
    assert cp.parse_pool(123) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# pick_tags — determinism, sizing, edge cases
# ---------------------------------------------------------------------------

_POOL = ["hatsune miku", "hakurei reimu", "asuka", "rei ayanami", "misato"]


def test_pick_is_deterministic_for_same_seed():
    """Same pool + count + seed always yields the same result (reproducible)."""
    assert cp.pick_tags(_POOL, 3, 42) == cp.pick_tags(_POOL, 3, 42)


def test_pick_returns_requested_count():
    """pick_tags returns exactly count tags when count <= len(pool)."""
    assert len(cp.pick_tags(_POOL, 3, 7)) == 3


def test_pick_no_duplicates():
    """pick_tags never returns duplicate tags within one call."""
    picked = cp.pick_tags(_POOL, 5, 99)
    assert len(picked) == len(set(picked))


def test_pick_caps_at_pool_size():
    """pick_tags caps silently at pool size when count > len(pool)."""
    assert len(cp.pick_tags(_POOL, 100, 7)) == len(_POOL)


def test_pick_zero_or_negative_count():
    """pick_tags returns [] for count <= 0."""
    assert cp.pick_tags(_POOL, 0, 7) == []
    assert cp.pick_tags(_POOL, -3, 7) == []


def test_pick_empty_pool():
    """pick_tags returns [] when pool is empty, regardless of count."""
    assert cp.pick_tags([], 3, 7) == []


def test_pick_different_seeds_usually_differ():
    """Different seeds should produce at least two distinct orderings across 20 runs."""
    results = {tuple(cp.pick_tags(_POOL, 3, s)) for s in range(20)}
    assert len(results) > 1


def test_join_tags():
    """join_tags joins with ', ' by default; supports custom delimiter."""
    assert cp.join_tags(["hatsune miku", "asuka"]) == "hatsune miku, asuka"
    assert cp.join_tags([]) == ""
    assert cp.join_tags(["hatsune miku", "asuka"], " | ") == "hatsune miku | asuka"


# ---------------------------------------------------------------------------
# Built-in default pool
# ---------------------------------------------------------------------------


def test_default_pool_loads_and_nonempty():
    """load_default_pool returns a non-empty list of strings from the data file."""
    pool = cp.load_default_pool()
    assert isinstance(pool, list)
    assert len(pool) > 100  # the shipped character pool is sizeable
    assert all(isinstance(t, str) for t in pool[:50])


def test_default_pool_cache_returns_same_instance():
    """load_default_pool returns the same list object on repeated calls (cached)."""
    a = cp.load_default_pool()
    b = cp.load_default_pool()
    assert a is b


# ---------------------------------------------------------------------------
# Node class contract
# ---------------------------------------------------------------------------


def test_node_category_and_io():
    """AnimaCharacterRandomizer declares expected category, function, and return types."""
    assert AnimaCharacterRandomizer.CATEGORY == "Anima"
    assert AnimaCharacterRandomizer.FUNCTION == "randomize"
    assert AnimaCharacterRandomizer.RETURN_TYPES == ("STRING",)
    assert AnimaCharacterRandomizer.RETURN_NAMES == ("character_tags",)


def test_node_input_types():
    """INPUT_TYPES exposes count, seed, pool, picked with correct widget config."""
    schema = AnimaCharacterRandomizer.INPUT_TYPES()
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
    node = AnimaCharacterRandomizer()
    out = node.randomize(2, 999, "hatsune miku, asuka", picked="rei ayanami, misato")
    assert out == ("rei ayanami, misato",)


def test_randomize_ignores_blank_picked_and_falls_back():
    """Whitespace-only picked is treated as absent -> seeded selection from pool."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(1, 0, "hatsune miku", picked="   ")
    assert out == ("hatsune miku",)


def test_randomize_uses_explicit_pool_and_is_deterministic():
    """Two calls with same args (and no picked) return identical results."""
    node = AnimaCharacterRandomizer()
    r1 = node.randomize(2, 123, "hatsune miku, hakurei reimu, asuka")
    r2 = node.randomize(2, 123, "hatsune miku, hakurei reimu, asuka")
    assert r1 == r2
    assert isinstance(r1, tuple) and isinstance(r1[0], str)
    picked = [t.strip() for t in r1[0].split(",")]
    assert len(picked) == 2
    assert set(picked) <= {"hatsune miku", "hakurei reimu", "asuka"}


def test_randomize_falls_back_to_default_pool_when_empty():
    """Empty pool causes fallback to built-in default pool (returns non-empty result)."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(3, 5, "")
    assert out[0]
    assert len(out[0].split(",")) == 3


def test_randomize_empty_pool_and_no_default(monkeypatch):
    """When pool is empty and default pool is unavailable, returns empty string."""
    monkeypatch.setattr(cp, "load_default_pool", lambda: [])
    node = AnimaCharacterRandomizer()
    assert node.randomize(3, 1, "") == ("",)


def test_randomize_count_one():
    """count=1 returns a single tag with no comma."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(1, 0, "hatsune miku, hakurei reimu")
    assert "," not in out[0]
    assert out[0] in ("hatsune miku", "hakurei reimu")
