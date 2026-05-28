"""__init__.py — ComfyUI extension entry point for anima-prompt-helper.

Exports:
    NODE_CLASS_MAPPINGS       — maps node class names to their Python classes.
    NODE_DISPLAY_NAME_MAPPINGS — maps node class names to human-readable labels.
    WEB_DIRECTORY             — relative path to the frontend JS/CSS assets.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure this extension's directory is on sys.path so sub-packages resolve
# regardless of how the module is loaded (ComfyUI loader, importlib, pytest).
_EXT_ROOT = str(Path(__file__).parent)
if _EXT_ROOT not in sys.path:
    sys.path.insert(0, _EXT_ROOT)

from python.nodes import (
    AnimaPromptComposer,
    AnimaPromptToConditioning,
    AnimaNegativePromptComposer,
    AnimaTagPalette,
    AnimaPromptImporter,
    AnimaArtistRandomizer,
    AnimaCharacterRandomizer,
    AnimaSituationRandomizer,
)

NODE_CLASS_MAPPINGS: dict = {
    "AnimaPromptComposer": AnimaPromptComposer,
    "AnimaPromptToConditioning": AnimaPromptToConditioning,
    "AnimaNegativePromptComposer": AnimaNegativePromptComposer,
    "AnimaTagPalette": AnimaTagPalette,
    "AnimaPromptImporter": AnimaPromptImporter,
    "AnimaArtistRandomizer": AnimaArtistRandomizer,
    "AnimaCharacterRandomizer": AnimaCharacterRandomizer,
    "AnimaSituationRandomizer": AnimaSituationRandomizer,
}

NODE_DISPLAY_NAME_MAPPINGS: dict = {
    "AnimaPromptComposer": "Anima Prompt Composer",
    "AnimaPromptToConditioning": "Anima Prompt -> Conditioning",
    "AnimaNegativePromptComposer": "Anima Negative Prompt Composer",
    "AnimaTagPalette": "Anima Tag Palette",
    "AnimaPromptImporter": "Anima Prompt Importer",
    "AnimaArtistRandomizer": "Anima Artist Randomizer",
    "AnimaCharacterRandomizer": "Anima Character Randomizer",
    "AnimaSituationRandomizer": "Anima Situation Randomizer",
}

WEB_DIRECTORY = "./web"

# Register API routes (side-effect; silently skipped outside ComfyUI).
try:
    import python.api  # noqa: F401
except ImportError:
    pass

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
