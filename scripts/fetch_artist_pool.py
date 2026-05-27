#!/usr/bin/env python3
"""fetch_artist_pool.py — build the built-in high-score artist pool.

Pulls the artist ranking from animadex.net (``/api/artists/search?sort=score``)
and keeps every artist whose quality ``score`` (0..1) is at least ``--min-score``.
The animadex ranking is only used for *ordering and selection* — each kept
artist is mapped back to the canonical Anima tag from
``data/anima/search.json`` (the model's authoritative artist list) so the pool
never contains a token the Anima model does not recognise.

Mapping rule (verified against the live data, 0 disagreements):
    animadex ``slug`` with parentheses stripped  ==  local ``slug``
    insert tag = formatArtistTagForInsert(local ``tag``)
               = local tag with ``_`` -> space and ``(`` ``)`` backslash-escaped
which is identical to ``"@" + animadex.trigger`` with the parens escaped.

Output: ``data/artist_pool_default.json``
    {
      "version": 1,
      "source": "https://animadex.net/?mode=artists (sort=score)",
      "min_score": 0.5,
      "generated": "YYYY-MM-DD",
      "count": <int>,
      "tags": ["@sakura shiori", "@myoushun", ...]   # insert form, score desc
    }

The site rejects requests without a browser User-Agent (HTTP 403), so one is
sent explicitly. This is a maintenance/build script, not imported at runtime.

Usage:
    python scripts/fetch_artist_pool.py [--min-score 0.5] [--max-pages 0]
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
_LOCAL_SEARCH = _ROOT / "data" / "anima" / "search.json"
_OUT_PATH = _ROOT / "data" / "artist_pool_default.json"

_API = "https://animadex.net/api/artists/search?sort=score&page={page}"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_REFERER = "https://animadex.net/?mode=artists"


def _format_for_insert(tag: str) -> str:
    """Mirror web/modules/artist_suggest.js::formatArtistTagForInsert.

    ``"@bee_(deadflow)"`` -> ``"@bee \\(deadflow\\)"``.
    """
    return tag.replace("_", " ").replace("(", "\\(").replace(")", "\\)")


def _norm_slug(slug: str) -> str:
    """animadex slug -> local slug: drop the parentheses characters."""
    return slug.replace("(", "").replace(")", "")


def _fetch_page(page: int, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(
        _API.format(page=page),
        headers={"User-Agent": _UA, "Referer": _REFERER},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-score", type=float, default=0.5,
                    help="keep artists with score >= this (default 0.5)")
    ap.add_argument("--max-pages", type=int, default=0,
                    help="stop after N pages (0 = until score drops below cutoff)")
    ap.add_argument("--sleep", type=float, default=0.3,
                    help="seconds to sleep between page requests")
    args = ap.parse_args()

    if not _LOCAL_SEARCH.exists():
        print(f"ERROR: {_LOCAL_SEARCH} not found", file=sys.stderr)
        return 1
    local = json.loads(_LOCAL_SEARCH.read_text(encoding="utf-8"))
    by_slug = {e["slug"]: e for e in local if isinstance(e, dict) and e.get("slug")}

    tags: list[str] = []
    seen: set[str] = set()
    skipped_unknown = 0
    page = 1
    while True:
        try:
            data = _fetch_page(page)
        except Exception as exc:  # noqa: BLE001 — maintenance script
            print(f"ERROR fetching page {page}: {exc}", file=sys.stderr)
            return 1
        results = data.get("results", [])
        if not results:
            break
        stop = False
        for a in results:
            score = a.get("score", 0.0)
            if score < args.min_score:
                stop = True
                break
            local_entry = by_slug.get(_norm_slug(a.get("slug", "")))
            if not local_entry:
                skipped_unknown += 1
                continue
            insert = _format_for_insert(local_entry["tag"])
            key = insert.lower()
            if key in seen:
                continue
            seen.add(key)
            tags.append(insert)
        total_pages = data.get("pages", page)
        print(f"page {page}/{total_pages}: kept so far={len(tags)} "
              f"(unknown skipped={skipped_unknown})")
        if stop:
            break
        page += 1
        if args.max_pages and page > args.max_pages:
            break
        time.sleep(args.sleep)

    payload = {
        "version": 1,
        "source": "https://animadex.net/?mode=artists (sort=score)",
        "min_score": args.min_score,
        "generated": _dt.date.today().isoformat(),
        "count": len(tags),
        "tags": tags,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(tags)} artist tags (>= {args.min_score}) to {_OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
