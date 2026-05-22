"""validators.py — stateless validation rule functions for anima-prompt-helper.

Each public function is pure (no I/O during invocation) and returns a list of
``ValidationIssue`` dataclass instances.

Underscore-exemption regexes are loaded once from ``data/anima_spec.json`` at
module import time; the hardcoded fallback list is used when the file is absent.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """Represents a single validation finding on a prompt field.

    Attributes:
        field:    One of the nine canonical field names (or "assembled").
        tag:      The specific token that triggered the rule.
        rule:     Rule identifier string (e.g. ``"UPPERCASE_TAG"``).
        severity: One of ``"error"``, ``"warning"``, ``"info"``.
        message:  Human-readable description of the issue.
    """

    field: str
    tag: str
    rule: str
    severity: str
    message: str


# ---------------------------------------------------------------------------
# Load underscore exemption patterns
# ---------------------------------------------------------------------------

_FALLBACK_EXEMPT_PATTERNS: list[str] = [r"^score_\d+$", r"^score_\d+_up$"]

_SPEC_PATH = Path(__file__).parent.parent / "data" / "anima_spec.json"


def _load_exempt_patterns() -> list[re.Pattern[str]]:
    """Load underscore-exempt regex patterns from anima_spec.json.

    Returns compiled patterns; falls back to hardcoded list on any error.
    """
    patterns_raw: list[str] = _FALLBACK_EXEMPT_PATTERNS
    if _SPEC_PATH.exists():
        try:
            with _SPEC_PATH.open(encoding="utf-8") as fh:
                spec = json.load(fh)
            raw = (
                spec.get("validation_rules", {})
                .get("underscore_forbidden_except", [])
            )
            if isinstance(raw, list) and raw:
                patterns_raw = raw
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load anima_spec.json for exempt patterns: %s", exc)
    return [re.compile(p) for p in patterns_raw]


_EXEMPT_PATTERNS: list[re.Pattern[str]] = _load_exempt_patterns()

# Regex for weighted-tag syntax: (tag:weight)
_WEIGHT_RE: re.Pattern[str] = re.compile(r"^\((.+):(\d+(?:\.\d+)?)\)$")

# Fields that skip certain checks per spec
_NO_UNDERSCORE_CHECK: frozenset[str] = frozenset({"natural_language"})
_NO_LOWERCASE_CHECK: frozenset[str] = frozenset({"character", "series", "natural_language"})

# ---------------------------------------------------------------------------
# Individual rule functions
# ---------------------------------------------------------------------------


def check_lowercase(fields: dict[str, str]) -> list[ValidationIssue]:
    """Rule UPPERCASE_TAG: warn when a token contains uppercase letters.

    Preconditions:
        - ``fields`` is a dict mapping field names to string values.
    Postconditions:
        - Returns a (possibly empty) list of ``ValidationIssue`` with
          severity ``"warning"`` and rule ``"UPPERCASE_TAG"``.
    Invariants:
        - Fields in ``_NO_LOWERCASE_CHECK`` are skipped.
        - ``natural_language`` is always skipped.
    """
    issues: list[ValidationIssue] = []
    for field, value in fields.items():
        if field in _NO_LOWERCASE_CHECK:
            continue
        for token in _iter_tokens(value):
            bare = _strip_weight(token)
            if bare != bare.lower():
                issues.append(
                    ValidationIssue(
                        field=field,
                        tag=token,
                        rule="UPPERCASE_TAG",
                        severity="warning",
                        message=f"Tag '{token}' contains uppercase letters; use lowercase",
                    )
                )
    return issues


def check_underscore(fields: dict[str, str]) -> list[ValidationIssue]:
    """Rule UNDERSCORE_TAG: warn when a token contains ``_`` and is not exempt.

    Preconditions:
        - ``fields`` is a dict mapping field names to string values.
    Postconditions:
        - Returns a (possibly empty) list of ``ValidationIssue`` with
          severity ``"warning"`` and rule ``"UNDERSCORE_TAG"``.
    Invariants:
        - Tokens matching any pattern in ``_EXEMPT_PATTERNS`` are skipped.
        - Fields in ``_NO_UNDERSCORE_CHECK`` are skipped.
    """
    issues: list[ValidationIssue] = []
    for field, value in fields.items():
        if field in _NO_UNDERSCORE_CHECK:
            continue
        for token in _iter_tokens(value):
            bare = _strip_weight(token)
            if "_" not in bare:
                continue
            if _is_exempt(token):
                continue
            issues.append(
                ValidationIssue(
                    field=field,
                    tag=token,
                    rule="UNDERSCORE_TAG",
                    severity="warning",
                    message=(
                        f"Tag '{token}' contains underscore; "
                        f"use '{bare.replace('_', ' ')}' instead (exception: score_N)"
                    ),
                )
            )
    return issues


def check_artist_at(fields: dict[str, str]) -> list[ValidationIssue]:
    """Rule ARTIST_MISSING_AT: error when an artist token lacks ``@`` prefix.

    Preconditions:
        - ``fields`` is a dict mapping field names to string values.
    Postconditions:
        - Returns a (possibly empty) list of ``ValidationIssue`` with
          severity ``"error"`` and rule ``"ARTIST_MISSING_AT"``.
    Invariants:
        - Only the ``"artist"`` field is checked.
        - Empty tokens are ignored.
    """
    issues: list[ValidationIssue] = []
    artist_value = fields.get("artist", "")
    for token in _iter_tokens(artist_value):
        if not token.startswith("@"):
            issues.append(
                ValidationIssue(
                    field="artist",
                    tag=token,
                    rule="ARTIST_MISSING_AT",
                    severity="error",
                    message=f"Artist tag '{token}' must start with '@'",
                )
            )
    return issues


def check_rating(fields: dict[str, str]) -> list[ValidationIssue]:
    """Rule INVALID_RATING: error when the rating value is not in the allowed set.

    Preconditions:
        - ``fields`` is a dict mapping field names to string values.
    Postconditions:
        - Returns a (possibly empty) list of ``ValidationIssue`` with
          severity ``"error"`` and rule ``"INVALID_RATING"``.
    Invariants:
        - Only the ``"rating"`` key is checked.
        - Absent ``"rating"`` key is treated as empty string and reported.
    """
    allowed = {"safe", "sensitive", "nsfw", "explicit"}
    issues: list[ValidationIssue] = []
    rating = fields.get("rating", "").strip()
    if rating not in allowed:
        issues.append(
            ValidationIssue(
                field="rating",
                tag=rating,
                rule="INVALID_RATING",
                severity="error",
                message=f"Rating '{rating}' is not in {sorted(allowed)}",
            )
        )
    return issues


def check_empty(assembled: str) -> list[ValidationIssue]:
    """Rule EMPTY_PROMPT: info when the assembled prompt is empty.

    Preconditions:
        - ``assembled`` is a str.
    Postconditions:
        - Returns a list with at most one ``ValidationIssue`` of severity
          ``"info"`` and rule ``"EMPTY_PROMPT"``.
    """
    if not assembled.strip():
        return [
            ValidationIssue(
                field="assembled",
                tag="",
                rule="EMPTY_PROMPT",
                severity="info",
                message="Assembled prompt is empty",
            )
        ]
    return []


def check_long(assembled: str) -> list[ValidationIssue]:
    """Rule LONG_PROMPT: warning when the assembled prompt exceeds 3000 chars.

    Preconditions:
        - ``assembled`` is a str.
    Postconditions:
        - Returns a list with at most one ``ValidationIssue`` of severity
          ``"warning"`` and rule ``"LONG_PROMPT"``.
    """
    if len(assembled) > 3000:
        return [
            ValidationIssue(
                field="assembled",
                tag="",
                rule="LONG_PROMPT",
                severity="warning",
                message=f"Assembled prompt is {len(assembled)} chars (> 3000)",
            )
        ]
    return []


def check_duplicate(fields: dict[str, str]) -> list[ValidationIssue]:
    """Rule DUPLICATE_TAG: warning when the same normalized tag appears in 2+ fields.

    Normalization: lowercase, collapse whitespace, strip.

    Preconditions:
        - ``fields`` is a dict mapping field names to string values.
    Postconditions:
        - Returns a (possibly empty) list of ``ValidationIssue`` with
          severity ``"warning"`` and rule ``"DUPLICATE_TAG"``.
    Invariants:
        - Each (normalized_tag, field) pair is reported at most once.
        - ``natural_language`` tokens are not split; the entire value is treated
          as a single token for dedup purposes (consistent with join_fields).
    """
    # Map normalized token -> list of (field, original_token)
    seen: dict[str, list[tuple[str, str]]] = {}

    for field, value in fields.items():
        if field == "natural_language":
            tokens = [value.strip()] if value.strip() else []
        else:
            tokens = list(_iter_tokens(value))
        for token in tokens:
            normalized = _normalize(token)
            if not normalized:
                continue
            seen.setdefault(normalized, []).append((field, token))

    issues: list[ValidationIssue] = []
    for normalized, occurrences in seen.items():
        # Deduplicate by field name first
        unique_fields = list(dict.fromkeys(f for f, _ in occurrences))
        if len(unique_fields) < 2:
            continue
        # Report once per extra field beyond the first
        first_field = unique_fields[0]
        first_token = next(t for f, t in occurrences if f == first_field)
        for extra_field in unique_fields[1:]:
            extra_token = next(t for f, t in occurrences if f == extra_field)
            issues.append(
                ValidationIssue(
                    field=extra_field,
                    tag=extra_token,
                    rule="DUPLICATE_TAG",
                    severity="warning",
                    message=(
                        f"Tag '{extra_token}' (normalized: '{normalized}') "
                        f"appears in both '{first_field}' and '{extra_field}'"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Composite validator
# ---------------------------------------------------------------------------


def validate_fields(
    fields: dict[str, str],
) -> tuple[list[ValidationIssue], int]:
    """Run all validation rules and return issues with the assembled length.

    Preconditions:
        - ``fields`` is a dict mapping field name strings to string values.
          Missing/null values are treated as ``""``.
    Postconditions:
        - Returns ``(issues, assembled_length)`` where ``issues`` is a list
          of ``ValidationIssue`` and ``assembled_length >= 0``.
    Invariants:
        - Deterministic for identical input.
        - No side effects.
    """
    # Import here to avoid circular dependency at module level.
    from .composer import join_fields

    # Normalize all values to str.
    clean: dict[str, str] = {
        k: (v if isinstance(v, str) else "") for k, v in fields.items()
    }

    assembled = join_fields(clean)
    assembled_length = len(assembled)

    issues: list[ValidationIssue] = []
    issues.extend(check_lowercase(clean))
    issues.extend(check_underscore(clean))
    issues.extend(check_artist_at(clean))
    issues.extend(check_rating(clean))
    issues.extend(check_empty(assembled))
    issues.extend(check_long(assembled))
    issues.extend(check_duplicate(clean))

    return issues, assembled_length


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_weight(token: str) -> str:
    """If token is in ``(tag:weight)`` syntax, return the bare tag; otherwise return token unchanged.

    Preconditions:
        - ``token`` is a str.
    Postconditions:
        - Returns the inner tag string if token matches ``(tag:N.N)`` format.
        - Returns the original token unchanged for all other inputs.

    Examples::

        _strip_weight("(blonde hair:1.2)") == "blonde hair"
        _strip_weight("blue eyes")          == "blue eyes"
    """
    m = _WEIGHT_RE.match(token)
    if m:
        return m.group(1).strip()
    return token


def _iter_tokens(value: str) -> list[str]:
    """Split a comma-separated field value into non-empty stripped tokens."""
    return [t.strip() for t in value.split(",") if t.strip()]


def _normalize(token: str) -> str:
    """Normalize a token for duplicate detection."""
    return " ".join(token.lower().split())


def _is_exempt(token: str) -> bool:
    """Return True if the token fully matches any underscore-exemption pattern.

    Uses ``fullmatch`` (not ``search``) so that a pattern like ``score_\\d+``
    from the spec file does not accidentally exempt tokens such as
    ``bad_score_7_tag`` where the pattern appears as a substring.
    """
    return any(p.fullmatch(token) for p in _EXEMPT_PATTERNS)
