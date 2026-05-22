"""Tests for palette merge logic and /character_presets route.

These tests are ComfyUI-independent and run with plain pytest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Ensure the extension root is on sys.path so we can import python.*
_EXTENSION_ROOT = Path(__file__).resolve().parent.parent
if str(_EXTENSION_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXTENSION_ROOT))

from python.api.routes import load_palette_merged, _PALETTE_PATH, _PALETTE_EXTRAS_PATH


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_BASE_PALETTE = {
    "version": "1.0",
    "categories": [
        {"id": "quality", "label": "Quality", "order": 10, "tags": []},
        {"id": "year", "label": "Year", "order": 20, "tags": []},
        {"id": "rating", "label": "Rating", "order": 30, "tags": []},
    ],
}

_EXTRAS_PALETTE = {
    "version": "1.0",
    "categories": [
        {"id": "accessory", "label": "Accessories", "order": 200, "tags": []},
        {"id": "vehicle", "label": "Vehicle", "order": 210, "tags": []},
    ],
}


def _make_load_side_effect(base: dict, extras: dict | None):
    """Return a side_effect function for patching _load_json_file."""
    def _side_effect(path: Path) -> dict:
        if path == _PALETTE_PATH:
            return base
        if path == _PALETTE_EXTRAS_PATH:
            if extras is None:
                raise FileNotFoundError(f"mocked missing: {path}")
            return extras
        raise FileNotFoundError(f"unexpected path: {path}")
    return _side_effect


# ---------------------------------------------------------------------------
# Test 1: Both files present — categories from both appear in result
# ---------------------------------------------------------------------------

def test_merge_both_files_present_returns_all_categories() -> None:
    """Merged result contains categories from both base and extras files."""
    with patch("python.api.routes._load_json_file", side_effect=_make_load_side_effect(_BASE_PALETTE, _EXTRAS_PALETTE)), \
         patch("python.api.routes._PALETTE_EXTRAS_PATH") as mock_extras_path:
        mock_extras_path.exists.return_value = True
        mock_extras_path.__eq__ = lambda self, other: other == _PALETTE_EXTRAS_PATH
        # Use actual paths; patch exists() on the extras path
        with patch.object(Path, "exists", return_value=True):
            result = load_palette_merged()

    cat_ids = {c["id"] for c in result["categories"]}
    assert "quality" in cat_ids, "base category 'quality' missing"
    assert "year" in cat_ids, "base category 'year' missing"
    assert "accessory" in cat_ids, "extras category 'accessory' missing"
    assert "vehicle" in cat_ids, "extras category 'vehicle' missing"
    assert len(result["categories"]) == 5


# ---------------------------------------------------------------------------
# Test 2: Sort order — base categories appear before extras
# ---------------------------------------------------------------------------

def test_merge_sort_order_base_before_extras() -> None:
    """Base categories (order < 200) appear before extras (order >= 200) after sort."""
    # Build a shuffled-order scenario to confirm sort actually works
    base = {
        "version": "1.0",
        "categories": [
            {"id": "rating", "label": "Rating", "order": 30, "tags": []},
            {"id": "quality", "label": "Quality", "order": 10, "tags": []},
        ],
    }
    extras = {
        "version": "1.0",
        "categories": [
            {"id": "vehicle", "label": "Vehicle", "order": 210, "tags": []},
            {"id": "accessory", "label": "Accessories", "order": 200, "tags": []},
        ],
    }
    with patch("python.api.routes._load_json_file", side_effect=_make_load_side_effect(base, extras)), \
         patch.object(Path, "exists", return_value=True):
        result = load_palette_merged()

    orders = [c["order"] for c in result["categories"]]
    assert orders == sorted(orders), f"categories not sorted by order: {orders}"

    # Confirm all base-file orders precede all extras-file orders
    ids_in_order = [c["id"] for c in result["categories"]]
    quality_idx = ids_in_order.index("quality")
    accessory_idx = ids_in_order.index("accessory")
    assert quality_idx < accessory_idx, "base 'quality' should come before extras 'accessory'"


# ---------------------------------------------------------------------------
# Test 3: Extras file missing — returns only base categories, no exception
# ---------------------------------------------------------------------------

def test_merge_extras_missing_returns_base_only() -> None:
    """When extras file is absent, only base categories are returned without error."""
    with patch("python.api.routes._load_json_file", side_effect=_make_load_side_effect(_BASE_PALETTE, None)), \
         patch("python.api.routes._PALETTE_EXTRAS_PATH") as mock_extras_path:
        mock_extras_path.exists.return_value = False

        result = load_palette_merged()

    assert len(result["categories"]) == 3
    cat_ids = {c["id"] for c in result["categories"]}
    assert cat_ids == {"quality", "year", "rating"}


# ---------------------------------------------------------------------------
# Test 4: /character_presets route — uses actual data file
# ---------------------------------------------------------------------------

def test_character_presets_data_file_has_presets_key() -> None:
    """The actual character_presets.json file has a 'presets' key with a list."""
    presets_path = _EXTENSION_ROOT / "data" / "character_presets.json"
    assert presets_path.exists(), f"character_presets.json not found at {presets_path}"

    with presets_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    assert "presets" in data, "character_presets.json missing 'presets' key"
    assert isinstance(data["presets"], list), "'presets' must be a list"
    assert len(data["presets"]) > 0, "'presets' list must be non-empty"


# ---------------------------------------------------------------------------
# Test 5: Merged palette from actual data files has 30 categories
# ---------------------------------------------------------------------------

def test_merge_actual_files_30_categories() -> None:
    """Merging the real data files yields exactly 30 categories."""
    base_path = _EXTENSION_ROOT / "data" / "tag_palette.json"
    extras_path = _EXTENSION_ROOT / "data" / "tag_palette_extras.json"

    assert base_path.exists(), f"tag_palette.json not found at {base_path}"
    assert extras_path.exists(), f"tag_palette_extras.json not found at {extras_path}"

    result = load_palette_merged()
    assert len(result["categories"]) == 30, (
        f"Expected 30 categories after merge, got {len(result['categories'])}"
    )


# ---------------------------------------------------------------------------
# Test 6: Categories without 'order' field sort last (default 9999)
# ---------------------------------------------------------------------------

def test_merge_categories_without_order_go_last() -> None:
    """Categories lacking an 'order' field sort last (treated as 9999)."""
    base = {
        "version": "1.0",
        "categories": [
            {"id": "quality", "label": "Quality", "order": 10, "tags": []},
            {"id": "no_order", "label": "No Order", "tags": []},  # no 'order' key
        ],
    }
    with patch("python.api.routes._load_json_file", side_effect=_make_load_side_effect(base, None)), \
         patch("python.api.routes._PALETTE_EXTRAS_PATH") as mock_extras_path:
        mock_extras_path.exists.return_value = False

        result = load_palette_merged()

    ids_in_order = [c["id"] for c in result["categories"]]
    assert ids_in_order[-1] == "no_order", (
        f"Category without 'order' should be last, got: {ids_in_order}"
    )
