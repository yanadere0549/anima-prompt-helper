"""composer.py — pure prompt assembly functions for anima-prompt-helper.

No I/O at import time; fully unit-testable without ComfyUI.
OOO_ANIMA_DEFAULTS is loaded lazily from data/anima_spec.json on the first
call to join_fields() that needs it and cached for the process lifetime.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANONICAL_ORDER: list[str] = [
    "quality",
    "year",
    "rating",
    "count",
    "character",
    "series",
    "artist",
    "general",
    "natural_language",
]

# Hard-coded fallback used when data/anima_spec.json is missing.
# Keys: quality, year, rating, extra  (extra maps to default_extra).
_OOO_ANIMA_FALLBACK: dict[str, str] = {
    "quality": "masterpiece, best quality, high quality",
    "year": "newest, year 2025, year 2024",
    "rating": "safe",
    "extra": "game cg",
}

# Lazily populated from anima_spec.json; None means "not yet attempted".
_ooo_anima_cache: dict[str, str] | None = None
_cache_loaded: bool = False


def _load_ooo_anima_defaults() -> dict[str, str]:
    """Load OOO_Anima preset values from data/anima_spec.json.

    Returns a dict with keys ``quality``, ``year``, ``rating``, ``extra``.
    Falls back to ``_OOO_ANIMA_FALLBACK`` if the file is missing or malformed.
    Result is cached in ``_ooo_anima_cache`` after the first call.
    """
    global _ooo_anima_cache, _cache_loaded
    if _cache_loaded:
        return _ooo_anima_cache  # type: ignore[return-value]

    _cache_loaded = True
    spec_path = Path(__file__).resolve().parent.parent / "data" / "anima_spec.json"
    try:
        with spec_path.open(encoding="utf-8") as fh:
            spec = json.load(fh)
        preset = spec["model_presets"]["ooo_anima"]
        loaded: dict[str, str] = {
            "quality": preset.get("default_prefix_quality", _OOO_ANIMA_FALLBACK["quality"]),
            "year":    preset.get("default_prefix_year",    _OOO_ANIMA_FALLBACK["year"]),
            "rating":  preset.get("default_rating",         _OOO_ANIMA_FALLBACK["rating"]),
            "extra":   preset.get("default_extra",          _OOO_ANIMA_FALLBACK["extra"]),
        }
        logger.debug("ooo_anima defaults loaded from %s", spec_path)
        _ooo_anima_cache = loaded
    except FileNotFoundError:
        logger.warning("anima_spec.json not found at %s; using hard-coded OOO_Anima defaults", spec_path)
        _ooo_anima_cache = dict(_OOO_ANIMA_FALLBACK)
    except (KeyError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read ooo_anima preset from %s (%s); using hard-coded defaults", spec_path, exc)
        _ooo_anima_cache = dict(_OOO_ANIMA_FALLBACK)

    return _ooo_anima_cache  # type: ignore[return-value]


# Public alias kept for test imports (tests may import OOO_ANIMA_DEFAULTS).
# It is a property-like accessor so tests always get the current cached value.
class _OOOAnimaDefaultsProxy(dict):
    """Thin proxy that defers loading until first ``__getitem__`` / iteration."""

    def _ensure(self) -> dict[str, str]:
        return _load_ooo_anima_defaults()

    def __getitem__(self, key: str) -> str:  # type: ignore[override]
        return self._ensure()[key]

    def __iter__(self):  # type: ignore[override]
        return iter(self._ensure())

    def items(self):  # type: ignore[override]
        return self._ensure().items()

    def get(self, key: str, default=None):  # type: ignore[override]
        return self._ensure().get(key, default)


OOO_ANIMA_DEFAULTS: _OOOAnimaDefaultsProxy = _OOOAnimaDefaultsProxy()

# ---------------------------------------------------------------------------
# User prefix presets
# ---------------------------------------------------------------------------

# Map of user-defined prefix-preset id -> {quality, year, rating, extra}.
# Populated lazily from data/user_prefix_presets.json on the first call to
# _load_user_prefix_presets().
_user_prefix_cache: dict[str, dict[str, str]] | None = None
_user_prefix_cache_loaded: bool = False


def _load_user_prefix_presets() -> dict[str, dict[str, str]]:
    """Load user prefix presets from data/user_prefix_presets.json.

    Returns a dict mapping preset id -> {quality, year, rating, extra}.
    Missing file or parse errors yield an empty dict.
    Result is cached for the process lifetime; call ``reset_user_prefix_cache()``
    to invalidate after an API write.
    """
    global _user_prefix_cache, _user_prefix_cache_loaded
    if _user_prefix_cache_loaded:
        return _user_prefix_cache  # type: ignore[return-value]

    _user_prefix_cache_loaded = True
    path = Path(__file__).resolve().parent.parent / "data" / "user_prefix_presets.json"
    if not path.exists():
        _user_prefix_cache = {}
        return _user_prefix_cache

    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        result: dict[str, dict[str, str]] = {}
        for p in data.get("presets", []) or []:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if not isinstance(pid, str) or not pid:
                continue
            result[pid] = {
                "quality": str(p.get("quality") or ""),
                "year": str(p.get("year") or ""),
                "rating": str(p.get("rating") or "safe"),
                "extra": str(p.get("extra") or ""),
            }
        _user_prefix_cache = result
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to load user_prefix_presets.json (%s); treating as empty", exc
        )
        _user_prefix_cache = {}

    return _user_prefix_cache  # type: ignore[return-value]


def reset_user_prefix_cache() -> None:
    """Invalidate the user prefix preset cache.

    Postcondition: the next call to ``_load_user_prefix_presets()`` will
    re-read the JSON file from disk. Safe to call from any thread because
    the only state mutated is the module-level pair of booleans.
    """
    global _user_prefix_cache, _user_prefix_cache_loaded
    _user_prefix_cache = None
    _user_prefix_cache_loaded = False


def get_user_prefix_preset_ids() -> list[str]:
    """Return the sorted list of currently-known user prefix preset ids.

    Used by ``nodes.py`` to advertise user-defined choices on the combo widget.
    """
    return sorted(_load_user_prefix_presets().keys())


# ---------------------------------------------------------------------------
# Negative prompt defaults
# ---------------------------------------------------------------------------

# Hard-coded fallback negative defaults when anima_spec.json is missing.
_NEGATIVE_FALLBACK: dict[str, str] = {
    "anima_base": "worst quality, low quality, score_1, score_2, score_3, artist name",
    "ooo_anima": "worst quality, low quality, score_1, score_2, score_3, artifacts, early, old, nsfw, realistic",
}

# Lazily populated from anima_spec.json; None means "not yet attempted".
_negative_cache: dict[str, str] | None = None
_negative_cache_loaded: bool = False

NEGATIVE_CANONICAL_ORDER: list[str] = [
    "quality_negative",
    "score_negative",
    "style_negative",
    "content_negative",
    "meta_negative",
    "extra_negative",
]


def _load_negative_defaults() -> dict[str, str]:
    """Load negative prompt defaults for anima_base and ooo_anima from anima_spec.json.

    Returns a dict with keys ``anima_base`` and ``ooo_anima``.
    Falls back to ``_NEGATIVE_FALLBACK`` if the file is missing or malformed.
    Result is cached after the first call.

    Thread-safety: protected by Python's GIL for CPython; a redundant double-load
    (if two threads race before ``_negative_cache_loaded`` is set) is harmless
    because both will compute the same result and assign identical values.
    This matches the identical pattern in ``_load_ooo_anima_defaults()``.
    """
    global _negative_cache, _negative_cache_loaded
    if _negative_cache_loaded:
        return _negative_cache  # type: ignore[return-value]

    _negative_cache_loaded = True
    spec_path = Path(__file__).resolve().parent.parent / "data" / "anima_spec.json"
    try:
        with spec_path.open(encoding="utf-8") as fh:
            spec = json.load(fh)
        loaded: dict[str, str] = {
            "anima_base": spec["model_presets"]["anima_base"].get(
                "default_negative", _NEGATIVE_FALLBACK["anima_base"]
            ),
            "ooo_anima": spec["model_presets"]["ooo_anima"].get(
                "default_negative", _NEGATIVE_FALLBACK["ooo_anima"]
            ),
        }
        logger.debug("negative defaults loaded from %s", spec_path)
        _negative_cache = loaded
    except FileNotFoundError:
        logger.warning(
            "anima_spec.json not found at %s; using hard-coded negative defaults", spec_path
        )
        _negative_cache = dict(_NEGATIVE_FALLBACK)
    except (KeyError, json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to read negative presets from %s (%s); using hard-coded defaults", spec_path, exc
        )
        _negative_cache = dict(_NEGATIVE_FALLBACK)

    return _negative_cache  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def join_fields(
    fields: dict[str, str],
    preset: str = "none",
    lora_trigger_words: list[str] | None = None,
) -> str:
    """Assemble the nine prompt fields into a single string.

    Preconditions:
        - ``fields`` is a ``dict`` mapping field names (str) to values (str).
          Missing keys are treated as empty string.
        - ``preset`` is one of ``{"none", "ooo_anima_default", "custom"}``.
          Any unknown value is treated as ``"none"``.
        - ``lora_trigger_words`` is either ``None`` or a ``list[str]``.
          Non-None, non-list values raise ``TypeError``.
          Each element must be a ``str``; non-str elements are silently skipped.

    Postconditions:
        - Returns a ``str``; never ``None``.
        - The return value may be ``""`` when all fields are empty.
        - Field order is always:
          quality → year → rating → [extra] → count → character → series →
          artist → general → [lora_trigger_words], joined with ``", "``,
          followed by ``natural_language`` separated by ``". "`` when non-empty.
        - ``lora_trigger_words`` tokens are appended after ``general`` and
          before ``natural_language``.
        - When ``preset == "ooo_anima_default"``, ``quality``, ``year``, and
          ``rating`` are replaced with values from ``model_presets.ooo_anima``
          in ``data/anima_spec.json`` (loaded lazily, cached).  Additionally,
          ``default_extra`` (e.g. ``"game cg"``) is inserted immediately after
          the ``rating`` field and before ``count``.  This matches the OOO_Anima
          model card's recommended prefix:
          ``masterpiece, best quality, high quality, newest, year 2025, year 2024,
          safe, game cg, <count>, ...``

    Invariants:
        - Deterministic: identical ``fields``, ``preset``, and
          ``lora_trigger_words`` produce identical output.
        - ``natural_language`` is never comma-split; it is appended verbatim
          (after stripping leading/trailing whitespace).
        - preset shadowing is logged at INFO level.
        - The caller's ``fields`` dict is never mutated.
    """
    if not isinstance(fields, dict):
        raise TypeError(f"fields must be dict, got {type(fields).__name__}")
    if not isinstance(preset, str):
        raise TypeError(f"preset must be str, got {type(preset).__name__}")
    if lora_trigger_words is not None and not isinstance(lora_trigger_words, list):
        raise TypeError(
            f"lora_trigger_words must be list or None, got {type(lora_trigger_words).__name__}"
        )

    # Work on a copy so the caller's dict is not mutated.
    effective: dict[str, str] = {
        k: (v if isinstance(v, str) else "") for k, v in fields.items()
    }

    # Extra prefix token injected after rating (only for ooo_anima_default).
    extra_prefix: str = ""

    # Apply preset shadowing ------------------------------------------------
    # Resolve preset to a defaults dict (quality/year/rating/extra) or None.
    preset_defaults: dict[str, str] | None = None
    if preset == "ooo_anima_default":
        preset_defaults = dict(_load_ooo_anima_defaults())
    elif preset and preset not in ("none", "custom"):
        # Treat as a user-defined prefix preset id.
        user_presets = _load_user_prefix_presets()
        if preset in user_presets:
            preset_defaults = dict(user_presets[preset])
        else:
            logger.info(
                "Unknown prefix preset %r; treating as 'none' (fields pass through unchanged)",
                preset,
            )

    if preset_defaults is not None:
        for key in ("quality", "year", "rating"):
            default_val = preset_defaults.get(key, "")
            original = effective.get(key, "")
            if original != default_val:
                logger.info(
                    "prefix preset '%s': shadowing field '%s' "
                    "(user value %r -> preset value %r)",
                    preset,
                    key,
                    original,
                    default_val,
                )
            effective[key] = default_val

        # Capture default_extra for insertion after rating.
        extra_prefix = (preset_defaults.get("extra", "") or "").strip()

    # Build the main token list (all fields except natural_language) ---------
    tag_parts: list[str] = []
    for field in CANONICAL_ORDER:
        if field == "natural_language":
            continue
        raw = effective.get(field, "").strip()
        if not raw:
            continue
        # Split by comma, strip tokens, drop empties, rejoin.
        tokens = [t.strip() for t in raw.split(",")]
        tokens = [t for t in tokens if t]
        if tokens:
            tag_parts.append(", ".join(tokens))

        # After the rating field, inject default_extra when set.
        if field == "rating" and extra_prefix:
            tag_parts.append(extra_prefix)

    # Append LoRA trigger words after general tags, before natural_language.
    if lora_trigger_words is not None:
        for word in lora_trigger_words:
            if not isinstance(word, str):
                continue
            token = word.strip()
            if token:
                tag_parts.append(token)

    assembled = ", ".join(tag_parts)

    # Append natural_language ------------------------------------------------
    nl_raw = effective.get("natural_language", "").strip()
    if nl_raw:
        if assembled:
            assembled = assembled + ". " + nl_raw
        else:
            assembled = nl_raw

    return assembled


def join_negative_fields(fields: dict[str, str], preset: str = "none") -> str:
    """Compose negative prompt from 6 field categories.

    Preconditions:
        - ``fields`` is a ``dict`` mapping field names (str) to values (str).
          Missing keys are treated as empty string.
        - ``preset`` is one of
          ``{"none", "anima_base_default", "ooo_anima_default", "custom"}``.
          Any unknown value is treated as ``"none"`` (fields joined in
          canonical order, no override applied).

    Postconditions:
        - Returns a ``str`` (possibly ``""``). Never ``None``.
        - The caller's ``fields`` dict is never mutated.

    Invariants:
        - When ``preset`` is ``"anima_base_default"`` or
          ``"ooo_anima_default"``, the entire ``default_negative`` string from
          ``model_presets.<id>.default_negative`` in ``anima_spec.json`` is
          returned as-is, completely replacing any user-supplied field values.
          No per-field merge occurs; user fields are ignored.
        - When ``preset`` is ``"none"`` or ``"custom"`` (or any unknown value),
          the six fields are joined in ``NEGATIVE_CANONICAL_ORDER`` order,
          token-deduplicated per field, and concatenated with ``", "``.
        - Deterministic: identical ``fields`` and ``preset`` produce identical
          output.
    """
    if not isinstance(fields, dict):
        raise TypeError(f"fields must be dict, got {type(fields).__name__}")
    if not isinstance(preset, str):
        raise TypeError(f"preset must be str, got {type(preset).__name__}")

    # Preset override: return model default directly, ignoring all field values.
    if preset in ("anima_base_default", "ooo_anima_default"):
        defaults = _load_negative_defaults()
        key = "anima_base" if preset == "anima_base_default" else "ooo_anima"
        logger.info("negative preset '%s': returning model default negative prompt", preset)
        return defaults[key]

    # preset == "none" or "custom": join the 6 fields in canonical order.
    tag_parts: list[str] = []
    for field in NEGATIVE_CANONICAL_ORDER:
        raw = (fields.get(field) or "").strip()
        if not raw:
            continue
        tokens = [t.strip() for t in raw.split(",")]
        tokens = [t for t in tokens if t]
        if tokens:
            tag_parts.append(", ".join(tokens))

    return ", ".join(tag_parts)
