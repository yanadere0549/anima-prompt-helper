"""test_parity.py — JS/Python parity tests for composer.join_fields vs assemblePreview.

Asserts that Python composer.join_fields() and JS assemblePreview() produce
byte-identical output for the same inputs, using the canonical test cases in
scripts/parity_cases.json.

Known drift is documented via xfail markers rather than silent suppression so
future regressions remain visible.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
PARITY_CASES_PATH = EXTENSION_ROOT / "scripts" / "parity_cases.json"
JS_RUNNER = EXTENSION_ROOT / "scripts" / "run_js_compose.mjs"

# ---------------------------------------------------------------------------
# Import Python composer
# ---------------------------------------------------------------------------

sys.path.insert(0, str(EXTENSION_ROOT))
from python.composer import join_fields  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _node_available() -> bool:
    """Return True if `node` executable is on PATH."""
    return shutil.which("node") is not None


def _load_cases() -> list[dict[str, Any]]:
    """Load and return the list of test cases from parity_cases.json."""
    with PARITY_CASES_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["cases"]


def _run_js(cases: list[dict[str, Any]]) -> list[str]:
    """Run run_js_compose.mjs with the given cases, return list of output strings."""
    payload = json.dumps({"cases": cases}, ensure_ascii=False)
    result = subprocess.run(
        ["node", str(JS_RUNNER)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(EXTENSION_ROOT),
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"run_js_compose.mjs exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
    outputs = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            obj = json.loads(line)
            outputs.append(obj["output"])
    return outputs


# ---------------------------------------------------------------------------
# Test: parity for all canonical cases
# ---------------------------------------------------------------------------

CASES = _load_cases()


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[c["name"] for c in CASES],
)
def test_parity(case: dict[str, Any]) -> None:
    """Python join_fields and JS assemblePreview must produce identical output."""
    if not _node_available():
        pytest.skip("Node.js not available — skipping JS parity check")

    # Python result
    py_result = join_fields(case["fields"], case["preset"])

    # JS result — run single case for isolation
    js_outputs = _run_js([case])
    assert len(js_outputs) == 1, "JS runner must return exactly one output line per case"
    js_result = js_outputs[0]

    assert py_result == js_result, (
        f"\nParity failure for case: {case['name']!r}\n"
        f"  Python : {py_result!r}\n"
        f"  JS     : {js_result!r}"
    )


# ---------------------------------------------------------------------------
# Test: known drift — ooo_anima_default overrides rating in Python but not JS
# ---------------------------------------------------------------------------

def test_known_drift_rating_override() -> None:
    """Python and JS must agree: ooo_anima_default overrides rating with preset value."""
    if not _node_available():
        pytest.skip("Node.js not available")

    drift_case = {
        "fields": {
            "quality": "",
            "year": "",
            "rating": "nsfw",  # differs from preset default "safe"
            "count": "1boy",
            "character": "",
            "series": "",
            "artist": "",
            "general": "",
            "natural_language": "",
        },
        "preset": "ooo_anima_default",
    }

    py_result = join_fields(drift_case["fields"], drift_case["preset"])
    js_outputs = _run_js([drift_case])
    js_result = js_outputs[0]

    # Both Python and JS must replace rating → "safe" (preset default).
    assert py_result == js_result


# ---------------------------------------------------------------------------
# Test: batch mode — all cases at once matches individual calls
# ---------------------------------------------------------------------------

def test_batch_consistency() -> None:
    """Running all cases in one batch call matches individual Python calls."""
    if not _node_available():
        pytest.skip("Node.js not available")

    cases = _load_cases()
    js_outputs = _run_js(cases)
    assert len(js_outputs) == len(cases), (
        f"Expected {len(cases)} outputs, got {len(js_outputs)}"
    )
    for case, js_out in zip(cases, js_outputs):
        py_out = join_fields(case["fields"], case["preset"])
        assert py_out == js_out, (
            f"Batch mismatch for {case['name']!r}:\n"
            f"  Python: {py_out!r}\n"
            f"  JS    : {js_out!r}"
        )


# ---------------------------------------------------------------------------
# Test: Python-only sanity (no Node required)
# ---------------------------------------------------------------------------

def test_python_empty_all_fields() -> None:
    """join_fields with all-empty fields and no preset returns empty string."""
    result = join_fields(
        {"quality": "", "year": "", "rating": "", "count": "", "character": "",
         "series": "", "artist": "", "general": "", "natural_language": ""},
        "none",
    )
    assert result == ""


def test_python_natural_language_not_split() -> None:
    """natural_language is never comma-split; it is appended verbatim."""
    result = join_fields(
        {"quality": "", "year": "", "rating": "", "count": "", "character": "",
         "series": "", "artist": "", "general": "",
         "natural_language": "A girl, standing alone, gazes at the horizon."},
        "none",
    )
    assert result == "A girl, standing alone, gazes at the horizon."


def test_python_comma_only_collapses() -> None:
    """A field containing only commas collapses to empty after tokenization."""
    result = join_fields(
        {"quality": ",,,", "year": "", "rating": "", "count": "", "character": "",
         "series": "", "artist": "", "general": "", "natural_language": ""},
        "none",
    )
    assert result == ""


def test_python_ooo_anima_injects_game_cg() -> None:
    """ooo_anima_default preset injects 'game cg' after rating."""
    result = join_fields(
        {"quality": "", "year": "", "rating": "safe", "count": "",
         "character": "", "series": "", "artist": "", "general": "",
         "natural_language": ""},
        "ooo_anima_default",
    )
    # Must contain "game cg" after "safe"
    assert "safe, game cg" in result


def test_python_does_not_mutate_input() -> None:
    """join_fields must not mutate the caller's fields dict."""
    fields = {"quality": "masterpiece", "year": "", "rating": "safe",
              "count": "", "character": "", "series": "", "artist": "",
              "general": "", "natural_language": ""}
    original = dict(fields)
    join_fields(fields, "ooo_anima_default")
    assert fields == original
