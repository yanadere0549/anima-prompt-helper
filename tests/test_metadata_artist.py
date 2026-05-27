"""Tests for AnimaArtistRandomizer artist extraction in metadata_extractor.

The randomizer records its chosen artists into a ``picked`` input/widget; the
composer's ``artist`` field is a link, so these tests verify that the picked
artists are surfaced into ``anima_fields['artist']`` and the positive text.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.metadata_extractor import _extract_from_comfyui_prompt


def _composer(artist_link=("55", 0), **fields):
    inputs = {
        "quality": "masterpiece",
        "count": "1girl",
        "general": "looking at viewer",
    }
    if artist_link is not None:
        inputs["artist"] = list(artist_link)  # link, not a literal string
    inputs.update(fields)
    return {"class_type": "AnimaPromptComposer", "inputs": inputs}


def _randomizer(picked):
    return {
        "class_type": "AnimaArtistRandomizer",
        "inputs": {"count": 2, "seed": 0, "pool": "@a, @b, @c", "picked": picked},
    }


def test_picked_surfaces_in_artist_field_and_positive():
    prompt = {"48": _composer(), "55": _randomizer("@hwansang jungdog, @ymd \\(holudoun\\)")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["artist"] == "@hwansang jungdog, @ymd \\(holudoun\\)"
    assert "@hwansang jungdog" in res["positive"]
    assert "@ymd \\(holudoun\\)" in res["positive"]


def test_blank_picked_adds_nothing():
    prompt = {"48": _composer(), "55": _randomizer("   ")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert "artist" not in res.get("anima_fields", {})


def test_merges_literal_composer_artist_with_randomizer_and_dedupes():
    # Composer has a literal artist (not a link) AND a randomizer is present.
    prompt = {
        "48": _composer(artist_link=None, artist="@dairi, @neme"),
        "55": _randomizer("@neme, @sakura shiori"),  # @neme duplicates
    }
    res = _extract_from_comfyui_prompt(prompt)
    artist = res["anima_fields"]["artist"]
    tags = [t.strip() for t in artist.split(",")]
    assert tags == ["@dairi", "@neme", "@sakura shiori"]  # order preserved, deduped


def test_randomizer_only_no_composer():
    prompt = {"55": _randomizer("@solo_artist")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["artist"] == "@solo_artist"
    assert "@solo_artist" in res["positive"]


def test_multiple_randomizers_combined():
    prompt = {
        "48": _composer(),
        "55": _randomizer("@a1"),
        "56": _randomizer("@a2, @a3"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    tags = [t.strip() for t in res["anima_fields"]["artist"].split(",")]
    assert set(tags) == {"@a1", "@a2", "@a3"}
