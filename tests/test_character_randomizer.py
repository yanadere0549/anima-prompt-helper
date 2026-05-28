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
# animadex preset loading + meta aggregation
# ---------------------------------------------------------------------------


def test_load_animadex_presets_keyed_by_lowercased_character():
    """load_animadex_presets returns a non-empty character→preset map (lower-cased keys)."""
    presets = cp.load_animadex_presets()
    assert isinstance(presets, dict)
    # Shipped file contains ~300 entries; sanity-check a known character.
    assert "hatsune miku" in presets
    miku = presets["hatsune miku"]
    assert miku.get("series") == "vocaloid"
    assert isinstance(miku.get("essential_general_tags"), list)
    assert isinstance(miku.get("prompt_example"), str)


def test_load_animadex_presets_cache_returns_same_instance():
    """load_animadex_presets returns the same dict object on repeated calls (cached)."""
    a = cp.load_animadex_presets()
    b = cp.load_animadex_presets()
    assert a is b


def test_aggregate_meta_empty_picks():
    """aggregate_meta returns three empty strings for an empty pick list."""
    assert cp.aggregate_meta([]) == ("", "", "")


def test_aggregate_meta_no_presets(monkeypatch):
    """aggregate_meta returns three empty strings when presets are unavailable."""
    monkeypatch.setattr(cp, "load_animadex_presets", lambda: {})
    assert cp.aggregate_meta(["hatsune miku"]) == ("", "", "")


def test_aggregate_meta_single_character(monkeypatch):
    """Single matched character: series/general/prompt_example all populated."""
    monkeypatch.setattr(
        cp,
        "load_animadex_presets",
        lambda: {
            "hatsune miku": {
                "character": "hatsune miku",
                "series": "vocaloid",
                "essential_general_tags": ["aqua hair", "twintails"],
                "prompt_example": "hatsune miku, aqua hair",
            }
        },
    )
    assert cp.aggregate_meta(["hatsune miku"]) == (
        "vocaloid",
        "aqua hair, twintails",
        "hatsune miku, aqua hair",
    )


def test_aggregate_meta_dedupes_series_and_general_case_insensitively(monkeypatch):
    """series + general are de-duplicated case-insensitively across picks."""
    monkeypatch.setattr(
        cp,
        "load_animadex_presets",
        lambda: {
            "a": {
                "character": "a",
                "series": "TouHou",
                "essential_general_tags": ["Red Eyes", "Long Hair"],
                "prompt_example": "a, red eyes",
            },
            "b": {
                "character": "b",
                "series": "touhou",  # case differs → dedupe
                "essential_general_tags": ["red eyes", "Blue Hair"],
                "prompt_example": "b, blue hair",
            },
        },
    )
    series, general, pe = cp.aggregate_meta(["a", "b"])
    # Series dedupes case-insensitively; first-seen casing wins.
    assert series == "TouHou"
    # general dedupes; preserves order from first appearance.
    parts = [g.strip() for g in general.split(",")]
    assert parts == ["Red Eyes", "Long Hair", "Blue Hair"]
    # prompt_example: NOT deduped (lines may differ); newline-joined.
    assert pe == "a, red eyes\nb, blue hair"


def test_aggregate_meta_skips_unknown_characters(monkeypatch):
    """Unknown characters are silently skipped; only matched picks contribute."""
    monkeypatch.setattr(
        cp,
        "load_animadex_presets",
        lambda: {
            "known": {
                "character": "known",
                "series": "alpha",
                "essential_general_tags": ["tag1"],
                "prompt_example": "known, tag1",
            }
        },
    )
    assert cp.aggregate_meta(["unknown", "known", "also_unknown"]) == (
        "alpha",
        "tag1",
        "known, tag1",
    )


def test_aggregate_meta_normalizes_pick_casing(monkeypatch):
    """Picks match presets via case-insensitive, trimmed comparison."""
    monkeypatch.setattr(
        cp,
        "load_animadex_presets",
        lambda: {
            "hatsune miku": {
                "character": "hatsune miku",
                "series": "vocaloid",
                "essential_general_tags": ["aqua hair"],
                "prompt_example": "hatsune miku",
            }
        },
    )
    assert cp.aggregate_meta(["  Hatsune Miku  "]) == (
        "vocaloid",
        "aqua hair",
        "hatsune miku",
    )


# ---------------------------------------------------------------------------
# Node class contract
# ---------------------------------------------------------------------------


def test_node_category_and_io():
    """AnimaCharacterRandomizer declares expected category, function, and return types."""
    assert AnimaCharacterRandomizer.CATEGORY == "Anima"
    assert AnimaCharacterRandomizer.FUNCTION == "randomize"
    assert AnimaCharacterRandomizer.RETURN_TYPES == (
        "STRING",
        "STRING",
        "STRING",
        "STRING",
    )
    assert AnimaCharacterRandomizer.RETURN_NAMES == (
        "character_tags",
        "series",
        "general",
        "prompt_example",
    )


def test_node_input_types():
    """INPUT_TYPES exposes count, seed, pool, picked, picked_* meta widgets."""
    schema = AnimaCharacterRandomizer.INPUT_TYPES()
    req = schema["required"]
    assert set(req) == {
        "count",
        "seed",
        "pool",
        "picked",
        "picked_series",
        "picked_general",
        "picked_prompt_example",
    }
    assert req["count"][0] == "INT"
    assert req["seed"][0] == "INT"
    # seed must expose control_after_generate so re-queuing reshuffles
    assert req["seed"][1].get("control_after_generate") is True
    assert req["pool"][0] == "STRING"
    assert req["pool"][1].get("multiline") is True
    assert req["picked"][0] == "STRING"
    assert req["picked_series"][0] == "STRING"
    assert req["picked_general"][0] == "STRING"
    assert req["picked_general"][1].get("multiline") is True
    assert req["picked_prompt_example"][0] == "STRING"
    assert req["picked_prompt_example"][1].get("multiline") is True


