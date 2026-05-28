"""character_pool.py — pure helpers for the Anima character randomizer.

Provides pool parsing, seeded (reproducible) selection, lazy loading of the
built-in default pool (``data/character_pool_default.json``), and lookup
against ``data/animadex_character_presets.json`` for character→meta
(series / essential general tags / prompt_example) aggregation. No I/O at
import time, so the logic is fully unit-testable without ComfyUI.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path

logger = logging.getLogger(__name__)

# data/character_pool_default.json — two levels up from python/
_DEFAULT_POOL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "character_pool_default.json"
)

# data/animadex_character_presets.json — supplies series / essential general
# tags / prompt_example metadata for each known character.
_ANIMADEX_PRESETS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "animadex_character_presets.json"
)

# Lazily populated; ``_default_pool_loaded`` guards a single load attempt.
_default_pool_cache: list[str] | None = None
_default_pool_loaded: bool = False

# Lazily populated character→preset map keyed by lower-cased character name.
_animadex_presets_cache: dict[str, dict] | None = None
_animadex_presets_loaded: bool = False


def parse_pool(raw: str) -> list[str]:
    """Split a comma/newline-separated pool string into trimmed unique tags.

    Preconditions:
        - ``raw`` is a str (any other type yields ``[]``).
    Postconditions:
        - Returns tags in first-seen order with case-insensitive de-duplication.
        - Empty / whitespace-only entries are dropped.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for chunk in raw.replace("\n", ",").split(","):
        tag = chunk.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def load_default_pool() -> list[str]:
    """Return the built-in character pool, cached for the process.

    Postconditions:
        - Returns a list of character tags.
        - Returns ``[]`` (never raises) if the data file is missing or malformed.
    """
    global _default_pool_cache, _default_pool_loaded
    if _default_pool_loaded:
        return _default_pool_cache or []

    _default_pool_loaded = True
    try:
        data = json.loads(_DEFAULT_POOL_PATH.read_text(encoding="utf-8"))
        tags = data.get("tags", []) if isinstance(data, dict) else []
        _default_pool_cache = [
            t.strip() for t in tags if isinstance(t, str) and t.strip()
        ]
        logger.debug(
            "character default pool loaded: %d tags from %s",
            len(_default_pool_cache),
            _DEFAULT_POOL_PATH,
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning(
            "character_pool_default.json unavailable (%s); default pool empty", exc
        )
        _default_pool_cache = []
    return _default_pool_cache


def pick_tags(pool: list[str], count: int, seed: int) -> list[str]:
    """Deterministically pick up to ``count`` distinct tags from ``pool``.

    Preconditions:
        - ``pool`` is a list of strings.
        - ``count`` and ``seed`` are ints.
    Postconditions:
        - ``count <= 0`` or empty pool -> ``[]``.
        - Returns ``min(count, len(pool))`` distinct tags (no repeats).
        - Selection and order are fully determined by ``seed`` (reproducible:
          the same seed + pool always yields the same result).
    """
    if not pool or count <= 0:
        return []
    n = min(count, len(pool))
    rng = random.Random(seed)
    return rng.sample(pool, n)


def join_tags(tags: list[str], delimiter: str = ", ") -> str:
    """Join ``tags`` with ``delimiter`` (default ``", "``)."""
    return delimiter.join(tags)


def load_animadex_presets() -> dict[str, dict]:
    """Return character→preset map loaded from ``animadex_character_presets.json``.

    Postconditions:
        - Returns a dict keyed by ``character.strip().lower()`` whose values are
          the raw preset dicts (with ``series``, ``essential_general_tags``,
          ``prompt_example``…). Cached for the process.
        - Returns ``{}`` (never raises) if the data file is missing or malformed.
    """
    global _animadex_presets_cache, _animadex_presets_loaded
    if _animadex_presets_loaded:
        return _animadex_presets_cache or {}

    _animadex_presets_loaded = True
    try:
        data = json.loads(_ANIMADEX_PRESETS_PATH.read_text(encoding="utf-8"))
        presets = data.get("presets", []) if isinstance(data, dict) else []
        out: dict[str, dict] = {}
        for preset in presets:
            if not isinstance(preset, dict):
                continue
            char = preset.get("character")
            if isinstance(char, str) and char.strip():
                out[char.strip().lower()] = preset
        _animadex_presets_cache = out
        logger.debug(
            "animadex character presets loaded: %d entries from %s",
            len(out),
            _ANIMADEX_PRESETS_PATH,
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning(
            "animadex_character_presets.json unavailable (%s); meta lookup empty",
            exc,
        )
        _animadex_presets_cache = {}
    return _animadex_presets_cache


def aggregate_meta(picks: list[str]) -> tuple[str, str, str]:
    """Aggregate series / general / prompt_example for picked character tags.

    Mirrors the panel's "メタ情報も挿入" behavior so that the headless / API
    path and the GUI path agree on what each random pick yields.

    Preconditions:
        - ``picks`` is an iterable of strings (non-strings silently skipped).
    Postconditions:
        - Returns ``(series, general, prompt_example)``:
            - ``series``: comma-joined unique series names of matched presets
              (case-insensitive de-duplication, first-seen order).
            - ``general``: comma-joined unique essential_general_tags from all
              matched presets (same de-dup rules).
            - ``prompt_example``: newline-joined ``prompt_example`` strings of
              matched presets (in pick order; not de-duplicated).
        - Characters with no matching preset are skipped silently.
        - Returns ``("", "", "")`` when ``picks`` is empty or no presets match.
    """
    if not picks:
        return ("", "", "")
    presets = load_animadex_presets()
    if not presets:
        return ("", "", "")

    series: list[str] = []
    series_seen: set[str] = set()
    general: list[str] = []
    general_seen: set[str] = set()
    prompt_examples: list[str] = []

    for tag in picks:
        if not isinstance(tag, str):
            continue
        key = tag.strip().lower()
        if not key:
            continue
        preset = presets.get(key)
        if not preset:
            continue

        s = preset.get("series")
        if isinstance(s, str) and s.strip():
            s_key = s.strip().lower()
            if s_key not in series_seen:
                series_seen.add(s_key)
                series.append(s.strip())

        gtags = preset.get("essential_general_tags")
        if isinstance(gtags, list):
            for g in gtags:
                if isinstance(g, str) and g.strip():
                    g_key = g.strip().lower()
                    if g_key not in general_seen:
                        general_seen.add(g_key)
                        general.append(g.strip())

        pe = preset.get("prompt_example")
        if isinstance(pe, str) and pe.strip():
            prompt_examples.append(pe.strip())

    return (", ".join(series), ", ".join(general), "\n".join(prompt_examples))
