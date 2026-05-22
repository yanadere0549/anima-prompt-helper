"""routes.py — aiohttp route handlers for anima-prompt-helper.

Endpoints:
    GET    /anima_prompt_helper/palette                       — serve merged tag palette
    GET    /anima_prompt_helper/spec                          — serve data/anima_spec.json
    GET    /anima_prompt_helper/character_presets             — serve merged builtin+user
                                                                character presets
    POST   /anima_prompt_helper/user_character_presets        — create / update user preset
    DELETE /anima_prompt_helper/user_character_presets/{id}   — delete user preset
    GET    /anima_prompt_helper/situation_presets             — serve merged builtin+user
                                                                situation presets
    POST   /anima_prompt_helper/user_situation_presets        — create / update user situation
    DELETE /anima_prompt_helper/user_situation_presets/{id}   — delete user situation
    GET    /anima_prompt_helper/artists                       — serve trimmed artist suggest index
    POST   /anima_prompt_helper/validate                      — run validation on supplied fields
    GET    /anima_prompt_helper/health                        — extension health/diagnostic report
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
_USER_CHARACTER_PRESETS_PATH = _EXT_ROOT / "data" / "user_character_presets.json"
_SITUATION_PRESETS_PATH = _EXT_ROOT / "data" / "situation_presets.json"
_USER_SITUATION_PRESETS_PATH = _EXT_ROOT / "data" / "user_situation_presets.json"
_ARTISTS_SEARCH_PATH = _EXT_ROOT / "data" / "anima" / "search.json"
_I18N_JA_PATH = _EXT_ROOT / "i18n" / "ja.json"

# In-memory caches (conceptually constant after first population).
_palette_cache: dict[str, Any] | None = None
_spec_cache: dict[str, Any] | None = None
_character_presets_cache: dict[str, Any] | None = None
_user_character_presets_cache: dict[str, Any] | None = None
_situation_presets_cache: dict[str, Any] | None = None
_user_situation_presets_cache: dict[str, Any] | None = None
_artists_cache: list[dict[str, Any]] | None = None

# Health: lazily-loaded version string cached after first read.
_version_cache: str | None = None

# Locks prevent simultaneous coroutines from double-loading the data files.
_palette_lock: asyncio.Lock = asyncio.Lock()
_spec_lock: asyncio.Lock = asyncio.Lock()
_character_presets_lock: asyncio.Lock = asyncio.Lock()
_user_character_presets_lock: asyncio.Lock = asyncio.Lock()
_situation_presets_lock: asyncio.Lock = asyncio.Lock()
_user_situation_presets_lock: asyncio.Lock = asyncio.Lock()
_artists_lock: asyncio.Lock = asyncio.Lock()

# Identifier validation pattern for user-supplied preset ids.
_PRESET_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

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


def _load_user_character_presets() -> dict[str, Any]:
    """Load data/user_character_presets.json, returning an empty shell on failure.

    Postconditions:
        - Always returns a dict with shape ``{"version": "1.0", "presets": [...]}``.
        - On missing file or parse error, returns ``{"version": "1.0", "presets": []}``.
    """
    if not _USER_CHARACTER_PRESETS_PATH.exists():
        return {"version": "1.0", "presets": []}
    try:
        data = _load_json_file(_USER_CHARACTER_PRESETS_PATH)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "user_character_presets.json parse error, treating as empty: %s", exc
        )
        return {"version": "1.0", "presets": []}
    if not isinstance(data, dict):
        return {"version": "1.0", "presets": []}
    presets = data.get("presets")
    if not isinstance(presets, list):
        presets = []
    return {"version": str(data.get("version", "1.0")), "presets": presets}


def _save_user_character_presets(data: dict[str, Any]) -> None:
    """Atomically write user_character_presets.json.

    Preconditions:
        - ``data`` is a serializable dict with ``presets`` list.
    Postconditions:
        - File is written atomically (temp + replace).
    Raises:
        OSError on filesystem error.
    """
    tmp_path = _USER_CHARACTER_PRESETS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp_path.replace(_USER_CHARACTER_PRESETS_PATH)


def _sanitize_preset_payload(raw: Any) -> dict[str, Any] | None:
    """Validate and normalize a preset dict from the client.

    Returns the sanitized preset dict, or ``None`` if invalid.

    Required fields: id (str matching _PRESET_ID_RE), label (str)
    Optional fields: character, series, essential_general_tags (list[str]),
                     recommended_artists (list[str]), notes, tier (int).
    """
    if not isinstance(raw, dict):
        return None
    pid = raw.get("id")
    if not isinstance(pid, str) or not _PRESET_ID_RE.match(pid):
        return None
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        return None

    def _str(v: Any) -> str:
        return v if isinstance(v, str) else ""

    def _str_list(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [s.strip() for s in v if isinstance(s, str) and s.strip()]

    tier_raw = raw.get("tier", 3)
    try:
        tier = int(tier_raw)
    except (TypeError, ValueError):
        tier = 3
    tier = max(1, min(5, tier))

    return {
        "id": pid,
        "label": label.strip()[:120],
        "character": _str(raw.get("character"))[:512],
        "series": _str(raw.get("series"))[:512],
        "essential_general_tags": _str_list(raw.get("essential_general_tags"))[:64],
        "recommended_artists": _str_list(raw.get("recommended_artists"))[:32],
        "notes": _str(raw.get("notes"))[:1024],
        "tier": tier,
        "user": True,
    }


def _load_user_situation_presets() -> dict[str, Any]:
    """Load data/user_situation_presets.json, returning an empty shell on failure.

    Postconditions:
        - Always returns a dict with shape ``{"version": "1.0", "presets": [...]}``.
        - On missing file or parse error, returns ``{"version": "1.0", "presets": []}``.
    """
    if not _USER_SITUATION_PRESETS_PATH.exists():
        return {"version": "1.0", "presets": []}
    try:
        data = _load_json_file(_USER_SITUATION_PRESETS_PATH)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "user_situation_presets.json parse error, treating as empty: %s", exc
        )
        return {"version": "1.0", "presets": []}
    if not isinstance(data, dict):
        return {"version": "1.0", "presets": []}
    presets = data.get("presets")
    if not isinstance(presets, list):
        presets = []
    return {"version": str(data.get("version", "1.0")), "presets": presets}


def _save_user_situation_presets(data: dict[str, Any]) -> None:
    """Atomically write user_situation_presets.json."""
    tmp_path = _USER_SITUATION_PRESETS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp_path.replace(_USER_SITUATION_PRESETS_PATH)


def _sanitize_situation_payload(raw: Any) -> dict[str, Any] | None:
    """Validate and normalize a situation preset dict from the client.

    Returns the sanitized dict, or ``None`` if invalid.

    Required: id (str matching _PRESET_ID_RE), label (str non-empty).
    Optional: category, count_override, general_tags (list[str]),
              natural_language, notes, tier (int).
    """
    if not isinstance(raw, dict):
        return None
    pid = raw.get("id")
    if not isinstance(pid, str) or not _PRESET_ID_RE.match(pid):
        return None
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        return None

    def _str(v: Any) -> str:
        return v if isinstance(v, str) else ""

    def _str_list(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [s.strip() for s in v if isinstance(s, str) and s.strip()]

    tier_raw = raw.get("tier", 3)
    try:
        tier = int(tier_raw)
    except (TypeError, ValueError):
        tier = 3
    tier = max(1, min(5, tier))

    category = _str(raw.get("category")).strip().lower()[:32]
    if not category:
        category = "custom"

    count_override = _str(raw.get("count_override")).strip()[:128]

    return {
        "id": pid,
        "label": label.strip()[:120],
        "category": category,
        "count_override": count_override if count_override else None,
        "general_tags": _str_list(raw.get("general_tags"))[:64],
        "natural_language": _str(raw.get("natural_language")).strip()[:2048],
        "notes": _str(raw.get("notes"))[:1024],
        "tier": tier,
        "user": True,
    }


def load_artists_index() -> list[dict[str, Any]]:
    """Load search.json and return a trimmed [{t, c}, ...] list for autocomplete.

    Each entry keeps only the fields the suggest UI needs:
        - ``t``: tag string (e.g. ``"@dairi"``) — kept verbatim from search.json.
        - ``c``: post count (int) — used as the popularity rank.

    Preconditions:
        - ``_ARTISTS_SEARCH_PATH`` exists and contains a JSON array.
    Postconditions:
        - Returns a list sorted by ``c`` descending.
        - Entries with empty/missing ``tag`` are dropped.
    Raises:
        FileNotFoundError: if search.json is absent.
        json.JSONDecodeError: if the file is not valid JSON.
    """
    raw = _load_json_file(_ARTISTS_SEARCH_PATH)
    if not isinstance(raw, list):
        raise ValueError("search.json root must be a list")

    trimmed: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        tag = entry.get("tag")
        if not isinstance(tag, str) or not tag:
            continue
        count = entry.get("postCount", 0)
        if not isinstance(count, (int, float)):
            count = 0
        trimmed.append({"t": tag, "c": int(count)})

    trimmed.sort(key=lambda e: e["c"], reverse=True)
    return trimmed


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
        "user_character_presets.json": _file_info(_USER_CHARACTER_PRESETS_PATH, _user_character_presets_cache is not None),
        "situation_presets.json": _file_info(_SITUATION_PRESETS_PATH, _situation_presets_cache is not None),
        "user_situation_presets.json": _file_info(_USER_SITUATION_PRESETS_PATH, _user_situation_presets_cache is not None),
        "anima/search.json": _file_info(_ARTISTS_SEARCH_PATH, _artists_cache is not None),
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
        "/anima_prompt_helper/user_character_presets",
        "/anima_prompt_helper/user_character_presets/{id}",
        "/anima_prompt_helper/situation_presets",
        "/anima_prompt_helper/user_situation_presets",
        "/anima_prompt_helper/user_situation_presets/{id}",
        "/anima_prompt_helper/artists",
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
    """Attach the route handlers to *routes*.

    Preconditions:
        - ``routes`` is an ``aiohttp.web.RouteTableDef``.
    Postconditions:
        - GET routes: palette, spec, character_presets, situation_presets,
          artists, health.
        - POST routes: validate, user_character_presets.
        - DELETE routes: user_character_presets/{preset_id}.
    Invariants:
        - GET handlers are idempotent read-only operations.
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
        """Serve the character presets, merging builtin + user files.

        Builtin presets get ``"user": False``; user presets get ``"user": True``.
        User presets override builtin entries with the same id.

        Returns:
            200 with {"version", "presets": [...]},
            503 if builtin file missing,
            500 on parse error.
        """
        global _character_presets_cache, _user_character_presets_cache
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

        async with _user_character_presets_lock:
            if _user_character_presets_cache is None:
                _user_character_presets_cache = _load_user_character_presets()

        builtin_presets = list(_character_presets_cache.get("presets", []))
        user_presets = list(_user_character_presets_cache.get("presets", []))

        # Tag builtin entries and merge: user presets override by id.
        by_id: dict[str, dict[str, Any]] = {}
        for p in builtin_presets:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                tagged = dict(p)
                tagged.setdefault("user", False)
                by_id[p["id"]] = tagged
        for p in user_presets:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                tagged = dict(p)
                tagged["user"] = True
                by_id[p["id"]] = tagged

        merged = list(by_id.values())
        return web.json_response({
            "version": _character_presets_cache.get("version", "1.0"),
            "presets": merged,
        })

    @routes.post("/anima_prompt_helper/user_character_presets")
    async def post_user_character_preset(request: web.Request) -> web.Response:
        """Create or update a user character preset (upsert by id).

        Request body (JSON, max 32 KB):
            {"preset": {"id": "...", "label": "...", "character": "...", ...}}

        Returns:
            200 with the saved preset (sanitized) on success,
            400 on invalid body, oversized body, or invalid preset.
        """
        global _user_character_presets_cache

        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return web.json_response({"error": "invalid_request"}, status=400)

        try:
            raw_bytes = await request.read()
        except Exception as exc:
            logger.warning("user_character_presets: read failed: %s", exc)
            return web.json_response({"error": "invalid_request"}, status=400)

        if len(raw_bytes) > 32 * 1024:
            return web.json_response({"error": "body_too_large"}, status=400)

        try:
            body = json.loads(raw_bytes)
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)

        if not isinstance(body, dict) or "preset" not in body:
            return web.json_response({"error": "invalid_request"}, status=400)

        sanitized = _sanitize_preset_payload(body["preset"])
        if sanitized is None:
            return web.json_response({"error": "invalid_preset"}, status=400)

        async with _user_character_presets_lock:
            data = _load_user_character_presets()
            presets = data.get("presets", [])
            updated = False
            for i, existing in enumerate(presets):
                if isinstance(existing, dict) and existing.get("id") == sanitized["id"]:
                    presets[i] = sanitized
                    updated = True
                    break
            if not updated:
                presets.append(sanitized)
            data["presets"] = presets

            try:
                _save_user_character_presets(data)
            except OSError as exc:
                logger.error("Failed to save user_character_presets.json: %s", exc)
                return web.json_response({"error": "save_failed"}, status=500)

            _user_character_presets_cache = data

        return web.json_response({"preset": sanitized, "updated": updated})

    @routes.delete("/anima_prompt_helper/user_character_presets/{preset_id}")
    async def delete_user_character_preset(request: web.Request) -> web.Response:
        """Delete a user character preset by id.

        Returns:
            200 on success ({"deleted": true, "id": ...}),
            400 if id is malformed,
            404 if not found.
        """
        global _user_character_presets_cache
        preset_id = request.match_info.get("preset_id", "")
        if not _PRESET_ID_RE.match(preset_id):
            return web.json_response({"error": "invalid_id"}, status=400)

        async with _user_character_presets_lock:
            data = _load_user_character_presets()
            presets = data.get("presets", [])
            new_presets = [
                p for p in presets
                if not (isinstance(p, dict) and p.get("id") == preset_id)
            ]
            if len(new_presets) == len(presets):
                return web.json_response({"error": "not_found"}, status=404)
            data["presets"] = new_presets
            try:
                _save_user_character_presets(data)
            except OSError as exc:
                logger.error("Failed to save user_character_presets.json: %s", exc)
                return web.json_response({"error": "save_failed"}, status=500)
            _user_character_presets_cache = data

        return web.json_response({"deleted": True, "id": preset_id})

    @routes.get("/anima_prompt_helper/situation_presets")
    async def get_situation_presets(request: web.Request) -> web.Response:
        """Serve the situation presets, merging builtin + user files.

        Builtin presets get ``"user": False``; user presets get ``"user": True``.
        User presets override builtin entries with the same id.

        Returns:
            200 with {"version", "presets": [...]},
            503 if builtin file missing,
            500 on parse error.
        """
        global _situation_presets_cache, _user_situation_presets_cache
        async with _situation_presets_lock:
            if _situation_presets_cache is None:
                if not _SITUATION_PRESETS_PATH.exists():
                    logger.warning(
                        "situation_presets.json not found at %s",
                        _SITUATION_PRESETS_PATH,
                    )
                    return web.json_response(
                        {"error": "situation_presets_not_found"}, status=503
                    )
                try:
                    _situation_presets_cache = _load_json_file(_SITUATION_PRESETS_PATH)
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse situation_presets.json: %s", exc)
                    return web.json_response(
                        {"error": "situation_presets_parse_error"}, status=500
                    )

        async with _user_situation_presets_lock:
            if _user_situation_presets_cache is None:
                _user_situation_presets_cache = _load_user_situation_presets()

        builtin_presets = list(_situation_presets_cache.get("presets", []))
        user_presets = list(_user_situation_presets_cache.get("presets", []))

        by_id: dict[str, dict[str, Any]] = {}
        for p in builtin_presets:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                tagged = dict(p)
                tagged.setdefault("user", False)
                by_id[p["id"]] = tagged
        for p in user_presets:
            if isinstance(p, dict) and isinstance(p.get("id"), str):
                tagged = dict(p)
                tagged["user"] = True
                by_id[p["id"]] = tagged

        merged = list(by_id.values())
        return web.json_response({
            "version": _situation_presets_cache.get("version", "1.0"),
            "presets": merged,
        })

    @routes.post("/anima_prompt_helper/user_situation_presets")
    async def post_user_situation_preset(request: web.Request) -> web.Response:
        """Create or update a user situation preset (upsert by id).

        Request body (JSON, max 32 KB):
            {"preset": {"id": "...", "label": "...", "category": "...",
                        "count_override": ..., "general_tags": [...],
                        "natural_language": "...", "notes": "...", "tier": N}}

        Returns:
            200 with the saved preset,
            400 on invalid body / oversized body / invalid preset.
        """
        global _user_situation_presets_cache

        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return web.json_response({"error": "invalid_request"}, status=400)

        try:
            raw_bytes = await request.read()
        except Exception as exc:
            logger.warning("user_situation_presets: read failed: %s", exc)
            return web.json_response({"error": "invalid_request"}, status=400)

        if len(raw_bytes) > 32 * 1024:
            return web.json_response({"error": "body_too_large"}, status=400)

        try:
            body = json.loads(raw_bytes)
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid_json"}, status=400)

        if not isinstance(body, dict) or "preset" not in body:
            return web.json_response({"error": "invalid_request"}, status=400)

        sanitized = _sanitize_situation_payload(body["preset"])
        if sanitized is None:
            return web.json_response({"error": "invalid_preset"}, status=400)

        async with _user_situation_presets_lock:
            data = _load_user_situation_presets()
            presets = data.get("presets", [])
            updated = False
            for i, existing in enumerate(presets):
                if isinstance(existing, dict) and existing.get("id") == sanitized["id"]:
                    presets[i] = sanitized
                    updated = True
                    break
            if not updated:
                presets.append(sanitized)
            data["presets"] = presets

            try:
                _save_user_situation_presets(data)
            except OSError as exc:
                logger.error("Failed to save user_situation_presets.json: %s", exc)
                return web.json_response({"error": "save_failed"}, status=500)

            _user_situation_presets_cache = data

        return web.json_response({"preset": sanitized, "updated": updated})

    @routes.delete("/anima_prompt_helper/user_situation_presets/{preset_id}")
    async def delete_user_situation_preset(request: web.Request) -> web.Response:
        """Delete a user situation preset by id.

        Returns:
            200 on success,
            400 if id malformed,
            404 if not found.
        """
        global _user_situation_presets_cache
        preset_id = request.match_info.get("preset_id", "")
        if not _PRESET_ID_RE.match(preset_id):
            return web.json_response({"error": "invalid_id"}, status=400)

        async with _user_situation_presets_lock:
            data = _load_user_situation_presets()
            presets = data.get("presets", [])
            new_presets = [
                p for p in presets
                if not (isinstance(p, dict) and p.get("id") == preset_id)
            ]
            if len(new_presets) == len(presets):
                return web.json_response({"error": "not_found"}, status=404)
            data["presets"] = new_presets
            try:
                _save_user_situation_presets(data)
            except OSError as exc:
                logger.error("Failed to save user_situation_presets.json: %s", exc)
                return web.json_response({"error": "save_failed"}, status=500)
            _user_situation_presets_cache = data

        return web.json_response({"deleted": True, "id": preset_id})

    @routes.get("/anima_prompt_helper/artists")
    async def get_artists(request: web.Request) -> web.Response:
        """Serve the trimmed artist suggest index for the composer autocomplete.

        Built from ``data/anima/search.json`` on first request and cached in
        memory thereafter. Each entry is ``{"t": "@tag", "c": post_count}``,
        sorted by ``c`` descending so popular artists appear first.

        Returns:
            200 with ``{"version": 1, "entries": [{t, c}, ...]}``,
            503 if search.json is missing,
            500 on parse error.
        """
        global _artists_cache
        async with _artists_lock:
            if _artists_cache is None:
                if not _ARTISTS_SEARCH_PATH.exists():
                    logger.warning(
                        "anima/search.json not found at %s", _ARTISTS_SEARCH_PATH
                    )
                    return web.json_response(
                        {"error": "artists_not_found"}, status=503
                    )
                try:
                    _artists_cache = load_artists_index()
                except json.JSONDecodeError as exc:
                    logger.error("Failed to parse anima/search.json: %s", exc)
                    return web.json_response(
                        {"error": "artists_parse_error"}, status=500
                    )
                except (ValueError, OSError) as exc:
                    logger.error("Failed to load artist index: %s", exc)
                    return web.json_response(
                        {"error": "artists_load_error"}, status=500
                    )
        return web.json_response({"version": 1, "entries": _artists_cache})

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
                    "/anima_prompt_helper/user_character_presets",
                    "/anima_prompt_helper/user_character_presets/{id}",
                    "/anima_prompt_helper/situation_presets",
                    "/anima_prompt_helper/user_situation_presets",
                    "/anima_prompt_helper/user_situation_presets/{id}",
                    "/anima_prompt_helper/artists",
                    "/anima_prompt_helper/validate",
                    "/anima_prompt_helper/health",
                ],
            }
        return web.json_response(payload)

