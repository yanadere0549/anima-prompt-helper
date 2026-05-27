"""metadata_extractor.py — extract embedded prompt metadata from generated images.

Supports:
    - PNG iTXt/tEXt/zTXt chunks (ComfyUI ``workflow``/``prompt`` JSON, A1111
      ``parameters`` text, NovelAI ``Comment``).
    - JPEG EXIF UserComment / Software (best-effort A1111 export).

The public entry point is :func:`extract_metadata`, which accepts raw image
bytes and returns a dict describing the embedded prompt(s).
"""
from __future__ import annotations

import json
import logging
import re
import struct
import zlib
from typing import Any

logger = logging.getLogger(__name__)

# PNG file signature (8 bytes).
_PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Low-level PNG chunk parsing
# ---------------------------------------------------------------------------


def _iter_png_chunks(data: bytes):
    """Yield ``(chunk_type, chunk_payload)`` tuples from PNG ``data``.

    Stops at IEND or when the buffer is exhausted. Malformed chunks are skipped
    silently — the goal is best-effort metadata recovery, not strict validation.

    Preconditions:
        - ``data`` starts with the PNG signature.
    Postconditions:
        - Yields decoded chunk payloads in file order.
    """
    if not data.startswith(_PNG_SIGNATURE):
        return
    offset = len(_PNG_SIGNATURE)
    n = len(data)
    while offset + 8 <= n:
        try:
            length = struct.unpack_from(">I", data, offset)[0]
        except struct.error:
            return
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        if payload_end + 4 > n:
            return
        payload = data[payload_start:payload_end]
        yield chunk_type, payload
        if chunk_type == b"IEND":
            return
        # skip 4-byte CRC
        offset = payload_end + 4


def _decode_text_chunk(chunk_type: bytes, payload: bytes) -> tuple[str, str] | None:
    """Decode a PNG text chunk into ``(keyword, text)``.

    Supports tEXt, zTXt, and iTXt. Returns ``None`` if decoding fails.
    """
    try:
        if chunk_type == b"tEXt":
            # keyword\x00text
            null = payload.index(b"\x00")
            keyword = payload[:null].decode("latin-1", errors="replace")
            text = payload[null + 1 :].decode("utf-8", errors="replace")
            return keyword, text
        if chunk_type == b"zTXt":
            # keyword\x00compression_method + compressed_text
            null = payload.index(b"\x00")
            keyword = payload[:null].decode("latin-1", errors="replace")
            # payload[null + 1] is the compression method (0 = zlib)
            compressed = payload[null + 2 :]
            text = zlib.decompress(compressed).decode("utf-8", errors="replace")
            return keyword, text
        if chunk_type == b"iTXt":
            # keyword\x00 compflag compmethod lang\x00 transkey\x00 text
            null1 = payload.index(b"\x00")
            keyword = payload[:null1].decode("utf-8", errors="replace")
            comp_flag = payload[null1 + 1]
            # comp_method = payload[null1 + 2]
            rest = payload[null1 + 3 :]
            null2 = rest.index(b"\x00")  # language tag terminator
            rest = rest[null2 + 1 :]
            null3 = rest.index(b"\x00")  # translated keyword terminator
            text_bytes = rest[null3 + 1 :]
            if comp_flag == 1:
                text_bytes = zlib.decompress(text_bytes)
            text = text_bytes.decode("utf-8", errors="replace")
            return keyword, text
    except (ValueError, zlib.error, IndexError) as exc:
        logger.debug("PNG text chunk decode error (%s): %s", chunk_type, exc)
        return None
    return None


# ---------------------------------------------------------------------------
# Format-specific extractors
# ---------------------------------------------------------------------------


# ComfyUI text-encode node class names whose ``text`` widget holds prompts.
# We collect them all and let the classifier sort them later.
_COMFYUI_TEXT_NODE_CLASSES: set[str] = {
    "CLIPTextEncode",
    "CLIPTextEncodeSDXL",
    "CLIPTextEncodeSDXLRefiner",
    "BNK_CLIPTextEncodeAdvanced",
    "smZ CLIPTextEncode",
    "AnimaPromptComposer",
}


