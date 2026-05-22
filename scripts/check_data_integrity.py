#!/usr/bin/env python3
"""Cross-file integrity check for anima-prompt-helper data files."""
from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

EXTENSION_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str   # "error" or "warning"
    file: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.file}: {self.message}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCORE_EXEMPT_RE = re.compile(r"^score_\d+(_up)?$")


def _is_score_exempt(tag: str) -> bool:
    return bool(_SCORE_EXEMPT_RE.match(tag))


def _load_json(path: Path) -> tuple[dict | None, str | None]:
    """Return (data, error_msg). error_msg is None on success."""
    if not path.exists():
        return None, f"file not found: {path}"
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error in {path}: {exc}"


def _collect_all_tags(data: dict) -> set[str]:
    """Collect all primary tag values from a palette data dict."""
    tags: set[str] = set()
    for cat in data.get("categories", []):
        for t in cat.get("tags", []):
            v = t.get("tag", "")
            if v:
                tags.add(v)
    return tags


def _check_palette_structure(
    data: dict,
    file_label: str,
    *,
    require_order_min: int | None = None,
) -> list[Issue]:
    """Shared structural checks for both palette files."""
    issues: list[Issue] = []

    if data.get("version") not in ("1.0", "1.1"):
        issues.append(Issue("error", file_label, f"expected version '1.0' or '1.1', got {data.get('version')!r}"))

    categories = data.get("categories")
    if not isinstance(categories, list):
        issues.append(Issue("error", file_label, "'categories' must be a list"))
        return issues

    seen_cat_ids: set[str] = set()
    for cat in categories:
        cat_id = cat.get("id", "")
        if not cat_id:
            issues.append(Issue("error", file_label, "category missing 'id'"))
        elif cat_id in seen_cat_ids:
            issues.append(Issue("error", file_label, f"duplicate category id: {cat_id!r}"))
        else:
            seen_cat_ids.add(cat_id)

        if not cat.get("label"):
            issues.append(Issue("error", file_label, f"category {cat_id!r} missing 'label'"))

        order = cat.get("order")
        if not isinstance(order, int):
            issues.append(Issue("error", file_label, f"category {cat_id!r} 'order' must be int, got {order!r}"))
        elif require_order_min is not None and order < require_order_min:
            issues.append(Issue(
                "error", file_label,
                f"category {cat_id!r} order={order} must be >= {require_order_min}"
            ))

        tags = cat.get("tags")
        if not isinstance(tags, list):
            issues.append(Issue("error", file_label, f"category {cat_id!r} 'tags' must be a list"))
            continue

        is_artist_cat = (cat_id == "artist")
        is_natural_lang_cat = (cat_id == "natural_language")
        seen_tags: set[str] = set()

        for tag_obj in tags:
            tag_val = tag_obj.get("tag", "")
            if not isinstance(tag_val, str) or not tag_val:
                issues.append(Issue("error", file_label, f"category {cat_id!r}: tag entry missing 'tag' string"))
                continue

            # must have tag: str and optionally display: str (no enforcement that display must exist)
            # (per spec: "either display: str or no display")

            # Duplicate within category
            if tag_val in seen_tags:
                issues.append(Issue(
                    "error", file_label,
                    f"category {cat_id!r}: duplicate tag value {tag_val!r}"
                ))
            else:
                seen_tags.add(tag_val)

            if is_artist_cat:
                if not tag_val.startswith("@"):
                    issues.append(Issue(
                        "error", file_label,
                        f"category 'artist': tag {tag_val!r} must start with '@'"
                    ))
            elif not is_natural_lang_cat:
                # Lowercase check
                if tag_val != tag_val.lower():
                    issues.append(Issue(
                        "error", file_label,
                        f"category {cat_id!r}: tag {tag_val!r} contains uppercase letters"
                    ))
                # Underscore check (except score_N / score_N_up)
                if "_" in tag_val and not _is_score_exempt(tag_val):
                    issues.append(Issue(
                        "error", file_label,
                        f"category {cat_id!r}: tag {tag_val!r} contains underscore (not score_N exempt)"
                    ))

    return issues


