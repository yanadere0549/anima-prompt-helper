#!/usr/bin/env bash
# install_templates.sh — Install anima-prompt-helper workflow templates into ComfyUI.
#
# Copies templates/*.json into <ComfyUI>/user/default/workflows/ with the
# prefix "anima-prompt-helper - " so they appear grouped in the workflow picker.
#
# Usage:
#   bash scripts/install_templates.sh
#   bash scripts/install_templates.sh --force
#   bash scripts/install_templates.sh --dry-run
#   bash scripts/install_templates.sh --quiet
#
# Options:
#   --force     Overwrite existing files in the target directory.
#   --dry-run   Print what would be copied without writing any files.
#   --quiet     Suppress per-file messages; print only the final summary.

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FORCE=0
DRY_RUN=0
QUIET=0

for arg in "$@"; do
    case "$arg" in
        --force|-Force)    FORCE=1    ;;
        --dry-run|-DryRun) DRY_RUN=1 ;;
        --quiet|-Quiet)    QUIET=1    ;;
        *)
            echo "[WARN] Unknown argument: $arg" >&2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Path detection
# scripts/ -> extension root -> ComfyUI root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMFY_ROOT="$(cd "$EXT_ROOT/../.." && pwd)"
TARGET_DIR="$COMFY_ROOT/user/default/workflows"
TEMPLATE_DIR="$EXT_ROOT/templates"
PREFIX="anima-prompt-helper - "

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
msg() {
    [ "$QUIET" -eq 0 ] && echo "$*"
}

# ---------------------------------------------------------------------------
# Validate template directory
# ---------------------------------------------------------------------------
if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "[ERROR] Templates directory not found: $TEMPLATE_DIR" >&2
    exit 1
fi

# Collect .json files
TEMPLATES=()
while IFS= read -r -d '' f; do
    TEMPLATES+=("$f")
done < <(find "$TEMPLATE_DIR" -maxdepth 1 -name "*.json" -print0 | sort -z)

if [ "${#TEMPLATES[@]}" -eq 0 ]; then
    echo "[WARN] No .json files found in: $TEMPLATE_DIR"
    exit 0
fi

# ---------------------------------------------------------------------------
# Create target directory (unless dry-run)
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" -eq 1 ]; then
    msg "[DRY RUN] Target directory: $TARGET_DIR"
else
    if [ ! -d "$TARGET_DIR" ]; then
        mkdir -p "$TARGET_DIR"
        msg "Created directory: $TARGET_DIR"
    fi
fi

# ---------------------------------------------------------------------------
# Process each template
# ---------------------------------------------------------------------------
COPIED=0
SKIPPED=0

for tmpl in "${TEMPLATES[@]}"; do
    basename_tmpl="$(basename "$tmpl")"
    dest_name="${PREFIX}${basename_tmpl}"
    dest_path="$TARGET_DIR/$dest_name"

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  would copy: $basename_tmpl -> $dest_name"
        COPIED=$((COPIED + 1))
        continue
    fi

    if [ -e "$dest_path" ]; then
        if [ "$FORCE" -eq 1 ]; then
            cp "$tmpl" "$dest_path"
            msg "  overwrite : $dest_name"
            COPIED=$((COPIED + 1))
        else
            msg "  skip      : $dest_name (already exists; use --force to overwrite)"
            SKIPPED=$((SKIPPED + 1))
        fi
    else
        cp "$tmpl" "$dest_path"
        msg "  copy      : $dest_name"
        COPIED=$((COPIED + 1))
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry-run summary: would copy ${COPIED} template(s)."
else
    echo "Done. Copied: ${COPIED}  Skipped: ${SKIPPED}"
fi

exit 0
