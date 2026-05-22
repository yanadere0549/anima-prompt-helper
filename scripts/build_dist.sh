#!/usr/bin/env bash
# build_dist.sh — Build sdist + wheel for anima-prompt-helper
# Run from anywhere; the script resolves the extension root automatically.
# Does NOT install anything.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== anima-prompt-helper — build sdist + wheel ==="
echo "Root: $ROOT"

# Verify python -m build is available
if ! python -m build --version > /dev/null 2>&1; then
    echo "WARNING: 'python -m build' is not available." >&2
    echo "Install it first:" >&2
    echo "    pip install build" >&2
    exit 1
fi
echo "build version: $(python -m build --version)"

# Run build
cd "$ROOT"
python -m build --sdist --wheel --outdir dist/

# Verify outputs
DIST="$ROOT/dist"
TAR_GZ=$(ls "$DIST"/*.tar.gz 2>/dev/null || true)
WHL=$(ls "$DIST"/*.whl 2>/dev/null || true)

ok=1
[ -z "$TAR_GZ" ] && { echo "ERROR: No .tar.gz found in dist/" >&2; ok=0; }
[ -z "$WHL"    ] && { echo "ERROR: No .whl found in dist/"    >&2; ok=0; }

if [ "$ok" -eq 1 ]; then
    echo ""
    echo "Dist files:"
    for f in $TAR_GZ $WHL; do
        size=$(du -k "$f" | cut -f1)
        printf "  %-55s %8s KB\n" "$(basename "$f")" "$size"
    done
    echo ""
    echo "[PASS] Build succeeded."
    exit 0
else
    exit 1
fi
