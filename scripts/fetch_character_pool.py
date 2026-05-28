#!/usr/bin/env python3
"""fetch_character_pool.py - build the built-in high-count 1girl character pool.

Pulls the character ranking from animadex.net
(``/api/characters/search?gender=1girl&sort=score``) and keeps every character
whose post ``count`` is at least ``--min-count``.  The animadex ranking is used
for *ordering and selection* only - each kept character tag is formatted from
the ``trigger`` field so the pool contains prompt-ready insert tokens.

Unlike the artist pool, the characters API does not expose a 0..1 quality
``score``.  Post ``count`` (total Danbooru posts) is used as the proxy: higher
count indicates a well-represented character the Anima model is more likely to
recognise.

Tag derivation:
    character tag = first token of ``trigger`` before the first comma
    insert tag    = character tag with ``(`` ``)`` backslash-escaped
                    (``_`` → space conversion is not needed; trigger is
                    already space-separated)

    Example: trigger ``"artoria pendragon (fate), fate (series)"``
             → insert tag ``"artoria pendragon \\(fate\\)"``

Output: ``data/character_pool_default.json``
    {
      "version": 1,
      "source": "https://animadex.net/?mode=characters&gender=1girl (sort=score)",
      "gender_filter": "1girl",
      "min_score": 0.5,
      "generated": "YYYY-MM-DD",
      "count": <int>,
      "tags": ["hatsune miku", "marin kitagawa", ...]   # insert form, count desc
    }

The ``min_score`` key in the output is kept for schema compatibility with the
artist pool; it stores the ``--min-score`` argument value even though the
actual filter is applied via post count (``--min-count``).

The site rejects requests without a browser User-Agent (HTTP 403), so one is
sent explicitly. This is a maintenance/build script, not imported at runtime.

Usage:
    python scripts/fetch_character_pool.py [--min-count 500] [--min-score 0.5]
                                           [--max-pages 0] [--sleep 0.3]
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
_OUT_PATH = _ROOT / "data" / "character_pool_default.json"

_API = (
    "https://animadex.net/api/characters/search"
    "?gender=1girl&sort=score&page={page}"
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_REFERER = "https://animadex.net/?mode=characters&gender=1girl"


def _format_for_insert(tag: str) -> str:
    """Mirror formatArtistTagForInsert for character tags.

    Escapes parentheses so the tag is safe for prompt insertion.
    Underscores are converted to spaces (trigger field already uses
    spaces, but this handles any edge cases in the data).

    ``"artoria pendragon (fate)"`` -> ``"artoria pendragon \\(fate\\)"``.
    """
    return tag.replace("_", " ").replace("(", r"\(").replace(")", r"\)")


def _extract_char_tag(trigger: str) -> str:
    """Return the character name part from a trigger string.

    Trigger format: ``"char name, series name"`` or just ``"char name"``.
    """
    return trigger.split(",")[0].strip()


def _fetch_page(page: int, timeout: float = 30.0, retries: int = 3) -> dict:
    req = urllib.request.Request(
        _API.format(page=page),
        headers={"User-Agent": _UA, "Referer": _REFERER},
    )
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                wait = attempt * 1.0
                print(
                    f"  retry {attempt}/{retries - 1} for page {page} "
                    f"after {wait}s ({exc})",
                    file=sys.stderr,
                )
                time.sleep(wait)
    raise last_exc


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--min-count",
        type=int,
        default=500,
        help="keep characters with post count >= this (default 500)",
    )
    ap.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help=(
            "stored in output JSON for schema compatibility; "
            "does not affect filtering (default 0.5)"
        ),
    )
    ap.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="stop after N pages (0 = until count drops below --min-count)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.3,
        help="seconds to sleep between page requests (default 0.3)",
    )
    args = ap.parse_args()

    tags: list[str] = []
    seen: set[str] = set()
    skipped_count = 0
    page = 1
    while True:
        try:
            data = _fetch_page(page)
        except Exception as exc:  # noqa: BLE001 - maintenance script
            print(f"ERROR fetching page {page}: {exc}", file=sys.stderr)
            return 1

        results = data.get("results", [])
        if not results:
            break

        stop = False
        for ch in results:
            count = ch.get("count", 0)
            if count < args.min_count:
                stop = True
                break

            trigger = ch.get("trigger", "")
            if not trigger:
                continue

            char_tag = _extract_char_tag(trigger)
            if not char_tag:
                continue

            insert = _format_for_insert(char_tag)
            key = insert.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(insert)

        total_pages = data.get("pages", page)
        print(
            f"page {page}/{total_pages}: kept so far={len(tags)} "
            f"(below-cutoff skipped={skipped_count})"
        )

        if stop:
            break
        page += 1
        if args.max_pages and page > args.max_pages:
            break
        time.sleep(args.sleep)

    payload = {
        "version": 1,
        "source": (
            "https://animadex.net/?mode=characters&gender=1girl (sort=score)"
        ),
        "gender_filter": "1girl",
        "min_score": args.min_score,
        "generated": _dt.date.today().isoformat(),
        "count": len(tags),
        "tags": tags,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {len(tags)} character tags "
        f"(count >= {args.min_count}) to {_OUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
