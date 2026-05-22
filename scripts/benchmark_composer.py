"""benchmark_composer.py — throughput benchmark for composer.join_fields,
composer.join_negative_fields, and validators.validate_fields.

Run standalone:
    python scripts/benchmark_composer.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow importing extension modules without ComfyUI on sys.path
# ---------------------------------------------------------------------------
EXTENSION_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(EXTENSION_ROOT))

from python.composer import join_fields, join_negative_fields  # noqa: E402
from python.validators import validate_fields                  # noqa: E402

# ---------------------------------------------------------------------------
# Representative payload (~10 tags per main field, realistic values)
# ---------------------------------------------------------------------------
NEGATIVE_FIELDS: dict[str, str] = {
    "quality_negative": "worst quality, low quality, normal quality",
    "score_negative": "score_1, score_2, score_3, score_4",
    "style_negative": "artifacts, blurry, jpeg artifacts, noise, pixelated",
    "content_negative": "bad anatomy, extra limbs, malformed hands, missing fingers",
    "meta_negative": "watermark, signature, text, logo, username",
    "extra_negative": "cropped, out of frame, duplicate, lowres",
}

FIELDS: dict[str, str] = {
    "quality": "masterpiece, best quality, high quality, score_9, score_8",
    "year": "newest, year 2025, year 2024",
    "rating": "safe",
    "count": "1girl, solo",
    "character": "Hatsune Miku, Asuna Yuuki",
    "series": "Vocaloid, Sword Art Online",
    "artist": "@wlop, @artgerm",
    "general": (
        "long hair, blue eyes, smile, school uniform, white shirt, "
        "pleated skirt, ribbon, blush, looking at viewer, upper body, "
        "cherry blossoms, outdoor, sunlight"
    ),
    "natural_language": (
        "A beautiful anime girl standing under cherry blossom trees "
        "with soft natural lighting in the afternoon."
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _palette_stats() -> tuple[int, int]:
    """Return (file_count, total_tag_count) from the data directory."""
    data_dir = EXTENSION_ROOT / "data"
    palette_files = list(data_dir.glob("tag_palette*.json"))
    total_tags = 0
    for p in palette_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for cat in data.get("categories", []):
                total_tags += len(cat.get("tags", []))
        except Exception:
            pass
    return len(palette_files), total_tags


def _fmt(ns_per_op: float) -> str:
    """Format ns/op as microseconds."""
    us = ns_per_op / 1_000
    ops_s = 1_000_000_000 / ns_per_op if ns_per_op > 0 else float("inf")
    return f"{us:>8.2f} us/op  ({ops_s:>12,.0f} ops/s)"


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def bench_join_fields(iterations: int = 100_000) -> float:
    """Return ns/op for join_fields."""
    # Warm-up
    for _ in range(100):
        join_fields(FIELDS)

    t0 = time.perf_counter_ns()
    for _ in range(iterations):
        join_fields(FIELDS)
    elapsed_ns = time.perf_counter_ns() - t0
    return elapsed_ns / iterations


def bench_join_negative_fields(preset: str, iterations: int = 100_000) -> float:
    """Return ns/op for join_negative_fields with the given preset."""
    # Warm-up
    for _ in range(100):
        join_negative_fields(NEGATIVE_FIELDS, preset=preset)

    t0 = time.perf_counter_ns()
    for _ in range(iterations):
        join_negative_fields(NEGATIVE_FIELDS, preset=preset)
    elapsed_ns = time.perf_counter_ns() - t0
    return elapsed_ns / iterations


def bench_validate_fields(iterations: int = 10_000) -> float:
    """Return ns/op for validate_fields."""
    # Warm-up
    for _ in range(50):
        validate_fields(FIELDS)

    t0 = time.perf_counter_ns()
    for _ in range(iterations):
        validate_fields(FIELDS)
    elapsed_ns = time.perf_counter_ns() - t0
    return elapsed_ns / iterations


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    file_count, total_tags = _palette_stats()

    print(f"Python {sys.version}")
    print(f"Palette files: {file_count}  |  Total tags in palette: {total_tags}")
    print()

    join_ns = bench_join_fields(100_000)
    neg_none_ns = bench_join_negative_fields("none", 100_000)
    neg_ooo_ns = bench_join_negative_fields("ooo_anima_default", 100_000)
    neg_base_ns = bench_join_negative_fields("anima_base_default", 100_000)
    validate_ns = bench_validate_fields(10_000)

    print(f"composer.join_fields:                  {_fmt(join_ns)}")
    print(f"composer.join_negative_fields (none):  {_fmt(neg_none_ns)}")
    print(f"composer.join_negative_fields (ooo):   {_fmt(neg_ooo_ns)}")
    print(f"composer.join_negative_fields (base):  {_fmt(neg_base_ns)}")
    print(f"validators.validate_fields:            {_fmt(validate_ns)}")

    # Sanity check: the three negative variants should not differ by more than 5x
    neg_values = [neg_none_ns, neg_ooo_ns, neg_base_ns]
    neg_min = min(neg_values)
    neg_max = max(neg_values)
    if neg_min > 0 and neg_max / neg_min > 5.0:
        print(
            f"\nWARNING: negative variant spread exceeds 5x "
            f"(min={neg_min/1_000:.2f} us/op, max={neg_max/1_000:.2f} us/op, "
            f"ratio={neg_max/neg_min:.1f}x)"
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