# ---------------------------------------------------------------------------
# Individual checkers
# ---------------------------------------------------------------------------

def check_tag_palette() -> list[Issue]:
    """Check data/tag_palette.json."""
    path = EXTENSION_ROOT / "data" / "tag_palette.json"
    data, err = _load_json(path)
    if err:
        return [Issue("error", "data/tag_palette.json", err)]
    return _check_palette_structure(data, "data/tag_palette.json")


def check_tag_palette_extras() -> list[Issue]:
    """Check data/tag_palette_extras.json against rules + cross-file uniqueness."""
    issues: list[Issue] = []
    path = EXTENSION_ROOT / "data" / "tag_palette_extras.json"
    data, err = _load_json(path)
    if err:
        return [Issue("error", "data/tag_palette_extras.json", err)]

    issues.extend(
        _check_palette_structure(data, "data/tag_palette_extras.json", require_order_min=200)
    )

    # Cross-file: no tag from extras may exist in main palette
    main_path = EXTENSION_ROOT / "data" / "tag_palette.json"
    main_data, main_err = _load_json(main_path)
    if main_err:
        issues.append(Issue("warning", "data/tag_palette_extras.json",
                            f"cannot perform cross-file check: {main_err}"))
    else:
        main_tags = _collect_all_tags(main_data)
        extras_tags = _collect_all_tags(data)
        for t in sorted(extras_tags):
            if t in main_tags:
                issues.append(Issue(
                    "error", "data/tag_palette_extras.json",
                    f"tag {t!r} already exists in tag_palette.json (cross-file duplicate)"
                ))

    return issues


def check_anima_spec() -> list[Issue]:
    """Check data/anima_spec.json."""
    issues: list[Issue] = []
    path = EXTENSION_ROOT / "data" / "anima_spec.json"
    data, err = _load_json(path)
    if err:
        return [Issue("error", "data/anima_spec.json", err)]

    label = "data/anima_spec.json"

    if data.get("version") != "1.0":
        issues.append(Issue("error", label, f"expected version '1.0', got {data.get('version')!r}"))

    # canonical_order: exactly 9 entries
    canonical_order = data.get("canonical_order", [])
    if not isinstance(canonical_order, list):
        issues.append(Issue("error", label, "'canonical_order' must be a list"))
    elif len(canonical_order) != 9:
        issues.append(Issue(
            "error", label,
            f"'canonical_order' must have exactly 9 entries, got {len(canonical_order)}"
        ))

    # field_specs: must have entry for every id in canonical_order
    field_specs = data.get("field_specs", {})
    if not isinstance(field_specs, dict):
        issues.append(Issue("error", label, "'field_specs' must be a dict"))
    else:
        for fid in canonical_order:
            if fid not in field_specs:
                issues.append(Issue(
                    "error", label,
                    f"'field_specs' missing entry for canonical_order id {fid!r}"
                ))

    # model_presets: must have anima_base and ooo_anima
    model_presets = data.get("model_presets", {})
    if not isinstance(model_presets, dict):
        issues.append(Issue("error", label, "'model_presets' must be a dict"))
    else:
        for required_preset in ("anima_base", "ooo_anima"):
            if required_preset not in model_presets:
                issues.append(Issue(
                    "error", label,
                    f"'model_presets' missing required preset {required_preset!r}"
                ))
            else:
                preset = model_presets[required_preset]
                for required_key in ("default_prefix_quality", "default_negative"):
                    if required_key not in preset:
                        issues.append(Issue(
                            "error", label,
                            f"preset {required_preset!r} missing key {required_key!r}"
                        ))
                rec = preset.get("recommended", {})
                if not isinstance(rec, dict):
                    issues.append(Issue(
                        "error", label,
                        f"preset {required_preset!r} 'recommended' must be a dict"
                    ))
                else:
                    for rec_key in ("sampler", "steps", "cfg"):
                        if rec_key not in rec:
                            issues.append(Issue(
                                "error", label,
                                f"preset {required_preset!r} 'recommended' missing key {rec_key!r}"
                            ))

    # validation_rules: rating_allowed_values must equal field_specs.rating.options exactly
    validation_rules = data.get("validation_rules", {})
    rating_allowed = validation_rules.get("rating_allowed_values", [])
    rating_options = field_specs.get("rating", {}).get("options", []) if isinstance(field_specs, dict) else []
    if sorted(rating_allowed) != sorted(rating_options):
        issues.append(Issue(
            "error", label,
            f"validation_rules.rating_allowed_values {rating_allowed} != "
            f"field_specs.rating.options {rating_options}"
        ))

    # Every regex in underscore_forbidden_except must compile
    uf_except = validation_rules.get("underscore_forbidden_except", [])
    if isinstance(uf_except, list):
        for pattern in uf_except:
            try:
                re.compile(pattern)
            except re.error as exc:
                issues.append(Issue(
                    "error", label,
                    f"underscore_forbidden_except pattern {pattern!r} is invalid regex: {exc}"
                ))

    return issues


