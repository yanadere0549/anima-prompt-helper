"""Unit tests for the GET /anima_prompt_helper/health endpoint.

Tests exercise ``build_health_payload()`` and ``_read_version()`` in
isolation — no aiohttp server required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure the extension root is on sys.path so sub-package imports resolve.
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

import python.api.routes as routes_module
from python.api.routes import build_health_payload, _read_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_FILES = [
    "tag_palette.json",
    "tag_palette_extras.json",
    "anima_spec.json",
    "character_presets.json",
    "i18n/ja.json",
]

_EXPECTED_ROUTES = [
    "/anima_prompt_helper/palette",
    "/anima_prompt_helper/spec",
    "/anima_prompt_helper/character_presets",
    "/anima_prompt_helper/validate",
    "/anima_prompt_helper/health",
]

_EXPECTED_NODE_CLASSES = [
    "AnimaPromptComposer",
    "AnimaPromptToConditioning",
    "AnimaNegativePromptComposer",
]


# ---------------------------------------------------------------------------
# Test 1 — status "ok" when all data files exist
# ---------------------------------------------------------------------------

def test_health_returns_ok_when_all_files_present():
    """All expected data files exist on disk → status must be "ok"."""
    # Reset version cache so tests are independent.
    routes_module._version_cache = None

    payload = build_health_payload()

    # All files must report exists=True in this repo (they are committed).
    missing = [
        name for name, info in payload["data_files"].items()
        if not info["exists"]
    ]
    assert missing == [], f"Files reported missing: {missing}"
    assert payload["status"] == "ok", (
        f"Expected status='ok' but got '{payload['status']}'. "
        f"Missing files: {missing}"
    )


# ---------------------------------------------------------------------------
# Test 2 — status "degraded" when a file is missing
# ---------------------------------------------------------------------------

def test_health_returns_degraded_when_file_missing():
    """Mock os.path.exists to return False for one file → status must be "degraded"."""
    routes_module._version_cache = None

    real_exists = Path.exists

    def mock_exists(self: Path) -> bool:
        if self.name == "tag_palette.json":
            return False
        return real_exists(self)

    with patch.object(Path, "exists", mock_exists):
        payload = build_health_payload()

    assert payload["status"] == "degraded", (
        f"Expected status='degraded' but got '{payload['status']}'"
    )
    assert payload["data_files"]["tag_palette.json"]["exists"] is False


# ---------------------------------------------------------------------------
# Test 3 — all 5 routes present in response
# ---------------------------------------------------------------------------

def test_health_response_includes_all_5_routes():
    """Health payload must list all 5 registered routes."""
    payload = build_health_payload()

    for route in _EXPECTED_ROUTES:
        assert route in payload["routes"], (
            f"Route '{route}' missing from health response routes list"
        )
    assert len(payload["routes"]) == 5, (
        f"Expected 5 routes, got {len(payload['routes'])}: {payload['routes']}"
    )


# ---------------------------------------------------------------------------
# Test 4 — node_class names present
# ---------------------------------------------------------------------------

def test_health_returns_node_class_names():
    """Health payload must contain the 3 registered node class names."""
    payload = build_health_payload()

    node_classes = payload["node_classes"]
    assert node_classes != ["import_error"], (
        "node_classes returned ['import_error'] — import of root __init__.py failed"
    )
    for cls in _EXPECTED_NODE_CLASSES:
        assert cls in node_classes, (
            f"Expected node class '{cls}' in health response, got: {node_classes}"
        )


# ---------------------------------------------------------------------------
# Test 5 — version field is a non-empty string
# ---------------------------------------------------------------------------

def test_health_version_field_present_and_string():
    """version must be a non-empty string (read from pyproject.toml or fallback)."""
    routes_module._version_cache = None  # force fresh read

    payload = build_health_payload()

    version = payload.get("version")
    assert isinstance(version, str), f"Expected version to be str, got {type(version)}"
    assert version, "version must be a non-empty string"
    # Should match semver-ish pattern from pyproject.toml
    assert "." in version, f"version '{version}' looks malformed (expected e.g. '0.2.0')"
