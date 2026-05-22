"""benchmark_validate_route.py — end-to-end HTTP latency for /anima_prompt_helper/validate.

Spins up a real aiohttp.web application in-process with the extension's route
handler and sends 500 POST requests, reporting mean / p50 / p95 / max in ms.

Does NOT require ComfyUI to be running.

Run standalone:
    python scripts/benchmark_validate_route.py
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
EXTENSION_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(EXTENSION_ROOT))

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

# Import the real route-registration function; routes.py guards the ComfyUI
# import with try/except so this succeeds outside ComfyUI.
from python.api.routes import register  # noqa: E402

# ---------------------------------------------------------------------------
# Realistic request payload
# ---------------------------------------------------------------------------
PAYLOAD: dict = {
    "fields": {
        "quality": "masterpiece, best quality, high quality, score_9, score_8",
        "year": "newest, year 2025, year 2024",
        "rating": "safe",
        "count": "1girl, solo",
        "character": "Hatsune Miku",
        "series": "Vocaloid",
        "artist": "@wlop",
        "general": (
            "long hair, blue eyes, smile, school uniform, white shirt, "
            "pleated skirt, ribbon, blush, looking at viewer, upper body"
        ),
        "natural_language": (
            "An anime girl standing under cherry blossom trees with soft lighting."
        ),
    }
}
PAYLOAD_BYTES = json.dumps(PAYLOAD).encode()

REQUESTS = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentile(sorted_data: list[float], pct: float) -> float:
    if not sorted_data:
        return 0.0
    idx = (pct / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


def _build_app() -> web.Application:
    """Build a minimal aiohttp app with the extension's routes registered."""
    routes = web.RouteTableDef()
    register(routes)
    app = web.Application()
    app.add_routes(routes)
    return app


# ---------------------------------------------------------------------------
# Async benchmark
# ---------------------------------------------------------------------------

async def run_benchmark(n: int = REQUESTS) -> list[float]:
    """Send n POST requests; return list of round-trip durations in ms."""
    app = _build_app()
    samples: list[float] = []

    async with TestClient(TestServer(app)) as client:
        # Warm-up: 10 requests not counted
        for _ in range(10):
            await client.post(
                "/anima_prompt_helper/validate",
                data=PAYLOAD_BYTES,
                headers={"Content-Type": "application/json"},
            )

        for _ in range(n):
            t0 = time.perf_counter_ns()
            resp = await client.post(
                "/anima_prompt_helper/validate",
                data=PAYLOAD_BYTES,
                headers={"Content-Type": "application/json"},
            )
            elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
            assert resp.status == 200, f"Unexpected status {resp.status}"
            samples.append(elapsed_ms)

    return samples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Python {sys.version}")
    print(f"Endpoint: POST /anima_prompt_helper/validate  ({REQUESTS} requests + 10 warm-up)")
    print(f"Payload size: {len(PAYLOAD_BYTES)} bytes")
    print()

    samples = asyncio.run(run_benchmark(REQUESTS))

    sorted_ms = sorted(samples)
    mean_ = statistics.mean(sorted_ms)
    p50   = _percentile(sorted_ms, 50)
    p95   = _percentile(sorted_ms, 95)
    max_  = sorted_ms[-1]

    print(f"  mean={mean_:.3f} ms  p50={p50:.3f} ms  p95={p95:.3f} ms  max={max_:.3f} ms")


if __name__ == "__main__":
    main()
    sys.exit(0)