# ---------------------------------------------------------------------------
# randomize() behaviour
# ---------------------------------------------------------------------------


def test_randomize_returns_picked_verbatim_when_present():
    """GUI path: non-empty picked + meta widgets are returned unchanged."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(
        2,
        999,
        "hatsune miku, asuka",
        picked="rei ayanami, misato",
        picked_series="neon genesis evangelion",
        picked_general="red eyes, blue hair",
        picked_prompt_example="rei ayanami, red eyes\nmisato, brown hair",
    )
    assert out == (
        "rei ayanami, misato",
        "neon genesis evangelion",
        "red eyes, blue hair",
        "rei ayanami, red eyes\nmisato, brown hair",
    )


def test_randomize_gui_path_with_blank_meta_returns_blanks():
    """GUI path is authoritative: if meta widgets are blank, blanks pass through."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(
        1, 0, "hatsune miku", picked="some_obscure_character"
    )
    assert out == ("some_obscure_character", "", "", "")


def test_randomize_ignores_blank_picked_and_falls_back():
    """Whitespace-only picked is treated as absent -> seeded selection from pool."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(1, 0, "hatsune miku", picked="   ")
    # character_tags is "hatsune miku"; meta may or may not be present depending
    # on whether animadex_character_presets.json ships an entry for miku.
    assert isinstance(out, tuple) and len(out) == 4
    assert out[0] == "hatsune miku"


def test_randomize_uses_explicit_pool_and_is_deterministic():
    """Two calls with same args (and no picked) return identical results."""
    node = AnimaCharacterRandomizer()
    r1 = node.randomize(2, 123, "hatsune miku, hakurei reimu, asuka")
    r2 = node.randomize(2, 123, "hatsune miku, hakurei reimu, asuka")
    assert r1 == r2
    assert isinstance(r1, tuple) and len(r1) == 4
    assert all(isinstance(x, str) for x in r1)
    picked = [t.strip() for t in r1[0].split(",")]
    assert len(picked) == 2
    assert set(picked) <= {"hatsune miku", "hakurei reimu", "asuka"}


def test_randomize_falls_back_to_default_pool_when_empty():
    """Empty pool causes fallback to built-in default pool (returns non-empty result)."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(3, 5, "")
    assert isinstance(out, tuple) and len(out) == 4
    assert out[0]
    assert len(out[0].split(",")) == 3


def test_randomize_empty_pool_and_no_default(monkeypatch):
    """When pool is empty and default pool is unavailable, returns four empty strings."""
    monkeypatch.setattr(cp, "load_default_pool", lambda: [])
    node = AnimaCharacterRandomizer()
    assert node.randomize(3, 1, "") == ("", "", "", "")


def test_randomize_count_one():
    """count=1 returns a single tag with no comma."""
    node = AnimaCharacterRandomizer()
    out = node.randomize(1, 0, "hatsune miku, hakurei reimu")
    assert "," not in out[0]
    assert out[0] in ("hatsune miku", "hakurei reimu")


def test_randomize_headless_aggregates_meta_from_animadex(monkeypatch):
    """Headless path: meta is aggregated from animadex presets for picked chars."""
    fake_presets = {
        "hatsune miku": {
            "character": "hatsune miku",
            "series": "vocaloid",
            "essential_general_tags": ["aqua hair", "twintails"],
            "prompt_example": "hatsune miku, aqua hair, twintails, vocaloid",
        },
        "hakurei reimu": {
            "character": "hakurei reimu",
            "series": "touhou",
            "essential_general_tags": ["red bow", "twintails"],  # twintails dedupes
            "prompt_example": "hakurei reimu, red bow, touhou",
        },
    }
    monkeypatch.setattr(cp, "load_animadex_presets", lambda: fake_presets)
    node = AnimaCharacterRandomizer()
    out = node.randomize(2, 0, "hatsune miku, hakurei reimu")
    assert out[0] in (
        "hatsune miku, hakurei reimu",
        "hakurei reimu, hatsune miku",
    )
    # series dedup: comma-joined, both present
    series_set = {s.strip() for s in out[1].split(",")}
    assert series_set == {"vocaloid", "touhou"}
    # general dedup: twintails appears once
    general_list = [g.strip() for g in out[2].split(",")]
    assert general_list.count("twintails") == 1
    assert set(general_list) >= {"aqua hair", "twintails", "red bow"}
    # prompt_example: newline-joined; both lines present
    pe_lines = out[3].split("\n")
    assert len(pe_lines) == 2
    assert any("vocaloid" in line for line in pe_lines)
    assert any("touhou" in line for line in pe_lines)


def test_randomize_headless_missing_preset_yields_blank_meta(monkeypatch):
    """Headless path: characters without a preset yield blank meta strings."""
    monkeypatch.setattr(cp, "load_animadex_presets", lambda: {})
    node = AnimaCharacterRandomizer()
    out = node.randomize(1, 0, "obscure_unknown_character")
    assert out[0] == "obscure_unknown_character"
    assert out[1:] == ("", "", "")
