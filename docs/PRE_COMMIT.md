# Pre-commit Hooks

## What is pre-commit?

[pre-commit](https://pre-commit.com/) is a framework for managing Git hooks.
It automatically runs a set of fast checks every time you run `git commit`,
catching issues before they reach the repository.

## Installation

```bash
pip install pre-commit
pre-commit install
```

`pre-commit install` writes a hook script to `.git/hooks/pre-commit`. After
this, hooks run automatically on every `git commit`.

## Hooks that run on each commit

| Hook | Trigger | Purpose |
|------|---------|---------|
| `check-yaml` | any `.yaml`/`.yml` staged | Verifies YAML files parse without errors. |
| `check-json` | any `.json` staged | Verifies JSON files parse without errors. |
| `check-merge-conflict` | any file staged | Detects leftover `<<<<<<` / `>>>>>>` conflict markers. |
| `check-added-large-files` | any file staged | Blocks files larger than 512 KB from being committed. |
| `end-of-file-fixer` | any file staged (except `.svg`) | Ensures every file ends with a single newline. |
| `trailing-whitespace` | any file staged (except `.md`) | Strips trailing whitespace from lines. |
| `check-toml` | any `.toml` staged | Verifies TOML files (e.g. `pyproject.toml`) parse without errors. |
| `py-compile` | any `.py` staged | Runs `python -m py_compile` on each staged Python file to catch syntax errors instantly. |
| `data-integrity` | `data/*.json` or `i18n/*.json` staged | Runs `scripts/check_data_integrity.py` to validate palette structure, cross-file uniqueness, spec consistency, and i18n cross-references. |
| `pytest-fast` | `python/*.py` or `tests/*.py` staged | Runs the full test suite with `-x` (stop on first failure) for fast feedback. |
| `node-check` | any `.js` staged | Runs `node --check` on each staged JavaScript file to catch syntax errors. |

## Running all hooks manually

```bash
pre-commit run --all-files
```

Useful before a PR or after pulling changes.

## Skipping hooks in an emergency

```bash
git commit --no-verify
```

> **Warning:** `--no-verify` bypasses all hooks, including data integrity and
> syntax checks. Only use this when you have a strong reason (e.g. a
> work-in-progress checkpoint on a throwaway branch). Never use it on `main`.

## Updating hook versions

```bash
pre-commit autoupdate
```

This updates the `rev:` pins in `.pre-commit-config.yaml` to the latest
releases. Review and commit the diff.

## Relationship to CI and `scripts/run_all_checks`

The pre-commit hooks are a fast subset intended to catch the most common
mistakes at commit time. For a full local CI run (including benchmarks), use
`scripts/run_all_checks.ps1` / `.sh`. See `scripts/CHECKS.md` for details.
