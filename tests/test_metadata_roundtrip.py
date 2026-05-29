"""End-to-end metadata round-trip tests.

Simulates: randomizer node execution -> ComfyUI prompt JSON assembly ->
_extract_from_comfyui_prompt -> anima_fields validation.

Unlike unit tests that embed picked values directly, these tests first call
each randomizer's randomize() to obtain actual picked values (headless path,
seed-driven), then embed those values as widget state in a prompt JSON, then
extract and verify the round-trip.

This ensures that Character / Situation picked values survive the full cycle
from node output through metadata extraction.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.nodes import (
    AnimaArtistRandomizer,
    AnimaCharacterRandomizer,
    AnimaSituationRandomizer,
)
from python.metadata_extractor import _extract_from_comfyui_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _char_node(
    count: int,
    seed: int,
    pool: str,
    picked: str,
    picked_series: str,
    picked_general: str,
    picked_prompt_example: str,
) -> dict:
    return {
        "class_type": "AnimaCharacterRandomizer",
        "inputs": {
            "count": count,
            "seed": seed,
            "pool": pool,
            "picked": picked,
            "picked_series": picked_series,
            "picked_general": picked_general,
            "picked_prompt_example": picked_prompt_example,
        },
    }


def _sit_node(count: int, seed: int, pool: str, picked: str) -> dict:
    return {
        "class_type": "AnimaSituationRandomizer",
        "inputs": {"count": count, "seed": seed, "pool": pool, "picked": picked},
    }


def _art_node(count: int, seed: int, pool: str, picked: str) -> dict:
    return {
        "class_type": "AnimaArtistRandomizer",
        "inputs": {"count": count, "seed": seed, "pool": pool, "picked": picked},
    }


def _composer_node(**fields) -> dict:
    return {
        "class_type": "AnimaPromptComposer",
        "inputs": {k: v for k, v in fields.items()},
    }


# ---------------------------------------------------------------------------
# Test 1: Character round-trip
# ---------------------------------------------------------------------------


def test_character_roundtrip_picked_preserved():
    """CharacterRandomizer.randomize() output embedded as picked widget values
    is fully recovered by _extract_from_comfyui_prompt as anima_fields["character"].
    """
    node = AnimaCharacterRandomizer()
    pool = "hatsune miku, rei ayanami, asuka langley soryu, hakurei reimu"
    count = 2
    seed = 42

    # Step 1: run randomizer headless (empty picked -> seed-driven selection)
    character_tags, series, general, prompt_example = node.randomize(
        count=count, seed=seed, pool=pool,
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )

    # Precondition: headless path must produce non-empty character_tags
    assert character_tags, "randomize() must return non-empty character_tags"

    # Step 2: assemble prompt JSON with those values as widget state
    prompt_json = {
        "1": _char_node(count, seed, pool, character_tags, series, general, prompt_example),
    }

    # Step 3: extract
    result = _extract_from_comfyui_prompt(prompt_json)

    # Step 4: assert round-trip
    assert result is not None
    af = result["anima_fields"]
    assert af["character"] == character_tags
    if series:
        assert af.get("series") == series
    if general:
        assert af.get("general") == general
    if prompt_example:
        assert af.get("natural_language") == prompt_example
    assert character_tags in result["positive"]


# ---------------------------------------------------------------------------
# Test 2: Situation round-trip
# ---------------------------------------------------------------------------


def test_situation_roundtrip_picked_preserved():
    """SituationRandomizer.randomize() output embedded as picked widget value
    is recovered by _extract_from_comfyui_prompt as anima_fields["general"].
    """
    node = AnimaSituationRandomizer()
    pool = "outdoor, night sky, beach, forest, city, school uniform"
    count = 2
    seed = 99

    # Step 1: run randomizer headless
    (situation_tags,) = node.randomize(count=count, seed=seed, pool=pool, picked="")

    assert situation_tags, "randomize() must return non-empty situation_tags"

    # Step 2: assemble prompt JSON
    prompt_json = {
        "1": _sit_node(count, seed, pool, situation_tags),
    }

    # Step 3: extract
    result = _extract_from_comfyui_prompt(prompt_json)

    # Step 4: assert round-trip
    assert result is not None
    af = result["anima_fields"]
    assert af["general"] == situation_tags
    assert situation_tags in result["positive"]


# ---------------------------------------------------------------------------
# Test 3: Artist round-trip (regression guard)
# ---------------------------------------------------------------------------


def test_artist_roundtrip_picked_preserved():
    """ArtistRandomizer.randomize() output embedded as picked widget value
    is recovered by _extract_from_comfyui_prompt as anima_fields["artist"].
    """
    node = AnimaArtistRandomizer()
    pool = "@dairi, @neme, @wlop, @sakimichan"
    count = 2
    seed = 7

    # Step 1: run randomizer headless
    (artist_tags,) = node.randomize(count=count, seed=seed, pool=pool, picked="")

    assert artist_tags, "randomize() must return non-empty artist_tags"

    # Step 2: assemble prompt JSON
    prompt_json = {
        "1": _art_node(count, seed, pool, artist_tags),
    }

    # Step 3: extract
    result = _extract_from_comfyui_prompt(prompt_json)

    # Step 4: assert round-trip
    assert result is not None
    assert result["anima_fields"]["artist"] == artist_tags
    assert artist_tags in result["positive"]


# ---------------------------------------------------------------------------
# Test 4: Three randomizers coexistence round-trip
# ---------------------------------------------------------------------------


def test_three_randomizers_roundtrip():
    """artist + character + situation all executed, embedded, and extracted
    into correct anima_fields keys with no cross-contamination.
    """
    a_node = AnimaArtistRandomizer()
    c_node = AnimaCharacterRandomizer()
    s_node = AnimaSituationRandomizer()

    (art_tags,) = a_node.randomize(count=1, seed=1, pool="@dairi, @neme", picked="")
    char_tags, char_series, char_gen, char_pe = c_node.randomize(
        count=1, seed=2, pool="hatsune miku, rei ayanami",
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )
    (sit_tags,) = s_node.randomize(count=1, seed=3, pool="outdoor, beach, night", picked="")

    prompt_json = {
        "1": _art_node(1, 1, "@dairi, @neme", art_tags),
        "2": _char_node(1, 2, "hatsune miku, rei ayanami",
                        char_tags, char_series, char_gen, char_pe),
        "3": _sit_node(1, 3, "outdoor, beach, night", sit_tags),
    }

    result = _extract_from_comfyui_prompt(prompt_json)
    assert result is not None
    af = result["anima_fields"]

    assert af["artist"] == art_tags
    assert af["character"] == char_tags
    # artist must not bleed into character and vice versa
    assert art_tags not in af["character"]
    assert char_tags not in af["artist"]

    # general contains situation picks; character general (if any) also merges in
    general_lower = af["general"].lower()
    for tag in sit_tags.split(","):
        assert tag.strip().lower() in general_lower

    if char_gen:
        for tag in char_gen.split(","):
            assert tag.strip().lower() in general_lower


# ---------------------------------------------------------------------------
# Test 5: Composer + CharacterRandomizer coexistence round-trip
# ---------------------------------------------------------------------------


def test_character_with_composer_roundtrip():
    """AnimaPromptComposer literal character and CharacterRandomizer picked
    are dedup-merged so both appear exactly once in anima_fields["character"]
    and positive.
    """
    c_node = AnimaCharacterRandomizer()
    char_tags, char_series, char_gen, char_pe = c_node.randomize(
        count=1, seed=42,
        pool="hatsune miku, asuka langley soryu, hakurei reimu",
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )

    composer_literal = "yotsuba kosuga"

    prompt_json = {
        "1": _composer_node(character=composer_literal, general="masterpiece"),
        "2": _char_node(1, 42,
                        "hatsune miku, asuka langley soryu, hakurei reimu",
                        char_tags, char_series, char_gen, char_pe),
    }

    result = _extract_from_comfyui_prompt(prompt_json)
    assert result is not None
    af = result["anima_fields"]

    # Both the composer literal and randomizer pick appear in character
    assert composer_literal in af["character"]
    assert char_tags in af["character"]

    # No duplicate of composer_literal in positive
    assert result["positive"].lower().count(composer_literal) == 1


# ---------------------------------------------------------------------------
# Test 6: Determinism — same seed yields same picks
# ---------------------------------------------------------------------------


def test_character_determinism_same_seed_same_picks():
    """Two calls with identical pool + seed return exactly the same 4-tuple."""
    node = AnimaCharacterRandomizer()
    pool = "a, b, c, d, e, f, g"
    seed = 12345

    r1 = node.randomize(
        count=3, seed=seed, pool=pool,
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )
    r2 = node.randomize(
        count=3, seed=seed, pool=pool,
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )

    assert r1 == r2, "Same seed must produce identical output (determinism)"


# ---------------------------------------------------------------------------
# Test 7: workflow JSON path (pseudo-dict widgets_values mapped by index)
# ---------------------------------------------------------------------------


def test_character_workflow_widgets_values_roundtrip():
    """workflow JSON path: widgets_values pre-mapped to inputs dict keys
    round-trips the same as the prompt JSON path.

    In the real workflow extractor the caller maps widgets_values[4..7] into
    inputs["picked"], inputs["picked_series"], etc. before calling
    _extract_from_comfyui_prompt. This test verifies that mapping.
    """
    c_node = AnimaCharacterRandomizer()
    char_tags, char_series, char_gen, char_pe = c_node.randomize(
        count=1, seed=42, pool="hatsune miku, rei ayanami",
        picked="", picked_series="", picked_general="", picked_prompt_example="",
    )

    # Simulate the already-mapped pseudo-dict that the workflow extractor produces
    pseudo_dict = {
        "1": {
            "class_type": "AnimaCharacterRandomizer",
            "inputs": {
                # count / seed / control_after_generate / pool are omitted
                # (not needed for extraction); only the picked* widgets matter.
                "picked": char_tags,
                "picked_series": char_series,
                "picked_general": char_gen,
                "picked_prompt_example": char_pe,
            },
        }
    }

    result = _extract_from_comfyui_prompt(pseudo_dict)
    assert result is not None
    af = result["anima_fields"]
    assert af["character"] == char_tags
    if char_series:
        assert af.get("series") == char_series
    if char_gen:
        assert af.get("general") == char_gen
    if char_pe:
        assert af.get("natural_language") == char_pe
