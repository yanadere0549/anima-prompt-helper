"""Unit tests for AnimaTagPalette node.

Tests INPUT_TYPES, RETURN_TYPES, and passthrough method.
ComfyUI-independent; runs with plain pytest.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow importing python package without installing ComfyUI.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from python.nodes import AnimaTagPalette


# ---------------------------------------------------------------------------
# Class-level contract tests
# ---------------------------------------------------------------------------


def test_category() -> None:
    assert AnimaTagPalette.CATEGORY == "Anima"


def test_function_name() -> None:
    assert AnimaTagPalette.FUNCTION == "passthrough"


def test_return_types() -> None:
    assert AnimaTagPalette.RETURN_TYPES == ("STRING",)


def test_return_names() -> None:
    assert AnimaTagPalette.RETURN_NAMES == ("tags",)


# ---------------------------------------------------------------------------
# INPUT_TYPES tests
# ---------------------------------------------------------------------------


def test_input_types_structure() -> None:
    """INPUT_TYPES must have a 'required' key containing 'tags_buffer'."""
    schema = AnimaTagPalette.INPUT_TYPES()
    assert "required" in schema
    assert "tags_buffer" in schema["required"]


def test_input_types_tags_buffer_type() -> None:
    """tags_buffer must be a single-line STRING.

    multiline=False prevents LiteGraph from auto-expanding the widget row as
    the comma-separated buffer grows; the widget is further hidden by the
    panel JS on the frontend.
    """
    schema = AnimaTagPalette.INPUT_TYPES()
    field_type, field_opts = schema["required"]["tags_buffer"]
    assert field_type == "STRING"
    assert field_opts.get("multiline") is False


def test_input_types_no_optional() -> None:
    """There should be no optional inputs by default."""
    schema = AnimaTagPalette.INPUT_TYPES()
    assert "optional" not in schema or not schema["optional"]


# ---------------------------------------------------------------------------
# passthrough tests
# ---------------------------------------------------------------------------


def test_passthrough_empty_string() -> None:
    node = AnimaTagPalette()
    result = node.passthrough("")
    assert result == ("",)


def test_passthrough_simple_tags() -> None:
    node = AnimaTagPalette()
    tags = "blue hair, smile, standing"
    result = node.passthrough(tags)
    assert result == (tags,)


def test_passthrough_returns_tuple() -> None:
    node = AnimaTagPalette()
    result = node.passthrough("any tag")
    assert isinstance(result, tuple)
    assert len(result) == 1


def test_passthrough_unicode_tags() -> None:
    """Non-ASCII tag strings must pass through unchanged."""
    node = AnimaTagPalette()
    tags = "髪色, 笑顔"
    result = node.passthrough(tags)
    assert result == (tags,)


def test_passthrough_whitespace_only() -> None:
    """Whitespace-only string is still valid (no stripping at this layer)."""
    node = AnimaTagPalette()
    result = node.passthrough("   ")
    assert result == ("   ",)


def test_passthrough_raises_on_non_string() -> None:
    """passthrough must raise TypeError when tags_buffer is not str."""
    node = AnimaTagPalette()
    with pytest.raises(TypeError):
        node.passthrough(123)  # type: ignore[arg-type]


def test_passthrough_raises_on_none() -> None:
    """passthrough must raise TypeError when tags_buffer is None."""
    node = AnimaTagPalette()
    with pytest.raises(TypeError):
        node.passthrough(None)  # type: ignore[arg-type]


def test_passthrough_raises_on_list() -> None:
    """passthrough must raise TypeError when tags_buffer is a list."""
    node = AnimaTagPalette()
    with pytest.raises(TypeError):
        node.passthrough(["blue hair"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Registration contract — checks NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS
# ---------------------------------------------------------------------------


def test_node_class_mappings_includes_tag_palette() -> None:
    """AnimaTagPalette must be registered in NODE_CLASS_MAPPINGS."""
    import importlib
    import types

    # Dynamically import __init__ without triggering server import errors
    spec = importlib.util.spec_from_file_location(
        "anima_prompt_helper_init", _ROOT / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Provide a stub 'python.api' to avoid ImportError from server module
    sys.modules.setdefault("server", types.ModuleType("server"))
    try:
        spec.loader.exec_module(mod)
    except Exception:
        pass  # May fail due to missing server; we only need the mappings

    # Fall back to direct import if dynamic load failed
    try:
        from __init__ import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS  # type: ignore[import]
    except ImportError:
        # Use the dynamically loaded module attributes
        NODE_CLASS_MAPPINGS = getattr(mod, "NODE_CLASS_MAPPINGS", {})
        NODE_DISPLAY_NAME_MAPPINGS = getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", {})

    assert "AnimaTagPalette" in NODE_CLASS_MAPPINGS
    assert NODE_CLASS_MAPPINGS["AnimaTagPalette"] is AnimaTagPalette
    assert "AnimaTagPalette" in NODE_DISPLAY_NAME_MAPPINGS
    assert NODE_DISPLAY_NAME_MAPPINGS["AnimaTagPalette"] == "Anima Tag Palette"
