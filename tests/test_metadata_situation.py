"""Tests for AnimaSituationRandomizer situation extraction in
metadata_extractor._extract_from_comfyui_prompt.

The randomizer records its chosen situations into the ``picked`` widget at
queue time.  These tests verify that picked surfaces into
anima_fields["general"] (merged/deduped with any composer general literal and
with CharacterRandomizer picked_general), for both the prompt-JSON path and
the workflow-JSON (pseudo-dict) path.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.metadata_extractor import _extract_from_comfyui_prompt


# ---------------------------------------------------------------------------
# Inline node factories
# ---------------------------------------------------------------------------


def _composer(**fields) -> dict:
    """Return an AnimaPromptComposer node dict."""
    return {
        "class_type": "AnimaPromptComposer",
        "inputs": {k: v for k, v in fields.items()},
    }


def _situation_randomizer(picked: str = "") -> dict:
    return {
        "class_type": "AnimaSituationRandomizer",
        "inputs": {
            "count": 1,
            "seed": 0,
            "pool": "",
            "picked": picked,
        },
    }


def _character_randomizer(
    picked: str = "",
    picked_series: str = "",
    picked_general: str = "",
    picked_prompt_example: str = "",
) -> dict:
    return {
        "class_type": "AnimaCharacterRandomizer",
        "inputs": {
            "count": 1,
            "seed": 0,
            "pool": "",
            "picked": picked,
            "picked_series": picked_series,
            "picked_general": picked_general,
            "picked_prompt_example": picked_prompt_example,
        },
    }


def _artist_randomizer(picked: str) -> dict:
    return {
        "class_type": "AnimaArtistRandomizer",
        "inputs": {"count": 1, "seed": 0, "pool": "", "picked": picked},
    }


# ---------------------------------------------------------------------------
# prompt JSON path
# ---------------------------------------------------------------------------


def test_situation_picked_surfaces_in_general_field():
    prompt = {"1": _situation_randomizer(picked="outdoor, night sky")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["general"] == "outdoor, night sky"


def test_blank_situation_picked_adds_nothing():
    # 空 picked → general フィールドが追加されない
    prompt = {
        "1": _situation_randomizer(picked="   "),
        "2": _composer(quality="masterpiece"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert "general" not in res.get("anima_fields", {})


def test_situation_merges_with_composer_general():
    # Composer general と situation picked の dedupe マージ
    prompt = {
        "10": _composer(general="looking at viewer"),
        "20": _situation_randomizer(picked="outdoor, looking at viewer"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    general = res["anima_fields"]["general"]
    tags = [t.strip() for t in general.split(",")]
    # "looking at viewer" はデデュープされ1回のみ
    assert tags.count("looking at viewer") == 1
    assert "outdoor" in tags


def test_multiple_situation_randomizers_combined():
    # 2 つの SituationRandomizer → 両方の picked が general にマージされる
    prompt = {
        "10": _composer(quality="masterpiece"),
        "20": _situation_randomizer(picked="outdoor, sunny"),
        "21": _situation_randomizer(picked="night sky, cloudy"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    tags = [t.strip() for t in res["anima_fields"]["general"].split(",")]
    assert set(tags) == {"outdoor", "sunny", "night sky", "cloudy"}


def test_situation_and_character_general_merge():
    # CharacterRandomizer の picked_general と SituationRandomizer の picked が
    # 両方 anima_fields["general"] にマージされる
    prompt = {
        "10": _character_randomizer(picked="rei ayanami", picked_general="long hair, blue hair"),
        "20": _situation_randomizer(picked="outdoor, blue hair"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    general = res["anima_fields"]["general"]
    tags = [t.strip() for t in general.split(",")]
    # "blue hair" はデデュープで1回のみ
    assert tags.count("blue hair") == 1
    assert "long hair" in tags
    assert "outdoor" in tags


def test_situation_and_artist_coexist():
    # ArtistRandomizer と SituationRandomizer が共存しても干渉しない
    prompt = {
        "10": _composer(quality="masterpiece"),
        "20": _artist_randomizer(picked="@dairi"),
        "30": _situation_randomizer(picked="outdoor, night sky"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["artist"] == "@dairi"
    assert res["anima_fields"]["general"] == "outdoor, night sky"
    # artist フィールドに situation が混入していない
    assert "outdoor" not in res["anima_fields"]["artist"]
    # general フィールドに artist が混入していない
    assert "@dairi" not in res["anima_fields"]["general"]


def test_three_randomizers_all_coexist():
    # artist + character + situation + composer のフル構成
    prompt = {
        "10": _composer(
            quality="masterpiece",
            general="solo",
        ),
        "20": _artist_randomizer(picked="@dairi"),
        "30": _character_randomizer(
            picked="rei ayanami",
            picked_series="neon genesis evangelion",
            picked_general="long hair, blue hair",
            picked_prompt_example="rei ayanami, blue hair",
        ),
        "40": _situation_randomizer(picked="outdoor, night sky"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    af = res["anima_fields"]

    # artist は artist フィールドにのみ
    assert af["artist"] == "@dairi"

    # character は character フィールドにのみ
    assert af["character"] == "rei ayanami"

    # series は series フィールドにのみ
    assert af["series"] == "neon genesis evangelion"

    # general = composer "solo" + character "long hair, blue hair" + situation "outdoor, night sky"
    general_tags = [t.strip() for t in af["general"].split(",")]
    assert "solo" in general_tags
    assert "long hair" in general_tags
    assert "blue hair" in general_tags
    assert "outdoor" in general_tags
    assert "night sky" in general_tags

    # natural_language は character randomizer 由来
    assert af["natural_language"] == "rei ayanami, blue hair"


# ---------------------------------------------------------------------------
# workflow JSON path (pseudo-dict — widgets_values already mapped by caller)
# ---------------------------------------------------------------------------


def test_workflow_situation_widgets_values():
    # workflow extractor が pseudo-dict に変換済みの状態をシミュレートする
    # widget 順: [count=1, seed=0, fixed, "", picked]
    # → 呼び出し側が index 4 を inputs["picked"] に展開して渡す
    pseudo = {
        "1": {
            "class_type": "AnimaSituationRandomizer",
            "inputs": {
                "picked": "outdoor, night sky",
            },
        }
    }
    res = _extract_from_comfyui_prompt(pseudo)
    assert res is not None
    assert res["anima_fields"]["general"] == "outdoor, night sky"


def test_workflow_situation_partial_widgets_values():
    # picked が空文字（短い widgets_values の場合に相当）でもクラッシュしない
    pseudo = {
        "1": {
            "class_type": "AnimaSituationRandomizer",
            "inputs": {
                # picked キー自体が無い（index 4 未満の widgets_values 相当）
            },
        }
    }
    res = _extract_from_comfyui_prompt(pseudo)
    # general フィールドが追加されないことを確認（クラッシュしない）
    assert res is None or "general" not in res.get("anima_fields", {})


def test_situation_general_in_positive_when_character_general_exists():
    """Character の picked_general と Situation の picked が両方 positive に出る"""
    prompt = {
        "1": _composer(general="masterpiece"),
        "2": {
            "class_type": "AnimaCharacterRandomizer",
            "inputs": {
                "count": 1,
                "seed": 0,
                "pool": "",
                "picked": "rei",
                "picked_series": "",
                "picked_general": "long hair",
                "picked_prompt_example": "",
            },
        },
        "3": _situation_randomizer(picked="outdoor"),
    }
    result = _extract_from_comfyui_prompt(prompt)
    assert result is not None
    positive = result["positive"].lower()
    # 両方が positive に出現
    assert "long hair" in positive
    assert "outdoor" in positive
    # general フィールドにも両方
    general_field = result["anima_fields"]["general"].lower()
    assert "long hair" in general_field
    assert "outdoor" in general_field
