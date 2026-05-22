"""routes.py — aiohttp route handlers for anima-prompt-helper.

Five endpoints:
    GET  /anima_prompt_helper/palette            — serve merged tag palette
    GET  /anima_prompt_helper/spec               — serve data/anima_spec.json
    GET  /anima_prompt_helper/character_presets  — serve data/character_presets.json
    POST /anima_prompt_helper/validate           — run validation on supplied fields
    GET  /anima_prompt_helper/health             — extension health/diagnostic report
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from ..validators import validate_fields

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extension root — two levels up from python/api/
# ---------------------------------------------------------------------------
_EXT_ROOT = Path(__file__).parent.parent.parent
_PALETTE_PATH = _EXT_ROOT / "data" / "tag_palette.json"
_PALETTE_EXTRAS_PATH = _EXT_ROOT / "data" / "tag_palette_extras.json"
_SPEC_PATH = _EXT_ROOT / "data" / "anima_spec.json"
_CHARACTER_PRESETS_PATH = _EXT_ROOT / "data" / "character_presets.json"
_I18N_JA_PATH = _EXT_ROOT / "i18n" / "ja.json"

# In-memory caches (conceptually constant after first population).
_palette_cache: dict[str, Any] | None = None
_spec_cache: dict[str, Any] | None = None
_character_presets_cache: dict[str, Any] | None = None

# Health: lazily-loaded version string cached after first read.
_version_cache: str | None = None

# Locks prevent simultaneous coroutines from double-loading the data files.
_palette_lock: asyncio.Lock = asyncio.Lock()
_spec_lock: asyncio.Lock = asyncio.Lock()
_character_presets_lock: asyncio.Lock = asyncio.Lock()

# Maximum accepted request body size for POST /validate (64 KB).
_MAX_BODY_BYTES: int = 64 * 1024


# ---------------------------------------------------------------------------
# Helper: load a JSON data file with caching
# ---------------------------------------------------------------------------

def _load_json_file(path: Path) -> dict[str, Any]:
    """Read and parse a JSON file from *path*.

    Preconditions:
        - ``path`` is a ``pathlib.Path``.
    Postconditions:
        - Returns the parsed dict.
    Raises:
        FileNotFoundError: if the file does not exist.
        json.JSONDecodeError: if the content is invalid JSON.
    """
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_palette_merged() -> dict[str, Any]:
    """Load and merge tag_palette.json with tag_palette_extras.json.

    Preconditions:
        - ``_PALETTE_PATH`` exists and contains valid JSON.
        - ``_PALETTE_EXTRAS_PATH`` may or may not exist.
    Postconditions:
        - Returns a dict with shape ``{"version": str, "categories": list}``
          where categories from both files are concatenated and sorted by
          the ``order`` field (categories without ``order`` go last with
          a default of 9999).
        - If extras file is absent, only base categories are returned.
    Raises:
        FileNotFoundError: if the base palette file does not exist.
        json.JSONDecodeError: if either file contains invalid JSON.
    """
    base = _load_json_file(_PALETTE_PATH)
    base_categories: list[dict[str, Any]] = list(base.get("categories", []))

    extras_categories: list[dict[str, Any]] = []
    if _PALETTE_EXTRAS_PATH.exists():
        try:
            extras = _load_json_file(_PALETTE_EXTRAS_PATH)
            extras_categories = list(extras.get("categories", []))
        except json.JSONDecodeError as exc:
            logger.debug(
                "tag_palette_extras.json parse error, skipping extras: %s", exc
            )
            raise
    else:
        logger.debug(
            "tag_palette_extras.json not found at %s; skipping extras",
            _PALETTE_EXTRAS_PATH,
        )

    merged_categories = base_categories + extras_categories
    merged_categories.sort(key=lambda c: c.get("order", 9999))

    return {"version": base.get("version", "1.0"), "categories": merged_categories}


# ---------------------------------------------------------------------------
# Health helpers
# ---------------------------------------------------------------------------

def _read_version() -> str:
    """Read the package version from pyproject.toml, caching after first call.

    Preconditions: none (always safe to call).
    Postconditions: Returns a non-empty string; falls back to "0.2.0".
    Invariants: Result is cached in ``_version_cache`` after the first call.
    """
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        toml_path = _EXT_ROOT / "pyproject.toml"
        text = toml_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                _, _, raw = stripped.partition("=")
                _version_cache = raw.strip().strip('"').strip("'")
                return _version_cache
    except Exception:
        pass
    _version_cache = "0.2.0"
    return _version_cache


def _file_info(path: Path, cached: bool) -> dict[str, Any]:
    """Return a health data-file entry dict for *path*.

    Preconditions: ``path`` is a ``pathlib.Path``.
    Postconditions: Returns ``{"exists": bool, "cached": bool, "size_bytes": int|None}``.
    """
    exists = path.exists()
    size_bytes: int | None = None
    if exists:
        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = None
    return {"exists": exists, "cached": cached, "size_bytes": size_bytes}


def build_health_payload() -> dict[str, Any]:
    """Construct the health response payload.

    Preconditions: none.
    Postconditions:
        - Returns a dict with keys: status, version, data_files, node_classes, routes.
        - ``status`` is "ok" iff all expected data files exist.
        - Never raises; on import error sets node_classes to ["import_error"].
    """
    data_files: dict[str, Any] = {
        "tag_palette.json": _file_info(_PALETTE_PATH, _palette_cache is not None),
        "tag_palette_extras.json": _file_info(_PALETTE_EXTRAS_PATH, False),
        "anima_spec.json": _file_info(_SPEC_PATH, _spec_cache is not None),
        "character_presets.json": _file_info(_CHARACTER_PRESETS_PATH, _character_presets_cache is not None),
        "i18n/ja.json": _file_info(_I18N_JA_PATH, False),
    }

    all_exist = all(info["exists"] for info in data_files.values())
    status = "ok" if all_exist else "degraded"

    # Dynamically read node class names from the root __init__.py.
    node_classes: list[str]
    try:
        import importlib
        root_module = importlib.import_module("__init__")
        mappings = getattr(root_module, "NODE_CLASS_MAPPINGS", None)
        if mappings is None:
            # Try loading from file path directly
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_aph_root_init", _EXT_ROOT / "__init__.py"
            )
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            mappings = getattr(mod, "NODE_CLASS_MAPPINGS", {})
        node_classes = list(mappings.keys()) if mappings else ["import_error"]
        if not node_classes:
            node_classes = ["import_error"]
            status = "degraded"
    except Exception:
        node_classes = ["import_error"]
        status = "degraded"

    routes_list = [
        "/anima_prompt_helper/palette",
        "/anima_prompt_helper/spec",
        "/anima_prompt_helper/character_presets",
        "/anima_prompt_helper/validate",
        "/anima_prompt_helper/health",
    ]

    return {
        "status": status,
        "version": _read_version(),
        "data_files": data_files,
        "node_classes": node_classes,
        "routes": routes_list,
    }


# ---------------------------------------------------------------------------
# Route registration helper (called from api/__init__.py)
# ---------------------------------------------------------------------------

def register(routes: web.RouteTableDef) -> None:
    """Attach all five route handlers to *routes*.

    Preconditions:
        - ``routes`` is an ``aiohttp.web.RouteTableDef``.
    Postconditions:
        - Five routes are registered: palette, spec, character_presets,
          validate, health.
    Invariants:
        - Handlers are idempotent read-only operations.
    """

    @routes.get("/anima_prompt_helper/palette")
    async def get_palette(request: web.Request) -> web.Response:
        """Serve the merged tag palette dataset (base + extras, sorted by order).

        Returns:
            200 with merged palette JSON (30 categories),
            503 if base file missing,
            500 on parse error.
        """
        global _palette_cache
        async with _palette_lock:
            if _palette_cache is None:
                if not _PALETTE_PATH.exists():
                    logger.warning("tag_palette.json not found at %s", _PALETTE_PATH)
                    return web.json_response(
                        {"error": "palette_not_found"}, status=503
                    )
                try:
                    _palette_cache = load_palette_merged()
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse palette file: %s", exc)
                    return web.json_response(
                        {"error": "palette_parse_error"}, status=500
                    )
        return web.json_response(_palette_cache)

    @routes.get("/anima_prompt_helper/spec")
    async def get_spec(request: web.Request) -> web.Response:
        """Serve the Anima spec (canonical order, presets, validation params).

        Returns:
            200 with spec JSON, 503 if file missing, 500 on parse error.
        """
        global _spec_cache
        async with _spec_lock:
            if _spec_cache is None:
                if not _SPEC_PATH.exists():
                    logger.warning("anima_spec.json not found at %s", _SPEC_PATH)
                    return web.json_response(
                        {"error": "spec_not_found"}, status=503
                    )
                try:
                    _spec_cache = _load_json_file(_SPEC_PATH)
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse anima_spec.json: %s", exc)
                    return web.json_response(
                        {"error": "spec_parse_error"}, status=500
                    )
        return web.json_response(_spec_cache)

    @routes.get("/anima_prompt_helper/character_presets")
    async def get_character_presets(request: web.Request) -> web.Response:
        """Serve the character preset list verbatim.

        Returns:
            200 with character_presets JSON ({version, presets:[...]}),
            503 if file missing,
            500 on parse error.
        """
        global _character_presets_cache
        async with _character_presets_lock:
            if _character_presets_cache is None:
                if not _CHARACTER_PRESETS_PATH.exists():
                    logger.warning(
                        "character_presets.json not found at %s",
                        _CHARACTER_PRESETS_PATH,
                    )
                    return web.json_response(
                        {"error": "character_presets_not_found"}, status=503
                    )
                try:
                    _character_presets_cache = _load_json_file(_CHARACTER_PRESETS_PATH)
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse character_presets.json: %s", exc)
                    return web.json_response(
                        {"error": "character_presets_parse_error"}, status=500
                    )
        return web.json_response(_character_presets_cache)

    @routes.post("/anima_prompt_helper/validate")
    async def post_validate(request: web.Request) -> web.Response:
        """Run server-side validation on the supplied field values.

        Request body (JSON, Content-Type: application/json, max 64 KB):
            {"fields": {"quality": "...", ...}}

        Returns:
            200 with {"issues": [...], "assembled_length": N}
            400 on malformed body, wrong Content-Type, or oversized body
            500 on unexpected exception
        """
        # Reject non-JSON Content-Type.
        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return web.json_response({"error": "invalid_request"}, status=400)

        # Read body with an explicit size cap to prevent unbounded memory use.
        try:
            raw_bytes = await request.read()
        except Exception as exc:
            logger.warning("validate: failed to read request body: %s", exc)
            return web.json_response({"error": "invalid_request"}, status=400)

        if len(raw_bytes) > _MAX_BODY_BYTES:
            logger.warning(
                "validate: request body too large (%d bytes > %d)",
                len(raw_bytes),
                _MAX_BODY_BYTES,
            )
            return web.json_response({"error": "invalid_request"}, status=400)

        try:
            body = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            logger.warning("validate: invalid JSON body: %s", exc)
            return web.json_response({"error": "invalid_request"}, status=400)

        if not isinstance(body, dict) or "fields" not in body:
            return web.json_response({"error": "invalid_request"}, status=400)

        raw_fields = body["fields"]
        if not isinstance(raw_fields, dict):
            return web.json_response({"error": "invalid_request"}, status=400)

        # Coerce all values to str; treat absent/null as "".
        fields: dict[str, str] = {
            k: (v if isinstance(v, str) else "")
            for k, v in raw_fields.items()
        }

        try:
            issues, assembled_length = validate_fields(fields)
        except Exception as exc:
            logger.exception("validate: unexpected error: %s", exc)
            return web.json_response({"error": "internal_error"}, status=500)

        issues_payload = [
            {
                "field": issue.field,
                "tag": issue.tag,
                "rule": issue.rule,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in issues
        ]

        return web.json_response(
            {"issues": issues_payload, "assembled_length": assembled_length}
        )

    @routes.get("/anima_prompt_helper/health")
    async def get_health(request: web.Request) -> web.Response:
        """Return a diagnostic health/status report for the extension.

        Always returns HTTP 200 so operators can programmatically parse the
        body regardless of the extension state. The ``status`` field in the
        body reflects the actual health ("ok" or "degraded").

        Returns:
            200 with health JSON (status, version, data_files, node_classes,
            routes). Never returns a 5xx response.
        """
        try:
            payload = build_health_payload()
        except Exception as exc:
            logger.error("health: unexpected error building payload: %s", exc)
            payload = {
                "status": "degraded",
                "version": _read_version(),
                "data_files": {},
                "node_classes": ["import_error"],
                "routes": [
                    "/anima_prompt_helper/palette",
                    "/anima_prompt_helper/spec",
                    "/anima_prompt_helper/character_presets",
                    "/anima_prompt_helper/validate",
                    "/anima_prompt_helper/health",
                ],
            }
        return web.json_response(payload)