# Heuristic markers in widget values that suggest a negative-prompt slot.
# Used as a fallback when the prompt JSON does not link nodes by purpose.
_NEGATIVE_HINTS: tuple[str, ...] = (
    "worst quality",
    "low quality",
    "lowres",
    "bad anatomy",
    "bad hands",
    "score_1",
    "score_2",
    "score_3",
    "artist name",
    "watermark",
)


def _looks_negative(text: str) -> bool:
    """Heuristic: does ``text`` look like a negative prompt?"""
    t = text.lower()
    return any(h in t for h in _NEGATIVE_HINTS)


def _extract_from_comfyui_prompt(prompt_json: dict) -> dict[str, Any] | None:
    """Pull positive / negative prompts from a ComfyUI ``prompt`` chunk.

    The ``prompt`` chunk shape is ``{"node_id": {"class_type": ..., "inputs":
    {...}}}``. We prefer ``AnimaPromptComposer`` (assembling its 9 fields) when
    present; otherwise we fall back to collecting all text widgets and using
    the negative-hint heuristic to split positive vs negative.

    Returns ``None`` if no text could be extracted.
    """
    if not isinstance(prompt_json, dict):
        return None

    # First pass — Anima composer wins if present.
    anima_positive: str | None = None
    anima_negative: str | None = None
    anima_fields: dict[str, str] | None = None
    text_widgets: list[str] = []
    # Artist tags chosen by AnimaArtistRandomizer nodes. The composer's
    # ``artist`` field is usually a link to the randomizer output (so it is not
    # a literal string here); the actual artists live in the randomizer's
    # ``picked`` widget, which it records into the image metadata at queue time.
    randomizer_picked: list[str] = []

    for node in prompt_json.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        if class_type == "AnimaPromptComposer":
            parts: list[str] = []
            fields_out: dict[str, str] = {}
            for fname in (
                "quality",
                "year",
                "rating",
                "count",
                "character",
                "series",
                "artist",
                "general",
            ):
                v = inputs.get(fname)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                    fields_out[fname] = v.strip()
            nl = inputs.get("natural_language")
            joined = ", ".join(parts)
            if isinstance(nl, str) and nl.strip():
                fields_out["natural_language"] = nl.strip()
                joined = (joined + ". " + nl.strip()) if joined else nl.strip()
            if joined:
                anima_positive = joined
            if fields_out:
                anima_fields = fields_out
        elif class_type == "AnimaNegativePromptComposer":
            parts: list[str] = []
            for fname in (
                "quality_negative",
                "score_negative",
                "style_negative",
                "content_negative",
                "meta_negative",
                "extra_negative",
            ):
                v = inputs.get(fname)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
            if parts:
                anima_negative = ", ".join(parts)
        elif class_type == "AnimaArtistRandomizer":
            picked = inputs.get("picked")
            if isinstance(picked, str) and picked.strip():
                randomizer_picked.append(picked.strip())
        elif class_type in _COMFYUI_TEXT_NODE_CLASSES:
            t = inputs.get("text") or inputs.get("text_g") or inputs.get("text_l")
            if isinstance(t, str) and t.strip():
                text_widgets.append(t.strip())
        else:
            # Other nodes may still have a ``text`` widget worth scraping.
            t = inputs.get("text")
            if isinstance(t, str) and t.strip() and ("," in t or len(t) > 24):
                text_widgets.append(t.strip())

    # Merge artists chosen by any AnimaArtistRandomizer into the artist field
    # (and the positive text), de-duplicated case-insensitively. The composer's
    # own artist link contributes nothing here, so this is what surfaces the
    # randomized artists in the importer's "Artist / 絵師" bucket.
    if randomizer_picked:
        existing_artist = (anima_fields or {}).get("artist", "")
        merged: list[str] = []
        seen: set[str] = set()
        for source in ([existing_artist] if existing_artist else []) + randomizer_picked:
            for tok in source.split(","):
                t = tok.strip()
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    merged.append(t)
        if merged:
            artist_str = ", ".join(merged)
            if anima_fields is None:
                anima_fields = {}
            anima_fields["artist"] = artist_str
            if anima_positive:
                anima_positive = anima_positive + ", " + artist_str
            else:
                anima_positive = artist_str

    positive = anima_positive
    negative = anima_negative

    if positive is None or negative is None:
        # Sort scraped widgets into positive / negative buckets using hints.
        # Keep the first non-negative text as positive; first negative-looking
        # text as negative.
        for t in text_widgets:
            if _looks_negative(t):
                if negative is None:
                    negative = t
            else:
                if positive is None:
                    positive = t

    if positive is None and negative is None:
        return None

    result: dict[str, Any] = {
        "format": "comfyui",
        "positive": positive or "",
        "negative": negative or "",
    }
    if anima_fields:
        result["anima_fields"] = anima_fields
    return result


