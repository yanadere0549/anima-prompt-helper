#!/usr/bin/env bash
# run_all_checks.sh — local CI runner for anima-prompt-helper (bash version)
# Mirrors .github/workflows/ci.yml
#
# Usage:
#   bash scripts/run_all_checks.sh
#   bash scripts/run_all_checks.sh --skip-benchmarks
#
# Exit code 0 only if all steps pass.

set -euo pipefail

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'   # no colour

pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
info()  { echo -e "${YELLOW}       $*${NC}"; }
step()  { echo -e "\n${CYAN}=== $* ===${NC}"; }

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------
SKIP_BENCHMARKS=0
for arg in "$@"; do
    case "$arg" in
        --skip-benchmarks|-SkipBenchmarks) SKIP_BENCHMARKS=1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Python detection — prefer interpreter that has pytest installed.
# On Windows+MSYS the venv "python" may shadow the system Python, so we
# enumerate every "python" / "python3" on PATH and pick the first with pytest.
# ---------------------------------------------------------------------------
PYTHON=""
PYTHON_FALLBACK=""

# Collect all python/python3 paths from PATH (type -a on bash)
ALL_PY_PATHS=()
while IFS= read -r p; do
    [ -n "$p" ] && ALL_PY_PATHS+=("$p")
done < <( { type -a python 2>/dev/null; type -a python3 2>/dev/null; } | grep -o '/[^ ]*' | awk '!seen[$0]++' )

for py in "${ALL_PY_PATHS[@]}"; do
    if [ -z "$PYTHON" ]; then
        if "$py" --version >/dev/null 2>&1; then
            if "$py" -c "import pytest" 2>/dev/null; then
                PYTHON="$py"
            else
                [ -z "$PYTHON_FALLBACK" ] && PYTHON_FALLBACK="$py"
            fi
        fi
    fi
done

[ -z "$PYTHON" ] && PYTHON="$PYTHON_FALLBACK"
if [ -z "$PYTHON" ]; then
    fail "Python not found. Install Python 3.10+ and ensure it is on PATH."
    exit 1
fi

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
START_TIME=$(date +%s)

# Step tracking arrays (bash 3 compatible)
STEP_NAMES=()
STEP_PASSED=()

record_step() {
    local name="$1" passed="$2"
    STEP_NAMES+=("$name")
    STEP_PASSED+=("$passed")
}

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}############################################################${NC}"
echo -e "${CYAN}#   anima-prompt-helper  --  local CI runner               #${NC}"
echo -e "${CYAN}############################################################${NC}"
echo "Root   : $EXT_ROOT"
echo "Python : $($PYTHON --version 2>&1)"
echo "Date   : $(date '+%Y-%m-%d %H:%M:%S')"
[ "$SKIP_BENCHMARKS" -eq 1 ] && info "Benchmarks : SKIPPED (--skip-benchmarks)"

# ---------------------------------------------------------------------------
# STEP 1 — py_compile (fail-fast)
# ---------------------------------------------------------------------------
step "Step 1 - Syntax check (py_compile)"

mapfile -t PY_FILES < <(
    find "$EXT_ROOT" -name '*.py' \
        -not -path '*/.venv*' \
        -not -path '*/.git/*' \
        -not -path '*/node_modules/*' \
        -not -path '*/__pycache__/*'
)

echo "       Found ${#PY_FILES[@]} .py files"

COMPILE_ERROR=0
for f in "${PY_FILES[@]}"; do
    if ! "$PYTHON" -m py_compile "$f" 2>/dev/null; then
        fail "Compile error: $f"
        COMPILE_ERROR=1
    fi
done

if [ "$COMPILE_ERROR" -ne 0 ]; then
    fail "py_compile failed. Fix syntax errors before proceeding."
    record_step "py_compile" 0
    END_TIME=$(date +%s)
    echo -e "\n${RED}[SUMMARY] ABORTED after step 1 (total $((END_TIME - START_TIME))s)${NC}"
    exit 1
fi

pass "All ${#PY_FILES[@]} Python files compile cleanly."
record_step "py_compile" 1

# ---------------------------------------------------------------------------
# STEP 2 — pytest
# ---------------------------------------------------------------------------
step "Step 2 - pytest"

cd "$EXT_ROOT"
set +e
"$PYTHON" -m pytest tests -v --tb=short
PYTEST_CODE=$?
set -e

if [ "$PYTEST_CODE" -eq 0 ]; then
    pass "pytest passed (exit $PYTEST_CODE)."
    record_step "pytest" 1
else
    fail "pytest failed (exit $PYTEST_CODE)."
    record_step "pytest" 0
fi

# ---------------------------------------------------------------------------
# STEP 3 — data integrity check
# ---------------------------------------------------------------------------
step "Step 3 - Data integrity check"

cd "$EXT_ROOT"
set +e
"$PYTHON" "$SCRIPT_DIR/check_data_integrity.py" 2>&1 | sed 's/^/       /'
INTEGRITY_CODE=${PIPESTATUS[0]}
set -e

if [ "$INTEGRITY_CODE" -eq 0 ]; then
    pass "check_data_integrity.py passed."
    record_step "data_integrity" 1
else
    fail "check_data_integrity.py failed (exit $INTEGRITY_CODE)."
    record_step "data_integrity" 0
fi

# ---------------------------------------------------------------------------
# STEP 4 — JSON validation
# ---------------------------------------------------------------------------
step "Step 4 - JSON file validation"

