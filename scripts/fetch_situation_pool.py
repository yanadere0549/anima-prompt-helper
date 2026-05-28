#!/usr/bin/env python3
"""fetch_situation_pool.py - build the built-in situation/scene/location tag pool.

Pulls general tags from the Danbooru public API
(``/tags.json?search[category]=0&search[order]=count``)
and keeps every tag whose name contains at least one keyword from the
situation whitelist (location, activity, weather/time, or costume helpers).

Only tags with ``post_count >= --min-post-count`` (default 5000) are kept to
avoid overly niche tags.

Output: ``data/situation_pool_default.json``
    {
      "version": 1,
      "source": "https://danbooru.donmai.us/tags.json (category=general, filtered by situation whitelist)",
      "min_post_count": 5000,
      "generated": "YYYY-MM-DD",
      "count": <int>,
      "tags": ["classroom", "school uniform", "morning", ...]
    }

Tags are converted from danbooru raw form (underscores) to prompt insert form
(spaces), with ``(`` and ``)`` backslash-escaped.

Usage:
    python scripts/fetch_situation_pool.py [--min-post-count 5000] [--max-pages 3]
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
_OUT_PATH = _ROOT / "data" / "situation_pool_default.json"

_API = (
    "https://danbooru.donmai.us/tags.json"
    "?search[category]=0&search[order]=count&limit=1000&page={page}"
)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# Pre-fetched cache dir: if tmp_danbooru_page{n}.json exists beside data/,
# read from it instead of hitting the live API.
_CACHE_DIR = _ROOT / "data"

# ---------------------------------------------------------------------------
# Situation whitelist — partial-match keywords.
# Any danbooru tag (with underscores replaced by spaces) that *contains* one
# of these words/phrases is considered situation-related.
# ---------------------------------------------------------------------------
_WHITELIST: list[str] = [
    # --- locations ---
    "classroom", "school", "hallway", "library", "gym", "cafeteria",
    "dormitory", "bedroom", "kitchen", "bathroom", "living room",
    "dining room", "balcony", "rooftop", "garden", "park", "beach",
    "ocean", "mountain", "forest", "lake", "river", "waterfall",
    "street", "alley", "subway", "train station", "train", "bus",
    "airport", "hotel", "cafe", "restaurant", "bar", "izakaya",
    "convenience store", "shopping mall", "market", "shrine", "temple",
    "church", "festival", "stage", "concert", "stadium",
    "swimming pool", "hot spring", "onsen", "ryokan", "hospital",
    "clinic", "office", "factory", "ruins", "dungeon", "castle",
    "throne room", "throne", "courtyard", "terrace", "attic",
    "basement", "cave", "desert", "snowfield", "indoors", "outdoors",
    "indoor", "outdoor",
    # --- activities / scenes ---
    "sitting", "standing", "lying", "walking", "running", "jumping",
    "dancing", "singing", "eating", "drinking", "cooking", "reading",
    "writing", "studying", "sleeping", "stretching", "yawning",
    "bathing", "showering", "swimming", "surfing", "skating",
    "skateboarding", "cycling", "driving", "fishing", "hiking",
    "camping", "picnic", "shopping", "traveling", "sightseeing",
    "working", "gardening", "painting", "drawing", "playing",
    "gaming", "playing instrument", "playing piano", "playing guitar",
    "holding phone", "taking photo", "selfie",
    "looking at viewer", "looking back", "looking up", "looking down",
    "smiling", "laughing", "crying", "blushing", "embarrassed",
    "sleepy", "tired", "dreaming",
    # --- time / weather / lighting ---
    "morning", "afternoon", "evening", "night", "dusk", "dawn",
    "sunset", "sunrise", "midnight", "golden hour", "sunlight",
    "moonlight", "starlight", "neon lights", "lantern", "candle",
    "streetlight", "snowing", "raining", "thunder", "storm",
    "foggy", "misty", "cloudy", "sunny", "windy", "snow", "rain",
    "fog", "mist", "cherry blossoms", "falling leaves", "autumn leaves",
    "petals", "fireworks", "snowflakes", "sparkles",
    # --- costume helpers ---
    "school uniform", "sailor uniform", "summer uniform", "pe uniform",
    "gym uniform", "business suit", "lab coat", "swimsuit", "bikini",
    "school swimsuit", "yukata", "kimono", "hakama", "miko", "maid",
    "nurse", "witch", "idol costume", "casual clothes", "pajamas",
    "apron", "lingerie", "sportswear", "raincoat", "coat", "scarf",
    "gloves", "hat", "beret", "baseball cap", "glasses", "headphones",
]

# Pre-sort by length descending so longer phrases are tested first (prevents
# "school" matching before "school uniform" is even tried — doesn't matter for
# current logic but keeps things deterministic).
_WHITELIST_SORTED = sorted(_WHITELIST, key=len, reverse=True)

# Explicit denylist — normalized tags (underscores replaced by spaces,
# lowercased) that would pass the whitelist substring test but are NSFW or
# otherwise inappropriate for general prompt use.  Checked after whitelist
# matching; matching any entry causes the tag to be dropped.
_DENYLIST: frozenset[str] = frozenset({
    "bar censor",
    "bara",
    "restrained",
    "lingerie",
    "shibari",
    "standing sex",
    "spreading own pussy",
    "body writing",
    "naked apron",
    "maebari",
    "bikini pull",
})


def _format_for_insert(raw: str) -> str:
    """Convert danbooru raw tag to prompt insert form.

    ``"school_uniform"`` -> ``"school uniform"``
    ``"pool_(disambiguation)"`` -> ``"pool \\(disambiguation\\)"``
    """
    return raw.replace("_", " ").replace("(", "\\(").replace(")", "\\)")


def _matches_whitelist(normalized: str) -> bool:
    """Return True if *normalized* (underscores already replaced by spaces,
    lowercased) passes the whitelist test and is NOT in the denylist.

    Preconditions:
        - ``normalized`` is lowercase with underscores replaced by spaces.
    Postconditions:
        - Returns False if the tag is in _DENYLIST (exact match).
        - Returns True only if a whitelist keyword is a substring of the tag.
    """
    if normalized in _DENYLIST:
        return False
    for kw in _WHITELIST_SORTED:
        if kw in normalized:
            return True
    return False


def _fetch_page(page: int, timeout: float = 30.0) -> list[dict]:
    cache = _CACHE_DIR / f"tmp_danbooru_page{page}.json"
    if cache.exists():
        print(f"  (using cached {cache.name})")
        return json.loads(cache.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        _API.format(page=page),
        headers={"User-Agent": _UA},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-post-count", type=int, default=5000,
                    help="keep tags with post_count >= this (default 5000)")
    ap.add_argument("--max-pages", type=int, default=3,
                    help="max API pages to fetch (1000 tags/page, default 3)")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="seconds to sleep between page requests (default 0.5)")
    args = ap.parse_args()

    tags: list[str] = []
    seen: set[str] = set()

    for page in range(1, args.max_pages + 1):
        print(f"fetching page {page}/{args.max_pages} …", flush=True)
        try:
            results = _fetch_page(page)
        except Exception as exc:  # noqa: BLE001 — maintenance script
            print(f"ERROR fetching page {page}: {exc}", file=sys.stderr)
            return 1

        if not results:
            print(f"page {page}: empty response, stopping.")
            break

        kept_this_page = 0
        for entry in results:
            name: str = entry.get("name", "")
            count: int = entry.get("post_count", 0)
            if count < args.min_post_count:
                # Results are sorted by count desc; once below threshold, skip
                # but don't break — some tags at the same post_count could pass.
                continue
            normalized = name.replace("_", " ").lower()
            if not _matches_whitelist(normalized):
                continue
            key = normalized
            if key in seen:
                continue
            seen.add(key)
            tags.append(_format_for_insert(name))
            kept_this_page += 1

        print(f"  kept {kept_this_page} tags this page (total so far: {len(tags)})")

        if page < args.max_pages:
            time.sleep(args.sleep)

    payload = {
        "version": 1,
        "source": (
            "https://danbooru.donmai.us/tags.json"
            " (category=general, filtered by situation whitelist)"
        ),
        "min_post_count": args.min_post_count,
        "generated": _dt.date.today().isoformat(),
        "count": len(tags),
        "tags": tags,
    }
    _OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {len(tags)} situation tags (post_count >= {args.min_post_count})"
          f" to {_OUT_PATH}")
    if tags:
        print("top 20 sample:", tags[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