# A1111 parameters block layout:
#   <positive>\nNegative prompt: <negative>\nSteps: N, Sampler: ..., ...
# Steps line is optional (NovelAI's "Description" block lacks it); we split on
# the first occurrence of "Negative prompt:" only.
_A1111_NEG_RE = re.compile(r"\nNegative prompt:\s*", re.IGNORECASE)
_A1111_PARAMS_RE = re.compile(
    r"\n(?:Steps|Sampler|Seed|CFG scale|Model|Schedule type|Size):\s",
    re.IGNORECASE,
)


def _extract_from_a1111_parameters(text: str) -> dict[str, Any]:
    """Parse an A1111 ``parameters`` text blob into positive/negative."""
    positive = text
    negative = ""
    m = _A1111_NEG_RE.search(text)
    if m:
        positive = text[: m.start()]
        rest = text[m.end() :]
        # Trim the trailing settings block (Steps: ...).
        pm = _A1111_PARAMS_RE.search(rest)
        if pm:
            negative = rest[: pm.start()]
        else:
            negative = rest
    else:
        # No Negative prompt line — try to trim the settings block off positive.
        pm = _A1111_PARAMS_RE.search(text)
        if pm:
            positive = text[: pm.start()]
    return {
        "format": "a1111",
        "positive": positive.strip(),
        "negative": negative.strip(),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_metadata(image_bytes: bytes) -> dict[str, Any]:
    """Extract embedded prompt metadata from ``image_bytes``.

    Preconditions:
        - ``image_bytes`` is the raw file content of an image.
    Postconditions:
        - Returns a dict with keys: ``format`` (str), ``positive`` (str),
          ``negative`` (str), ``raw_chunks`` (dict[str, str] — for debugging).
        - If no metadata is found, ``format`` is ``"unknown"`` and both
          prompts are ``""``.

    Never raises — best-effort recovery from arbitrary bytes.
    """
    raw_chunks: dict[str, str] = {}

    if image_bytes.startswith(_PNG_SIGNATURE):
        for chunk_type, payload in _iter_png_chunks(image_bytes):
            if chunk_type not in (b"tEXt", b"zTXt", b"iTXt"):
                continue
            decoded = _decode_text_chunk(chunk_type, payload)
            if not decoded:
                continue
            keyword, text = decoded
            # Keep only the first occurrence per keyword to avoid clobbering.
            raw_chunks.setdefault(keyword, text)

        # Priority 1 — ComfyUI ``prompt`` chunk (full graph).
        if "prompt" in raw_chunks:
            try:
                parsed = json.loads(raw_chunks["prompt"])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                result = _extract_from_comfyui_prompt(parsed)
                if result:
                    result["raw_chunks"] = raw_chunks
                    return result

        # Priority 2 — ComfyUI ``workflow`` chunk (UI graph; less reliable).
        if "workflow" in raw_chunks:
            try:
                wf = json.loads(raw_chunks["workflow"])
            except json.JSONDecodeError:
                wf = None
            if isinstance(wf, dict) and isinstance(wf.get("nodes"), list):
                # Reshape into a ``prompt``-like dict so the same extractor can
                # consume both. Workflow nodes carry widget_values as a list
                # whose order matches the node's input order; we walk that
                # list cautiously and only pull str values.
                pseudo: dict[str, dict[str, Any]] = {}
                for node in wf["nodes"]:
                    if not isinstance(node, dict):
                        continue
                    nid = node.get("id")
                    ctype = node.get("type")
                    wvals = node.get("widgets_values")
                    if nid is None or not isinstance(ctype, str):
                        continue
                    inputs: dict[str, Any] = {}
                    if ctype == "AnimaPromptComposer" and isinstance(wvals, list):
                        # widget order: quality, year, rating, count, character,
                        # series, artist, general, natural_language,
                        # prefix_preset, [lora_trigger_words]
                        names = [
                            "quality",
                            "year",
                            "rating",
                            "count",
                            "character",
                            "series",
                            "artist",
                            "general",
                            "natural_language",
                        ]
                        for i, name in enumerate(names):
                            if i < len(wvals) and isinstance(wvals[i], str):
                                inputs[name] = wvals[i]
                    elif ctype == "AnimaNegativePromptComposer" and isinstance(wvals, list):
                        names = [
                            "quality_negative",
                            "score_negative",
                            "style_negative",
                            "content_negative",
                            "meta_negative",
                            "extra_negative",
                        ]
                        for i, name in enumerate(names):
                            if i < len(wvals) and isinstance(wvals[i], str):
                                inputs[name] = wvals[i]
                    elif ctype == "AnimaArtistRandomizer" and isinstance(wvals, list):
                        # widget order: count, seed, control_after_generate,
                        # pool, picked. picked (index 4) holds the artists
                        # chosen for the run; pool (index 3) is the full pool.
                        if len(wvals) >= 5 and isinstance(wvals[4], str):
                            inputs["picked"] = wvals[4]
                    elif ctype in _COMFYUI_TEXT_NODE_CLASSES and isinstance(wvals, list):
                        # First string widget is the prompt text.
                        for v in wvals:
                            if isinstance(v, str) and v.strip():
                                inputs["text"] = v
                                break
                    pseudo[str(nid)] = {"class_type": ctype, "inputs": inputs}
                if pseudo:
                    result = _extract_from_comfyui_prompt(pseudo)
                    if result:
                        result["format"] = "comfyui_workflow"
                        result["raw_chunks"] = raw_chunks
                        return result

        # Priority 3 — A1111 ``parameters``.
        if "parameters" in raw_chunks:
            result = _extract_from_a1111_parameters(raw_chunks["parameters"])
            result["raw_chunks"] = raw_chunks
            return result

        # Priority 4 — NovelAI ``Comment`` (JSON with "prompt"/"uc" keys).
        if "Comment" in raw_chunks:
            try:
                nai = json.loads(raw_chunks["Comment"])
            except json.JSONDecodeError:
                nai = None
            if isinstance(nai, dict):
                return {
                    "format": "novelai",
                    "positive": str(nai.get("prompt") or "").strip(),
                    "negative": str(nai.get("uc") or "").strip(),
                    "raw_chunks": raw_chunks,
                }

    # JPEG / WebP / unknown — best-effort scan for embedded text.
    # We do NOT pull a JPEG decoder dependency; just search the bytes for the
    # A1111 "Negative prompt:" signature, which is shipped UTF-8 in EXIF
    # UserComment with the 8-byte "UNICODE\x00" preamble.
    if b"parameters" in image_bytes[:65536] or b"Negative prompt:" in image_bytes[:65536]:
        # Try to recover a UTF-16-LE block (EXIF UserComment Unicode encoding)
        try:
            idx = image_bytes.find(b"UNICODE\x00")
            if idx >= 0:
                snippet = image_bytes[idx + 8 : idx + 8 + 8192]
                try:
                    text = snippet.decode("utf-16-le", errors="replace")
                except UnicodeDecodeError:
                    text = ""
                if "Negative prompt:" in text or "Steps:" in text:
                    result = _extract_from_a1111_parameters(text)
                    result["raw_chunks"] = {"parameters": text}
                    return result
        except Exception as exc:  # pragma: no cover — defensive
            logger.debug("JPEG EXIF scan failed: %s", exc)

    return {
        "format": "unknown",
        "positive": "",
        "negative": "",
        "raw_chunks": raw_chunks,
    }
