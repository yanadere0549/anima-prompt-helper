#!/usr/bin/env bash
# zip_release.sh — Build a local release zip matching the GitHub Actions release.yml output.
# Output: dist/anima-prompt-helper-v0.2.0.zip
# Does NOT install anything.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="v0.2.0"
ZIP_NAME="anima-prompt-helper-${VERSION}.zip"
DIST_DIR="$ROOT/dist"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"

echo "=== anima-prompt-helper — zip release ==="
echo "Root   : $ROOT"
echo "Output : $ZIP_PATH"

mkdir -p "$DIST_DIR"

# Remove stale zip
[ -f "$ZIP_PATH" ] && rm -f "$ZIP_PATH"

cd "$ROOT"

# Build zip excluding same paths as release.yml
zip -r "$ZIP_PATH" . \
    --exclude ".git/*" \
    --exclude "*/__pycache__/*" \
    --exclude "*/*.pyc" \
    --exclude ".github/*" \
    --exclude ".venv*/*" \
    --exclude "node_modules/*" \
    --exclude "data/anima_workflow_*" \
    --exclude "*.egg-info/*" \
    --exclude "dist/*" \
    --exclude "build/*" \
    --exclude ".pytest_cache/*"

# Report
size=$(du -k "$ZIP_PATH" | cut -f1)
echo ""
echo "Created: $ZIP_PATH"
echo "Size   : ${size} KB"
echo "[PASS] zip_release succeeded."
exit 0
