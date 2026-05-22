#!/usr/bin/env python3
"""Sanity-check .pre-commit-config.yaml structure.

Usage:
    python scripts/test_precommit_config.py

Exits 0 if the YAML structure is valid; exits 1 on any structural error.
If PyYAML is not installed, prints a warning and exits 0 (non-blocking).
"""
from __future__ import annotations

import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"


def main() -> int:
    # ------------------------------------------------------------------
    # 1. Check PyYAML availability
    # ------------------------------------------------------------------
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        print(
            "WARNING: PyYAML not installed — skipping .pre-commit-config.yaml parse.\n"
            "         Install with: pip install pyyaml"
        )
        return 0

    # ------------------------------------------------------------------
    # 2. Load the file
    # ------------------------------------------------------------------
    if not CONFIG_PATH.exists():
        print(f"ERROR: config file not found: {CONFIG_PATH}", file=sys.stderr)
        return 1

    try:
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(f"ERROR: YAML parse error in {CONFIG_PATH}:\n  {exc}", file=sys.stderr)
        return 1

    if not isinstance(config, dict):
        print("ERROR: top-level value is not a mapping (expected a dict).", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # 3. Structural validation
    # ------------------------------------------------------------------
    errors: list[str] = []

    repos = config.get("repos")
    if repos is None:
        errors.append("missing top-level 'repos' key")
    elif not isinstance(repos, list):
        errors.append("'repos' must be a list")
    else:
        hook_count = 0
        for repo_idx, repo in enumerate(repos):
            repo_label = repo.get("repo", f"<repo[{repo_idx}]>")

            if "repo" not in repo:
                errors.append(f"repos[{repo_idx}]: missing 'repo' key")

            hooks = repo.get("hooks")
            if hooks is None:
                errors.append(f"{repo_label}: missing 'hooks' key")
            elif not isinstance(hooks, list):
                errors.append(f"{repo_label}: 'hooks' must be a list")
            else:
                for hook_idx, hook in enumerate(hooks):
                    if "id" not in hook:
                        errors.append(
                            f"{repo_label} hooks[{hook_idx}]: missing 'id' key"
                        )
                    hook_count += 1

    # ------------------------------------------------------------------
    # 4. Report
    # ------------------------------------------------------------------
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"OK: .pre-commit-config.yaml is valid - {hook_count} hook(s) defined.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
