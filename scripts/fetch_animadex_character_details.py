#!/usr/bin/env python3
"""fetch_animadex_character_details.py - build animadex_character_presets.json.

Fetches character detail data from animadex.net and produces a preset file
compatible with the existing ``data/character_presets.json`` schema, extended
with a ``prompt_example`` field.

=== API Investigation Results (2026-05-28) ===

Working endpoint:
    GET https://animadex.net/api/characters/search?gender=1girl&sort=score&page=N
    - Returns 36 characters per page, ordered by score (popularity proxy).
    - HTTP 200 with a browser User-Agent; HTTP 403 without one.

Non-working endpoints:
    GET https://animadex.net/api/characters/<slug>  → HTTP 404 (no detail endpoint)

Fields available per character in the search API response:
    slug          (str)   danbooru-style slug, e.g. "hatsune_miku"
    name          (str)   display name, e.g. "Hatsune Miku"
    copyright     (str)   series slug, e.g. "vocaloid"
    copyright_name (str)  series display name, e.g. "Vocaloid"
    trigger       (str)   "char name, series name" - prompt insert form
    tags          (list)  essential appearance tags from danbooru, e.g.
                          ["1girl", "aqua eyes", "twintails", "long hair", ...]
    count         (int)   total danbooru post count (proxy for model recognition)
    rating        (dict)  {"up": N, "down": N} - animadex user rating
    fav_count     (int)   animadex favourites
    loras         (list)  linked CivitAI LoRA entries (often empty)
    has_image     (bool)  whether animadex has a generated preview
    is_hidden     (bool)  whether hidden from public listing
    url           (str)   danbooru search URL
    thumb_url/img_url (str) CDN URLs for preview images

Fields NOT available (synthesised or omitted):
    associated_artists  → not in API; always set to [] (empty)
    prompt_example      → synthesised: character_tag + essential_tags (space-joined,
                          excluding "1girl") + series_tag
    tier                → derived from post count:
                          >=50000 → 5, >=10000 → 4, >=3000 → 3, >=500 → 2, else 1

=== Contract ===

Preconditions:
    - Internet access to animadex.net (raises SystemExit(1) on repeated failure)
    - Python 3.8+, stdlib only

Postconditions:
    - data/animadex_character_presets.json written with count == len(presets)
    - Every preset has: id, label, character, series, essential_general_tags,
      recommended_artists, prompt_example, notes, tier, source
    - id starts with "animadex_" prefix to avoid collision with character_presets.json

Invariants:
    - character tags use insert form: spaces (not underscores), parens escaped as \\( \\)
    - essential_general_tags excludes "1girl" (redundant in prompt context)
    - No duplicate slugs in output

Usage:
    python scripts/fetch_animadex_character_details.py [--top 300] [--sleep 0.4]
                                                       [--max-retries 3]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OUT_PATH = _ROOT / "data" / "animadex_character_presets.json"

_API = (
    "https://animadex.net/api/characters/search"
    "?gender=1girl&sort=score&page={page}"
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_REFERER = "https://animadex.net/?mode=characters&gender=1girl"

# Tags that carry no useful prompt signal; stripped from essential_general_tags.
_NOISE_TAGS = frozenset({"1girl", "1boy", "2girls", "male focus", "female focus"})


def _format_for_insert(tag: str) -> str:
    """Convert a raw tag to prompt-insert form.

    Precondition:  tag is a non-empty string.
    Postcondition: underscores replaced by spaces; ( and ) backslash-escaped.

    "artoria pendragon (fate)" -> "artoria pendragon \\(fate\\)"
    """
    return tag.replace("_", " ").replace("(", r"\(").replace(")", r"\)")


def _count_to_tier(count: int) -> int:
    """Map post count to a 1–5 tier.

    Postcondition: returns int in [1, 5].
    """
    if count >= 50_000:
        return 5
    if count >= 10_000:
        return 4
    if count >= 3_000:
        return 3
    if count >= 500:
        return 2
    return 1


def _make_id(slug: str) -> str:
    """Return preset id with animadex_ prefix.

    "hatsune_miku" -> "animadex_hatsune_miku"
    """
    return f"animadex_{slug}"


def _make_label(name: str, copyright_name: str) -> str:
    """Return human-readable label.

    "Hatsune Miku", "Vocaloid" -> "Hatsune Miku (Vocaloid)"
    """
    if copyright_name:
        return f"{name} ({copyright_name})"
    return name


def _extract_character_tag(trigger: str) -> str:
    """Extract character tag from trigger string.

    "hatsune miku, vocaloid" -> "hatsune miku"
    """
    return trigger.split(",")[0].strip()


def _extract_series_tag(trigger: str, copyright: str) -> str:
    """Extract series tag: second token of trigger, fallback to copyright slug.

    Precondition: trigger is non-empty string.
    """
    parts = trigger.split(",")
    if len(parts) >= 2:
        series = parts[1].strip()
        if series:
            return _format_for_insert(series)
    return _format_for_insert(copyright)


def _make_essential_tags(raw_tags: list[str]) -> list[str]:
    """Convert raw API tags to insert-form essential_general_tags.

    Filters noise tags (1girl etc.) and de-duplicates while preserving order.
    Postcondition: result contains no duplicates and no noise tags.
    """
    seen: set[str] = set()
    out: list[str] = []
    for t in raw_tags:
        if not t:
            continue
        insert = _format_for_insert(t.lower())
        if insert in _NOISE_TAGS or insert in seen:
            continue
        seen.add(insert)
        out.append(insert)
    return out


def _make_prompt_example(
    character: str,
    series: str,
    essential_tags: list[str],
) -> str:
    """Synthesise a prompt example from character, series, and essential tags.

    Format: "<character>, <tag1>, <tag2>, ..., <series>"
    Postcondition: non-empty string.
    """
    parts = [character] + essential_tags
    if series and series not in parts:
        parts.append(series)
    return ", ".join(parts)


def _fetch_page(page: int, retries: int, sleep_on_retry: float = 1.0) -> dict:
    """Fetch one page of the character search API.

    Precondition:  page >= 1, retries >= 1
    Postcondition: returns parsed JSON dict
    Raises:        last exception after all retries exhausted
    """
    url = _API.format(page=page)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Referer": _REFERER},
    )
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                wait = attempt * sleep_on_retry
                print(
                    f"  retry {attempt}/{retries - 1} page {page} "
                    f"after {wait:.1f}s ({exc})",
                    file=sys.stderr,
                )
                time.sleep(wait)
    raise last_exc


def _build_preset(ch: dict) -> dict:
    """Convert a raw API character dict to a preset dict.

    Precondition:  ch has at least 'slug', 'name', 'trigger' keys.
    Postcondition: returned dict has all required preset fields.
    """
    trigger = ch.get("trigger", "") or ch.get("name", "")
    character = _extract_character_tag(trigger)
    character_insert = _format_for_insert(character)

    copyright_slug = ch.get("copyright", "")
    copyright_name = ch.get("copyright_name", "")
    series = _extract_series_tag(trigger, copyright_slug)

    raw_tags: list[str] = ch.get("tags") or []
    essential_tags = _make_essential_tags(raw_tags)
    prompt_example = _make_prompt_example(character_insert, series, essential_tags)

    return {
        "id": _make_id(ch["slug"]),
        "label": _make_label(ch.get("name", character), copyright_name),
        "character": character_insert,
        "series": series,
        "essential_general_tags": essential_tags,
        "recommended_artists": [],  # not available from animadex character API
        "prompt_example": prompt_example,
        "notes": (
            f"Sourced from animadex.net character detail page. "
            f"Post count: {ch.get('count', 0):,}. "
            f"essential_general_tags from danbooru tag co-occurrence data."
        ),
        "tier": _count_to_tier(ch.get("count", 0)),
        "source": "animadex",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--top",
        type=int,
        default=300,
        help="number of top characters to collect (default: 300)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.4,
        help="seconds to sleep between page requests (default: 0.4)",
    )
    ap.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="max retries per page request (default: 3)",
    )
    args = ap.parse_args()

    assert args.top >= 1, f"--top must be >= 1, got {args.top}"
    assert args.sleep >= 0, f"--sleep must be >= 0, got {args.sleep}"
    assert args.max_retries >= 1, f"--max-retries must be >= 1, got {args.max_retries}"

    presets: list[dict] = []
    seen_slugs: set[str] = set()
    page = 1
    total_pages: int | None = None

    print(
        f"Fetching top {args.top} characters from animadex.net "
        f"(sleep={args.sleep}s, max-retries={args.max_retries})..."
    )

    while len(presets) < args.top:
        try:
            data = _fetch_page(page, retries=args.max_retries)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: failed to fetch page {page}: {exc}", file=sys.stderr)
            return 1

        if total_pages is None:
            total_pages = data.get("pages", page)

        results: list[dict] = data.get("results", [])
        if not results:
            print(f"No more results at page {page}. Stopping.")
            break

        for ch in results:
            if len(presets) >= args.top:
                break
            slug = ch.get("slug", "")
            if not slug or slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            preset = _build_preset(ch)
            presets.append(preset)

        print(
            f"page {page}/{total_pages or '?'}: "
            f"collected {len(presets)}/{args.top}"
        )

        if len(presets) >= args.top:
            break
        if total_pages is not None and page >= total_pages:
            print("Reached last API page.")
            break

        page += 1
        time.sleep(args.sleep)

    payload = {
        "version": "1.0",
        "source": "https://animadex.net (character search API, sort=score)",
        "generated": _dt.date.today().isoformat(),
        "count": len(presets),
        "presets": presets,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(presets)} presets to {_OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
