# anima-prompt-helper — Local CI Check Runner

Runs the same steps as `.github/workflows/ci.yml` so you can catch regressions
before pushing. Three entry points are provided:

| Entry point              | Platform              |
|--------------------------|-----------------------|
| `scripts/run_all_checks.ps1` | Windows PowerShell 5.1 / 7+ |
| `scripts/run_all_checks.bat` | Windows CMD (thin wrapper) |
| `scripts/run_all_checks.sh`  | bash (WSL / Linux / macOS)  |

---

## What each step verifies

| Step | Name | What it checks |
|------|------|----------------|
| 1 | **py_compile** | Every `.py` file under the extension root parses without syntax errors. Mirrors the `lint` job. Fail-fast: if any file fails the script exits immediately. |
| 2 | **pytest** | Full test suite under `tests/` (`pytest -v --tb=short`). Mirrors `Run pytest` step. |
| 3 | **data_integrity** | Runs `scripts/check_data_integrity.py`, which validates palette structure, anima_spec, character_presets, i18n cross-references, and cross-file uniqueness. |
| 4 | **json_validation** | Parses every `*.json` under `data/`, `i18n/`, and `templates/` with `json.load`. Also validates that all node IDs referenced in `data/anima_workflow_*.json` links exist. |
| 5 | **benchmarks** | Runs `benchmark_composer.py`, `benchmark_palette_load.py`, and `benchmark_validate_route.py`. Checks they exit 0 and prints their last 6 lines of output. |

---

## How to interpret failures

### Step 1 fail — `[FAIL] Compile error: <file>`
A `.py` file has a syntax error. Open the indicated file, read the Python
traceback printed before the `[FAIL]` line, and fix the syntax.

### Step 2 fail — pytest output
Read the `FAILED` lines and short tracebacks printed by pytest. Run the
specific test file manually for more detail:
```
python -m pytest tests/test_composer.py -v
```

### Step 3 fail — data integrity
Each `ERROR:` or `WARN:` line names the file and the rule violated. Common
causes: duplicate tag IDs, uppercase in non-artist tags, underscore outside
the `score_N` exemption, cross-file tag collision.

### Step 4 fail — JSON parse error
The offending file has malformed JSON (trailing comma, unquoted key, etc.).
Run `python -c "import json; json.load(open('<file>', encoding='utf-8'))"` to
get the exact line/column.

### Step 5 fail — benchmark exited non-zero
Usually a missing `aiohttp` dependency (benchmark_validate_route.py needs it).
Install with `pip install aiohttp`. If a performance assertion was added to a
benchmark script, review its source for threshold checks.

---

## Pre-commit hooks

For automatic checks on every `git commit`, this project ships a
`.pre-commit-config.yaml` that mirrors the most critical CI steps (Python
syntax, data integrity, pytest, JSON validity, and Node syntax). Install once
with `pip install pre-commit && pre-commit install`; hooks run automatically
from then on. See [`docs/PRE_COMMIT.md`](../docs/PRE_COMMIT.md) for the full
hook list, manual invocation (`pre-commit run --all-files`), and the emergency
skip option.

---

## Build and release scripts

Two additional scripts are provided for packaging:

| Script | Platform | Purpose |
|--------|----------|---------|
| `scripts/build_dist.ps1` | Windows PowerShell | Runs `python -m build --sdist --wheel --outdir dist/` and reports output file sizes. Requires `pip install build` if not already installed. |
| `scripts/build_dist.sh`  | bash (WSL / Linux / macOS) | Same as above for Unix. |
| `scripts/zip_release.ps1` | Windows PowerShell | Builds `dist/anima-prompt-helper-v0.2.0.zip` using the same excludes as `.github/workflows/release.yml`. |
| `scripts/zip_release.sh`  | bash (WSL / Linux / macOS) | Same as above for Unix. |

Run from the extension root or any directory — the scripts resolve the root automatically.

```powershell
# Build sdist + wheel
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/build_dist.ps1

# Build release zip
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/zip_release.ps1
```

```bash
bash scripts/build_dist.sh
bash scripts/zip_release.sh
```

---

## Skipping benchmarks

Benchmarks take 10-30 seconds each. Skip them for a quick syntax+test cycle:

**PowerShell**
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_all_checks.ps1 -SkipBenchmarks
```

**CMD**
```cmd
scripts\run_all_checks.bat -SkipBenchmarks
```

**bash**
```bash
bash scripts/run_all_checks.sh --skip-benchmarks
```

---

## Example expected output (SkipBenchmarks)

```
############################################################
#   anima-prompt-helper  --  local CI runner               #
############################################################
Root   : /path/to/anima-prompt-helper
Python : Python 3.12.x
Date   : 2025-xx-xx xx:xx:xx
       Benchmarks : SKIPPED (-SkipBenchmarks)

=== Step 1 - Syntax check (py_compile) ===
       Found 42 .py files
[PASS] All 42 Python files compile cleanly.

=== Step 2 - pytest ===
... pytest output ...
[PASS] pytest passed (exit 0).

=== Step 3 - Data integrity check ===
       OK: data files are consistent
[PASS] check_data_integrity.py passed.

=== Step 4 - JSON file validation ===
       Checking 8 JSON file(s)...
       OK  data/anima_spec.json
       OK  data/character_presets.json
       ...
       No workflow JSON files found -- skipping node-id validation
[PASS] All 8 JSON file(s) valid.

=== Step 5 - Benchmarks (SKIPPED) ===
       Pass -SkipBenchmarks to skip. Remove flag to run.

############################################################
#                       SUMMARY                           #
############################################################
  Total time : 12s

  Step 1: [PASS] py_compile  (42 files)
  Step 2: [PASS] pytest
  Step 3: [PASS] data_integrity
  Step 4: [PASS] json_validation  (8 files)
  Step 5: [PASS] benchmarks  (skipped)

  RESULT: ALL CHECKS PASSED
```
