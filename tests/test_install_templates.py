"""Tests for scripts/install_templates (.ps1 / .sh).

Creates a temporary directory tree that mimics a ComfyUI installation,
places real templates/*.json under the fake extension, then invokes the
installer in --dry-run mode and verifies the output.

On Windows the PowerShell script is tested via pwsh/powershell.
On Unix-like systems the bash script is tested via bash.
The test is skipped if neither interpreter is available.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths relative to the real extension root
# ---------------------------------------------------------------------------
_THIS_FILE  = Path(__file__).resolve()
_EXT_ROOT   = _THIS_FILE.parent.parent          # …/anima-prompt-helper/
_TEMPLATES  = _EXT_ROOT / "templates"


# ---------------------------------------------------------------------------
# Helpers: find interpreter
# ---------------------------------------------------------------------------

def _find_pwsh() -> str | None:
    """Return path to pwsh or powershell, or None if unavailable."""
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _find_bash() -> str | None:
    """Return path to bash, or None if unavailable."""
    return shutil.which("bash")


# ---------------------------------------------------------------------------
# Fixture: temporary ComfyUI tree
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_comfy(tmp_path: Path) -> Path:
    """
    Build:
      tmp_path/
        user/default/workflows/          (target, pre-created)
        custom_nodes/
          anima-prompt-helper/
            scripts/
              install_templates.ps1
              install_templates.sh
            templates/
              *.json   (copied from real extension)
    Returns tmp_path (the fake ComfyUI root).
    """
    ext = tmp_path / "custom_nodes" / "anima-prompt-helper"
    scripts_dir  = ext / "scripts"
    templates_dir = ext / "templates"
    workflows_dir = tmp_path / "user" / "default" / "workflows"

    for d in (scripts_dir, templates_dir, workflows_dir):
        d.mkdir(parents=True)

    # Copy real templates
    real_jsons = list(_TEMPLATES.glob("*.json"))
    assert len(real_jsons) >= 1, "No template JSON files found in real extension"
    for src in real_jsons:
        shutil.copy2(src, templates_dir / src.name)

    # Copy scripts (needed so the script can resolve its own $PSScriptRoot / BASH_SOURCE)
    for script_name in ("install_templates.ps1", "install_templates.sh"):
        src_script = _EXT_ROOT / "scripts" / script_name
        if src_script.exists():
            shutil.copy2(src_script, scripts_dir / script_name)

    return tmp_path


# ---------------------------------------------------------------------------
# Helpers: count real templates
# ---------------------------------------------------------------------------

def _template_count() -> int:
    return len(list(_TEMPLATES.glob("*.json")))


# ---------------------------------------------------------------------------
# Windows: PowerShell test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="PowerShell test runs on Windows only",
)
def test_dry_run_powershell(fake_comfy: Path) -> None:
    pwsh = _find_pwsh()
    if pwsh is None:
        pytest.skip("pwsh / powershell not found on PATH")

    script = fake_comfy / "custom_nodes" / "anima-prompt-helper" / "scripts" / "install_templates.ps1"
    result = subprocess.run(
        [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-DryRun"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Script exited {result.returncode}:\n{result.stderr}"

    stdout = result.stdout + result.stderr
    n = _template_count()

    # Expect "would copy: N" somewhere in the summary line
    assert f"would copy: {n}" in stdout or f"would copy {n}" in stdout, (
        f"Expected 'would copy: {n}' or 'would copy {n}' in output.\nGot:\n{stdout}"
    )

    # Verify no files were actually written to workflows dir
    workflows_dir = fake_comfy / "user" / "default" / "workflows"
    assert list(workflows_dir.iterdir()) == [], "Dry-run must not write any files"


# ---------------------------------------------------------------------------
# Unix: bash test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Bash test skipped on Windows (use PowerShell test instead)",
)
def test_dry_run_bash(fake_comfy: Path) -> None:
    bash = _find_bash()
    if bash is None:
        pytest.skip("bash not found on PATH")

    script = fake_comfy / "custom_nodes" / "anima-prompt-helper" / "scripts" / "install_templates.sh"
    result = subprocess.run(
        [bash, str(script), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Script exited {result.returncode}:\n{result.stderr}"

    stdout = result.stdout + result.stderr
    n = _template_count()

    assert f"would copy: {n}" in stdout or f"would copy {n}" in stdout, (
        f"Expected 'would copy: {n}' or 'would copy {n}' in output.\nGot:\n{stdout}"
    )

    # Verify no files were actually written to workflows dir
    workflows_dir = fake_comfy / "user" / "default" / "workflows"
    assert list(workflows_dir.iterdir()) == [], "Dry-run must not write any files"
