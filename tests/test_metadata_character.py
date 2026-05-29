"""Tests for AnimaCharacterRandomizer character/series/general/natural_language
extraction in metadata_extractor._extract_from_comfyui_prompt.

The randomizer records its chosen characters into picked / picked_series /
picked_general / picked_prompt_example widgets at queue time.  These tests
verify that those values surface into anima_fields with the correct keys and
deduplication behaviour, for both the prompt-JSON path and the workflow-JSON
(pseudo-dict) path.
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


def _situation_randomizer(picked: str = "") -> dict:
    return {
        "class_type": "AnimaSituationRandomizer",
        "inputs": {"count": 1, "seed": 0, "pool": "", "picked": picked},
    }


def _workflow_character_node(node_id: int, *widgets_values) -> dict:
    """Return a workflow-style pseudo-dict entry for AnimaCharacterRandomizer.

    The workflow extractor maps widget_values by index:
        [0]=count  [1]=seed  [2]=control_after_generate  [3]=pool
        [4]=picked  [5]=picked_series  [6]=picked_general  [7]=picked_prompt_example
    """
    names = [
        "picked",
        "picked_series",
        "picked_general",
        "picked_prompt_example",
    ]
    # widgets_values is positional: first element maps to index 4 (picked)
    inputs: dict = {}
    for i, name in enumerate(names):
        if i < len(widgets_values) and isinstance(widgets_values[i], str):
            inputs[name] = widgets_values[i]
    return {str(node_id): {"class_type": "AnimaCharacterRandomizer", "inputs": inputs}}


# ---------------------------------------------------------------------------
# prompt JSON path
# ---------------------------------------------------------------------------


def test_picked_surfaces_in_character_field():
    prompt = {"1": _character_randomizer(picked="rei ayanami")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["character"] == "rei ayanami"


def test_picked_series_surfaces_in_series_field():
    prompt = {"1": _character_randomizer(picked="rei ayanami", picked_series="neon genesis evangelion")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["series"] == "neon genesis evangelion"


def test_picked_general_surfaces_in_general_field():
    prompt = {"1": _character_randomizer(picked="rei ayanami", picked_general="long hair, blue hair")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["general"] == "long hair, blue hair"


def test_picked_prompt_example_surfaces_in_natural_language():
    prompt = {"1": _character_randomizer(picked="rei ayanami", picked_prompt_example="rei ayanami, blue hair")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["natural_language"] == "rei ayanami, blue hair"


def test_blank_picked_adds_nothing():
    # picked が空 / 空白のみ → character フィールドが追加されない
    # picked_series / picked_general も空にする（各フィールドは独立して収集されるため）
    prompt = {
        "1": _character_randomizer(picked="   ", picked_series="", picked_general=""),
        "2": _composer(quality="masterpiece"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert "character" not in res.get("anima_fields", {})
    assert "series" not in res.get("anima_fields", {})
    assert "general" not in res.get("anima_fields", {})


def test_composer_literal_character_merged_with_randomizer():
    # Composer に literal character がある AND randomizer picked も存在 → dedupe merged
    prompt = {
        "10": _composer(character="yotsuba kosuga"),
        "20": _character_randomizer(picked="rei ayanami"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    character = res["anima_fields"]["character"]
    tags = [t.strip() for t in character.split(",")]
    assert tags == ["yotsuba kosuga", "rei ayanami"]


def test_composer_literal_general_merged_with_picked_general():
    # Composer general と randomizer picked_general の dedupe マージ
    prompt = {
        "10": _composer(general="looking at viewer"),
        "20": _character_randomizer(picked="rei ayanami", picked_general="long hair, looking at viewer"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    general = res["anima_fields"]["general"]
    tags = [t.strip() for t in general.split(",")]
    # "looking at viewer" はデデュープされ1回のみ
    assert tags.count("looking at viewer") == 1
    assert "long hair" in tags


def test_multiple_character_randomizers_combined():
    # 2 つの CharacterRandomizer → 両方の picked がマージされる
    prompt = {
        "10": _composer(quality="masterpiece"),
        "20": _character_randomizer(picked="rei ayanami"),
        "21": _character_randomizer(picked="asuka langley"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    tags = [t.strip() for t in res["anima_fields"]["character"].split(",")]
    assert set(tags) == {"rei ayanami", "asuka langley"}


def test_character_and_artist_coexist():
    # Artist randomizer と Character randomizer が共存しても互いに干渉しない
    prompt = {
        "10": _composer(quality="masterpiece"),
        "20": _artist_randomizer(picked="@dairi"),
        "30": _character_randomizer(picked="rei ayanami"),
    }
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["artist"] == "@dairi"
    assert res["anima_fields"]["character"] == "rei ayanami"
    # artist フィールドに character が混入していない
    assert "rei ayanami" not in res["anima_fields"]["artist"]
    # character フィールドに artist が混入していない
    assert "@dairi" not in res["anima_fields"]["character"]


def test_no_composer_only_randomizer():
    # Composer ノードが無くても randomizer の picked が抽出される
    prompt = {"1": _character_randomizer(picked="rei ayanami", picked_series="neon genesis evangelion")}
    res = _extract_from_comfyui_prompt(prompt)
    assert res is not None
    assert res["anima_fields"]["character"] == "rei ayanami"
    assert res["anima_fields"]["series"] == "neon genesis evangelion"


# ---------------------------------------------------------------------------
# workflow JSON path (pseudo-dict — widgets_values already mapped by caller)
# ---------------------------------------------------------------------------


def test_workflow_character_widgets_values():
    # workflow extractor が pseudo-dict に変換済みの状態をシミュレートする
    # widget 順: [count=1, seed=0, fixed, "", picked, picked_series, picked_general, picked_prompt_example]
    # → 呼び出し側が index 4..7 を inputs に展開して渡す
    pseudo = {
        "1": {
            "class_type": "AnimaCharacterRandomizer",
            "inputs": {
                "picked": "rei ayanami",
                "picked_series": "neon genesis evangelion",
                "picked_general": "long hair, blue hair",
                "picked_prompt_example": "rei ayanami, blue hair",
            },
        }
    }
    res = _extract_from_comfyui_prompt(pseudo)
    assert res is not None
    assert res["anima_fields"]["character"] == "rei ayanami"
    assert res["anima_fields"]["series"] == "neon genesis evangelion"
    assert res["anima_fields"]["general"] == "long hair, blue hair"
    assert res["anima_fields"]["natural_language"] == "rei ayanami, blue hair"


def test_workflow_character_partial_widgets_values():
    # picked のみ存在（picked_series 以降が欠落）でもクラッシュしない
    pseudo = {
        "1": {
            "class_type": "AnimaCharacterRandomizer",
            "inputs": {
                "picked": "rei ayanami",
                # picked_series / picked_general / picked_prompt_example は無い
            },
        }
    }
    res = _extract_from_comfyui_prompt(pseudo)
    assert res is not None
    assert res["anima_fields"]["character"] == "rei ayanami"
    assert "series" not in res["anima_fields"]
    assert "general" not in res["anima_fields"]
    assert "natural_language" not in res["anima_fields"]


def test_workflow_only_no_prompt_chunk():
    # workflow から生成した pseudo dict のみ（composer 無し）で抽出できる
    pseudo = {
        "5": {
            "class_type": "AnimaCharacterRandomizer",
            "inputs": {
                "picked": "asuka langley",
                "picked_series": "neon genesis evangelion",
            },
        }
    }
    res = _extract_from_comfyui_prompt(pseudo)
    assert res is not None
    assert res["anima_fields"]["character"] == "asuka langley"
    assert res["anima_fields"]["series"] == "neon genesis evangelion"


def test_composer_literal_no_duplicate_in_positive():
    """Composer character literal + randomizer picked が positive に二重で出ない"""
    prompt = {
        "1": _composer(character="yotsuba kosuga", general="masterpiece"),
        "2": _character_randomizer(picked="rei ayanami"),
    }
    result = _extract_from_comfyui_prompt(prompt)
    assert result is not None
    positive = result["positive"]
    # "yotsuba kosuga" は 1 回しか出現しない
    assert positive.lower().count("yotsuba kosuga") == 1
    # "rei ayanami" も含まれる
    assert "rei ayanami" in positive.lower()


def test_natural_language_multiline_dedup():
    """既存 NL が複数行のとき行レベルで dedup"""
    prompt = {
        "1": _composer(natural_language="line A\nline B"),
        "2": _character_randomizer(picked_prompt_example="line A"),
    }
    result = _extract_from_comfyui_prompt(prompt)
    assert result is not None
    nl = result["anima_fields"]["natural_language"]
    lines = nl.split("\n")
    # "line A" が 1 行のみ
    assert sum(1 for ln in lines if ln.strip() == "line A") == 1
    # "line B" も保持
    assert "line B" in lines
