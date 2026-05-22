# Benchmark Suite — anima-prompt-helper

Three standalone scripts that document baseline performance. Run each from the
extension root (`custom_nodes/anima-prompt-helper/`).

---

## 1. `benchmark_composer.py`

**What it measures:** Pure Python throughput of `composer.join_fields()`,
`composer.join_negative_fields()` (three preset variants), and
`validators.validate_fields()` — no I/O, no network.

**Method:**
- 100,000 iterations of `join_fields` under `time.perf_counter_ns()`.
- 100,000 iterations of `join_negative_fields(preset="none")` — full
  6-field tokenize-and-join path.
- 100,000 iterations of `join_negative_fields(preset="ooo_anima_default")` —
  lazy-load + preset-override early-return path.
- 100,000 iterations of `join_negative_fields(preset="anima_base_default")` —
  lazy-load + preset-override early-return path.
- 10,000 iterations of `validate_fields` (all seven rules).
- Positive composer uses a realistic 9-field payload; negative composer uses a
  realistic 6-field payload (~4-5 tags each: quality_negative, score_negative,
  style_negative, content_negative, meta_negative, extra_negative).
- After timing, a **sanity check** asserts the three negative variants do not
  differ by more than 5×.  The preset paths legitimately exceed this threshold
  because they return the cached model-default string immediately (a single dict
  lookup) rather than tokenizing all fields; a WARNING line is printed when the
  ratio is exceeded so the spread is visible in CI logs.

**Run:**
```
python scripts/benchmark_composer.py
```

**Sample output (Python 3.11.13, Windows 11):**
```
Python 3.11.13 (main, Jul 23 2025, 00:29:09) [MSC v.1944 64 bit (AMD64)]
Palette files: 2  |  Total tags in palette: 509

composer.join_fields:                      3.95 us/op  (     253,352 ops/s)
composer.join_negative_fields (none):      2.72 us/op  (     367,565 ops/s)
composer.join_negative_fields (ooo):       0.15 us/op  (   6,713,392 ops/s)
composer.join_negative_fields (base):      0.15 us/op  (   6,887,764 ops/s)
validators.validate_fields:               28.25 us/op  (      35,404 ops/s)

WARNING: negative variant spread exceeds 5x (min=0.15 us/op, max=2.72 us/op, ratio=18.7x)
```

> **Note on the WARNING:** The large spread (≈18×) is expected and by design.
> The `ooo_anima_default` and `anima_base_default` paths skip all field
> processing and return a single cached string lookup, while `preset="none"`
> tokenizes all six fields.  The WARNING exists to surface the spread for
> review, not to indicate a defect.

---

## 2. `benchmark_palette_load.py`

**What it measures:** Cold-load latency for the JSON palette data files and the
merge operation that assembles the combined structure returned by the
`GET /anima_prompt_helper/palette` handler.

**Method:**
- Benchmark 1: `json.load(open(tag_palette.json))` — 100 iterations.
- Benchmark 2: load both files + sort merged categories — 100 iterations.
- Reports mean / p50 / p95 / max in milliseconds.
- Prints `sys.getsizeof` of each parsed dict as a shallow size baseline.

**Run:**
```
python scripts/benchmark_palette_load.py
```

**Sample output (Python 3.11.13, Windows 11):**
```
--- Benchmark 1: json.load(tag_palette.json) x100 ---
  tag_palette.json raw load
    mean=0.168 ms  p50=0.164 ms  p95=0.172 ms  max=0.366 ms

--- Benchmark 2: full merge (both files) x100 ---
  merge both palettes
    mean=0.325 ms  p50=0.305 ms  p95=0.471 ms  max=0.562 ms

--- Memory size baseline (sys.getsizeof, shallow) ---
  sys.getsizeof tag_palette.json parsed dict:       184 bytes
  sys.getsizeof tag_palette_extras parsed dict:     184 bytes
  sys.getsizeof merged result dict:                 184 bytes
  Merged categories: 30  |  Total tags: 509
```

Note: `sys.getsizeof` is a shallow measure (dict object overhead only). Actual
in-memory footprint of the nested structure is much larger.

---

## 3. `benchmark_validate_route.py`

**What it measures:** End-to-end HTTP round-trip latency for
`POST /anima_prompt_helper/validate` including JSON serialization/deserialization,
route dispatch, and validation logic.

**Method:**
- Uses `aiohttp.test_utils.TestClient` + `TestServer` — no external process.
- Registers the real `routes.register()` handler from `python.api.routes`.
- 10 warm-up requests (not counted) then 500 timed requests.
- Reports mean / p50 / p95 / max in milliseconds.

**Does not require ComfyUI to be running.** The `server` import in
`python/api/__init__.py` is guarded with `try/except ImportError`.

**Run:**
```
python scripts/benchmark_validate_route.py
```

**Sample output (Python 3.11.13, Windows 11):**
```
Python 3.11.13 (main, Jul 23 2025, 00:29:09) [MSC v.1944 64 bit (AMD64)]
Endpoint: POST /anima_prompt_helper/validate  (500 requests + 10 warm-up)
Payload size: 461 bytes

  mean=0.918 ms  p50=0.908 ms  p95=1.056 ms  max=1.626 ms
```

---

## Build and release scripts

For packaging and distribution, see the companion scripts:

| Script | Purpose |
|--------|---------|
| `scripts/build_dist.ps1` / `build_dist.sh` | Run `python -m build --sdist --wheel` and report output sizes. |
| `scripts/zip_release.ps1` / `zip_release.sh` | Build `dist/anima-prompt-helper-v0.2.0.zip` matching the GitHub release workflow. |

---

## Dependencies

All scripts use only the Python standard library plus `aiohttp`, which is
already part of ComfyUI's environment. No additional packages are required.

## Timing

| Script                        | Typical wall time |
|-------------------------------|-------------------|
| `benchmark_composer.py`       | ~1–2 s            |
| `benchmark_palette_load.py`   | ~1 s              |
| `benchmark_validate_route.py` | ~5 s              |