JSON_FILES=()
for dir in data i18n templates; do
    target="$EXT_ROOT/$dir"
    if [ -d "$target" ]; then
        while IFS= read -r -d '' f; do
            JSON_FILES+=("$f")
        done < <(find "$target" -name '*.json' -print0)
    fi
done

echo "       Checking ${#JSON_FILES[@]} JSON file(s)..."

JSON_FAILED=0
for jf in "${JSON_FILES[@]}"; do
    relpath="${jf#$EXT_ROOT/}"
    if "$PYTHON" - "$jf" <<'PYEOF' 2>/dev/null
import json, sys
json.load(open(sys.argv[1], encoding='utf-8'))
PYEOF
    then
        echo "       OK  $relpath"
    else
        fail "  JSON parse error: $relpath"
        JSON_FAILED=1
    fi
done

# Workflow node-ID validation
cd "$EXT_ROOT"
set +e
WF_OUTPUT=$("$PYTHON" - <<PYEOF 2>&1
import json, sys, pathlib

workflow_files = list(pathlib.Path("$EXT_ROOT").rglob("data/anima_workflow_*.json"))
if not workflow_files:
    print("No workflow JSON files found -- skipping node-id validation")
    sys.exit(0)

errors = []
for wf_path in workflow_files:
    try:
        data = json.loads(wf_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{wf_path}: JSON parse error: {exc}")
        continue
    nodes = data.get("nodes", [])
    node_ids = {n["id"] for n in nodes if "id" in n}
    links = data.get("links", [])
    for link in links:
        if len(link) < 5:
            continue
        if link[1] not in node_ids:
            errors.append(f"{wf_path}: link {link[0]} references missing src node {link[1]}")
        if link[3] not in node_ids:
            errors.append(f"{wf_path}: link {link[0]} references missing dst node {link[3]}")

if errors:
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
print(f"OK: validated {len(workflow_files)} workflow file(s)")
PYEOF
)
WF_CODE=$?
set -e

echo "$WF_OUTPUT" | sed 's/^/       /'

if [ "$JSON_FAILED" -eq 0 ] && [ "$WF_CODE" -eq 0 ]; then
    pass "All ${#JSON_FILES[@]} JSON file(s) valid."
    record_step "json_validation" 1
else
    [ "$JSON_FAILED" -ne 0 ] && fail "JSON parse errors found."
    [ "$WF_CODE" -ne 0 ]     && fail "Workflow node-ID validation failed."
    record_step "json_validation" 0
fi

# ---------------------------------------------------------------------------
# STEP 5 — Benchmarks
# ---------------------------------------------------------------------------
if [ "$SKIP_BENCHMARKS" -eq 1 ]; then
    step "Step 5 - Benchmarks (SKIPPED)"
    info "Pass --skip-benchmarks to skip. Remove flag to run."
    record_step "benchmarks" 1
else
    step "Step 5 - Benchmarks"

    mapfile -t BENCH_SCRIPTS < <(find "$SCRIPT_DIR" -maxdepth 1 -name "benchmark_*.py" | sort)
    echo "       Found ${#BENCH_SCRIPTS[@]} benchmark script(s)."

    BENCH_FAILED=0
    for bs in "${BENCH_SCRIPTS[@]}"; do
        bname="$(basename "$bs")"
        echo -e "\n  ${YELLOW}--- $bname ---${NC}"
        cd "$EXT_ROOT"
        set +e
        BENCH_OUT=$("$PYTHON" "$bs" 2>&1)
        BENCH_CODE=$?
        set -e
        # Print last 6 lines
        echo "$BENCH_OUT" | tail -n 6 | sed 's/^/       /'
        if [ "$BENCH_CODE" -ne 0 ]; then
            fail "$bname exited $BENCH_CODE"
            BENCH_FAILED=1
        else
            pass "$bname completed."
        fi
    done

    if [ "$BENCH_FAILED" -eq 0 ]; then
        record_step "benchmarks" 1
    else
        record_step "benchmarks" 0
    fi
fi

# ---------------------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------------------
END_TIME=$(date +%s)
TOTAL_SEC=$((END_TIME - START_TIME))

ALL_PASSED=1
for p in "${STEP_PASSED[@]}"; do
    [ "$p" -eq 0 ] && ALL_PASSED=0 && break
done

echo ""
echo -e "${CYAN}############################################################${NC}"
echo -e "${CYAN}#                       SUMMARY                           #${NC}"
echo -e "${CYAN}############################################################${NC}"
echo "  Total time : ${TOTAL_SEC}s"
echo ""

N=${#STEP_NAMES[@]}
for (( i=0; i<N; i++ )); do
    sname="${STEP_NAMES[$i]}"
    spassed="${STEP_PASSED[$i]}"
    stepnum=$((i + 1))
    if [ "$spassed" -eq 1 ]; then
        echo -e "  Step ${stepnum}: ${GREEN}[PASS]${NC} ${sname}"
    else
        echo -e "  Step ${stepnum}: ${RED}[FAIL]${NC} ${sname}"
    fi
done

echo ""
if [ "$ALL_PASSED" -eq 1 ]; then
    echo -e "  ${GREEN}RESULT: ALL CHECKS PASSED${NC}"
    exit 0
else
    echo -e "  ${RED}RESULT: ONE OR MORE CHECKS FAILED${NC}"
    exit 1
fi
