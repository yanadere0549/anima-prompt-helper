"""benchmark_palette_load.py — cold-load and merge latency for tag palette files.

Measures:
  1. json.load() time for tag_palette.json alone (100 iterations).
  2. The full "in-route merge" logic: load both palette files, walk categories,
     and assemble a merged categories list — the same work the palette GET
     handler performs on first request.

Run standalone:
    python scripts/benchmark_palette_load.py
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
EXTENSION_ROOT = Path(__file__).parent.parent
PALETTE_PATH = EXTENSION_ROOT / "data" / "tag_palette.json"
EXTRAS_PATH  = EXTENSION_ROOT / "data" / "tag_palette_extras.json"

ITERATIONS = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_data: list[float], pct: float) -> float:
    """Return the pct-th percentile from a sorted list (0-100)."""
    if not sorted_data:
        return 0.0
    idx = (pct / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def _report(label: str, samples_ns: list[float]) -> None:
    """Print mean / p50 / p95 / max for a list of nanosecond samples."""
    samples_ms = [s / 1_000_000 for s in samples_ns]
    sorted_ms = sorted(samples_ms)
    mean_ = statistics.mean(sorted_ms)
    p50   = _percentile(sorted_ms, 50)
    p95   = _percentile(sorted_ms, 95)
    max_  = sorted_ms[-1]
    print(f"  {label}")
    print(f"    mean={mean_:.3f} ms  p50={p50:.3f} ms  p95={p95:.3f} ms  max={max_:.3f} ms")


# ---------------------------------------------------------------------------
# Benchmark 1: raw JSON load of tag_palette.json
# ---------------------------------------------------------------------------

def bench_single_load(iterations: int = ITERATIONS) -> list[float]:
    """Time json.load for tag_palette.json; return list of ns durations."""
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        with PALETTE_PATH.open(encoding="utf-8") as fh:
            json.load(fh)
        samples.append(time.perf_counter_ns() - t0)
    return samples


# ---------------------------------------------------------------------------
# Benchmark 2: in-route merge logic (both files + assemble merged structure)
# ---------------------------------------------------------------------------

def _merge_palettes() -> dict:
    """Replicate the palette GET handler merge logic.

    Postconditions:
        - Returns a dict with key "categories" containing the combined list
          sorted by each category's "order" field.
    """
    palette = json.loads(PALETTE_PATH.read_bytes())
    extras  = json.loads(EXTRAS_PATH.read_bytes())

    merged_cats: list[dict] = list(palette.get("categories", []))
    for cat in extras.get("categories", []):
        merged_cats.append(cat)

    merged_cats.sort(key=lambda c: c.get("order", 999))

    return {
        "version": palette.get("version", "1.0"),
        "categories": merged_cats,
    }


def bench_merge_load(iterations: int = ITERATIONS) -> list[float]:
    """Time the full merge logic; return list of ns durations."""
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        _merge_palettes()
        samples.append(time.perf_counter_ns() - t0)
    return samples


# ---------------------------------------------------------------------------
# Memory size observation (rough baseline via sys.getsizeof)
# ---------------------------------------------------------------------------

def _size_info() -> None:
    import sys as _sys
    palette = json.loads(PALETTE_PATH.read_bytes())
    extras  = json.loads(EXTRAS_PATH.read_bytes())
    merged  = _merge_palettes()
    print(f"  sys.getsizeof tag_palette.json parsed dict:  {_sys.getsizeof(palette):>8,} bytes")
    print(f"  sys.getsizeof tag_palette_extras parsed dict:{_sys.getsizeof(extras):>8,} bytes")
    print(f"  sys.getsizeof merged result dict:            {_sys.getsizeof(merged):>8,} bytes")
    total_tags = sum(len(c.get("tags", [])) for c in merged["categories"])
    print(f"  Merged categories: {len(merged['categories'])}  |  Total tags: {total_tags}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Python {sys.version}")
    print(f"tag_palette.json : {PALETTE_PATH}")
    print(f"tag_palette_extras.json: {EXTRAS_PATH}")
    print()

    print(f"--- Benchmark 1: json.load(tag_palette.json) x{ITERATIONS} ---")
    single_samples = bench_single_load(ITERATIONS)
    _report("tag_palette.json raw load", single_samples)
    print()

    print(f"--- Benchmark 2: full merge (both files) x{ITERATIONS} ---")
    merge_samples = bench_merge_load(ITERATIONS)
    _report("merge both palettes", merge_samples)
    print()

    print("--- Memory size baseline (sys.getsizeof, shallow) ---")
    _size_info()


if __name__ == "__main__":
    main()
    sys.exit(0)