def check_character_presets() -> list[Issue]:
    """Check data/character_presets.json."""
    issues: list[Issue] = []
    path = EXTENSION_ROOT / "data" / "character_presets.json"
    data, err = _load_json(path)
    if err:
        return [Issue("error", "data/character_presets.json", err)]

    label = "data/character_presets.json"
    presets = data.get("presets")
    if not isinstance(presets, list):
        issues.append(Issue("error", label, "'presets' must be a list"))
        return issues

    seen_ids: set[str] = set()
    for preset in presets:
        pid = preset.get("id", "")
        if not pid:
            issues.append(Issue("error", label, "preset missing 'id'"))
        elif pid in seen_ids:
            issues.append(Issue("error", label, f"duplicate preset id: {pid!r}"))
        else:
            seen_ids.add(pid)

        # character and series: lowercase, no underscores
        for field_name in ("character", "series"):
            val = preset.get(field_name, "")
            if not isinstance(val, str):
                continue
            if val and val != val.lower():
                issues.append(Issue(
                    "error", label,
                    f"preset {pid!r} field {field_name!r}={val!r} contains uppercase"
                ))
            if val and "_" in val:
                issues.append(Issue(
                    "error", label,
                    f"preset {pid!r} field {field_name!r}={val!r} contains underscore"
                ))

        # essential_general_tags: lowercase, no underscores (except score_N)
        for tag in preset.get("essential_general_tags", []):
            if not isinstance(tag, str):
                continue
            if tag != tag.lower():
                issues.append(Issue(
                    "error", label,
                    f"preset {pid!r} essential_general_tags {tag!r} contains uppercase"
                ))
            if "_" in tag and not _is_score_exempt(tag):
                issues.append(Issue(
                    "error", label,
                    f"preset {pid!r} essential_general_tags {tag!r} contains underscore"
                ))

    return issues


