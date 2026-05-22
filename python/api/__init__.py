"""python/api/__init__.py — registers aiohttp routes on PromptServer.

Side-effect import: attaches the five /anima_prompt_helper/* routes to
``PromptServer.instance.routes`` when ComfyUI's server is running.

When imported outside ComfyUI (e.g. during unit tests), the
``ImportError`` from ``server`` is caught gracefully and routes are not
registered.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from server import PromptServer  # type: ignore[import]
    from .routes import register

    register(PromptServer.instance.routes)
    logger.info("anima-prompt-helper: API routes registered successfully.")
except ImportError:
    logger.debug(
        "anima-prompt-helper: server module not available "
        "(likely running outside ComfyUI). API routes not registered."
    )