def check_i18n() -> list[Issue]:
    """Check i18n/ja.json (optional file — absence is a warning)."""
    issues: list[Issue] = []
    path = EXTENSION_ROOT / "i18n" / "ja.json"
    label = "i18n/ja.json"

    if not path.exists():
        issues.append(Issue("warning", label, "file absent (i18n is optional)"))
        return issues

    data, err = _load_json(path)
    if err:
        return [Issue("error", label, err)]

    if data.get("locale") != "ja":
        issues.append(Issue("error", label, f"expected locale 'ja', got {data.get('locale')!r}"))

    tag_labels = data.get("tag_labels")
    if not isinstance(tag_labels, dict):
        issues.append(Issue("error", label, "'tag_labels' must be a dict"))
        tag_labels = {}

    # Build tag sets from both palette files for cross-reference
    all_palette_tags: set[str] = set()
    for palette_filename in ("tag_palette.json", "tag_palette_extras.json"):
        p_path = EXTENSION_ROOT / "data" / palette_filename
        p_data, p_err = _load_json(p_path)
        if p_err is None:
            all_palette_tags.update(_collect_all_tags(p_data))

    # Each key in tag_labels should exist in some palette file (warning if not)
    for key in tag_labels:
        if key not in all_palette_tags:
            issues.append(Issue(
                "warning", label,
                f"tag_labels key {key!r} not found in any palette (may be a future addition)"
            ))

    # category_labels -> must match category ids in tag_palette.json
    main_path = EXTENSION_ROOT / "data" / "tag_palette.json"
    main_data, main_err = _load_json(main_path)
    if main_err is None:
        main_cat_ids = {c["id"] for c in main_data.get("categories", []) if "id" in c}
        for key in data.get("category_labels", {}):
            if key not in main_cat_ids:
                issues.append(Issue(
                    "error", label,
                    f"category_labels key {key!r} not found in tag_palette.json categories"
                ))

    # category_labels_extras -> must match category ids in tag_palette_extras.json
    extras_path = EXTENSION_ROOT / "data" / "tag_palette_extras.json"
    extras_data, extras_err = _load_json(extras_path)
    if extras_err is None:
        extras_cat_ids = {c["id"] for c in extras_data.get("categories", []) if "id" in c}
        for key in data.get("category_labels_extras", {}):
            if key not in extras_cat_ids:
                issues.append(Issue(
                    "error", label,
                    f"category_labels_extras key {key!r} not found in tag_palette_extras.json categories"
                ))

    return issues


def check_cross_references() -> list[Issue]:
    """Cross-file reference checks."""
    issues: list[Issue] = []

    # Build all palette tags union
    all_palette_tags: set[str] = set()
    for palette_filename in ("tag_palette.json", "tag_palette_extras.json"):
        p_path = EXTENSION_ROOT / "data" / palette_filename
        p_data, p_err = _load_json(p_path)
        if p_err is None:
            all_palette_tags.update(_collect_all_tags(p_data))

    # For each character preset's essential_general_tags,
    # warn if < 50% appear in either palette
    presets_path = EXTENSION_ROOT / "data" / "character_presets.json"
    presets_data, presets_err = _load_json(presets_path)
    if presets_err is None:
        for preset in presets_data.get("presets", []):
            pid = preset.get("id", "?")
            egt = preset.get("essential_general_tags", [])
            if not egt:
                continue
            found = sum(1 for t in egt if t in all_palette_tags)
            ratio = found / len(egt)
            if ratio < 0.5:
                issues.append(Issue(
                    "warning", "data/character_presets.json",
                    f"preset {pid!r}: only {found}/{len(egt)} essential_general_tags "
                    f"appear in palette files ({ratio:.0%} < 50%)"
                ))

    # Check aliases in tag_palette.json: no alias may collide with another tag's primary value
    main_path = EXTENSION_ROOT / "data" / "tag_palette.json"
    main_data, main_err = _load_json(main_path)
    if main_err is None:
        primary_tags: set[str] = _collect_all_tags(main_data)
        for cat in main_data.get("categories", []):
            cat_id = cat.get("id", "?")
            for tag_obj in cat.get("tags", []):
                primary = tag_obj.get("tag", "")
                for alias in tag_obj.get("aliases", []):
                    if alias in primary_tags and alias != primary:
                        issues.append(Issue(
                            "error", "data/tag_palette.json",
                            f"category {cat_id!r}: alias {alias!r} of tag {primary!r} "
                            f"collides with a primary tag value"
                        ))

    return issues


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def check_all() -> list[Issue]:
    issues: list[Issue] = []
    issues.extend(check_tag_palette())
    issues.extend(check_tag_palette_extras())
    issues.extend(check_anima_spec())
    issues.extend(check_character_presets())
    issues.extend(check_i18n())
    issues.extend(check_cross_references())
    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Integrity check for anima-prompt-helper data files")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exit 1)",
    )
    args = parser.parse_args()

    issues = check_all()

    if not issues:
        print("OK: data files are consistent")
        sys.exit(0)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    for issue in warnings:
        print(f"WARN: {issue.file}: {issue.message}")
    for issue in errors:
        print(f"ERROR: {issue.file}: {issue.message}")

    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
