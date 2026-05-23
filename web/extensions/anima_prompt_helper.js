/**
 * anima_prompt_helper.js — ComfyUI extension entry point
 *
 * Loaded automatically by ComfyUI because WEB_DIRECTORY = "./web" and this
 * file lives under web/extensions/.
 *
 * URL prefix: /extensions/anima-prompt-helper/
 */

import { app } from "/scripts/app.js";
import { injectNegativePalettePanel, setNegativeCaches } from "../modules/negative_panel.js";
import { injectTagPalettePanel, setTagPaletteCaches } from "../modules/tag_palette_panel.js";
import { CharacterPresetStore } from "../modules/character_presets.js";
import { SituationPresetStore } from "../modules/situation_presets.js";
import { PrefixPresetStore, attachPrefixPresetUI } from "../modules/prefix_presets.js";
import { setArtistList, attachArtistSuggest } from "../modules/artist_suggest.js";

// --- Inject stylesheet ---
(function injectStyles() {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.type = "text/css";
  link.href = "/extensions/anima-prompt-helper/styles/anima_prompt_helper.css";
  document.head.appendChild(link);
})();

// --- Module-scope caches ---
let paletteCache = null;
let specCache = null;
let characterPresetsCache = null;
let situationPresetsCache = null;
let prefixPresetsCache = null;
let artistsCache = null;

/**
 * Fetch the palette data from the backend.
 * On failure logs a warning and returns null.
 * @returns {Promise<Object|null>}
 */
async function fetchPalette() {
  try {
    const resp = await fetch("/anima_prompt_helper/palette");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] palette fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] palette fetch error:", err);
    return null;
  }
}

/**
 * Fetch the spec data from the backend.
 * On failure logs a warning and returns null.
 * @returns {Promise<Object|null>}
 */
async function fetchSpec() {
  try {
    const resp = await fetch("/anima_prompt_helper/spec");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] spec fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] spec fetch error:", err);
    return null;
  }
}

/**
 * Fetch character presets from the backend.
 * Tries the API endpoint first; falls back to the static file URL on 404.
 * On any failure logs a warning and returns null.
 * @returns {Promise<Object|null>}
 */
async function fetchCharacterPresets() {
  // Primary: API route added by the concurrent backend change
  try {
    const resp = await fetch("/anima_prompt_helper/character_presets");
    if (resp.ok) {
      return await resp.json();
    }
    if (resp.status !== 404) {
      console.warn("[AnimaPromptHelper] character_presets fetch failed:", resp.status);
      return null;
    }
    // 404 — fall through to static file fallback
  } catch (err) {
    console.warn("[AnimaPromptHelper] character_presets fetch error (primary):", err);
    return null;
  }

  // Fallback: static file served via WEB_DIRECTORY
  try {
    const resp = await fetch("/extensions/anima-prompt-helper/data/character_presets.json");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] character_presets fallback fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] character_presets fallback fetch error:", err);
    return null;
  }
}

/**
 * Fetch situation presets from the backend.
 * Tries the API endpoint first; falls back to the static file URL on 404.
 * @returns {Promise<Object|null>}
 */
async function fetchSituationPresets() {
  try {
    const resp = await fetch("/anima_prompt_helper/situation_presets");
    if (resp.ok) {
      return await resp.json();
    }
    if (resp.status !== 404) {
      console.warn("[AnimaPromptHelper] situation_presets fetch failed:", resp.status);
      return null;
    }
  } catch (err) {
    console.warn("[AnimaPromptHelper] situation_presets fetch error (primary):", err);
    return null;
  }
  // Fallback: static file
  try {
    const resp = await fetch("/extensions/anima-prompt-helper/data/situation_presets.json");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] situation_presets fallback fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] situation_presets fallback fetch error:", err);
    return null;
  }
}

/**
 * Fetch prefix presets (builtin + user) from the backend.
 * Returns null on any failure so callers can degrade gracefully.
 *
 * @returns {Promise<Object|null>}
 */
async function fetchPrefixPresets() {
  try {
    const resp = await fetch("/anima_prompt_helper/prefix_presets");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] prefix_presets fetch failed:", resp.status);
      return null;
    }
    return await resp.json();
  } catch (err) {
    console.warn("[AnimaPromptHelper] prefix_presets fetch error:", err);
    return null;
  }
}

/**
 * Fetch the trimmed artist suggest index from the backend.
 * Returns the entries array (not the wrapper object) on success, or null
 * on any failure so callers can degrade gracefully.
 * @returns {Promise<Array<{t: string, c: number}>|null>}
 */
async function fetchArtists() {
  try {
    const resp = await fetch("/anima_prompt_helper/artists");
    if (!resp.ok) {
      console.warn("[AnimaPromptHelper] artists fetch failed:", resp.status);
      return null;
    }
    const data = await resp.json();
    if (data && Array.isArray(data.entries)) {
      return data.entries;
    }
    console.warn("[AnimaPromptHelper] artists payload missing 'entries' array");
    return null;
  } catch (err) {
    console.warn("[AnimaPromptHelper] artists fetch error:", err);
    return null;
  }
}

// --- Register the extension ---
app.registerExtension({
  name: "AnimaPromptHelper",

  /**
   * Called once during ComfyUI startup.
   * Lazily fetches palette and spec; caches them in module scope.
   */
  async setup() {
    [paletteCache, specCache, characterPresetsCache, situationPresetsCache, prefixPresetsCache, artistsCache] = await Promise.all([
      fetchPalette(),
      fetchSpec(),
      fetchCharacterPresets(),
      fetchSituationPresets(),
      fetchPrefixPresets(),
      fetchArtists(),
    ]);
    setNegativeCaches(paletteCache, specCache);
    setTagPaletteCaches(paletteCache, specCache);
    setArtistList(artistsCache);

    if (!paletteCache) {
      console.warn("[AnimaPromptHelper] setup: palette unavailable — palette panel will show error state.");
    }
    if (!specCache) {
      console.warn("[AnimaPromptHelper] setup: spec unavailable — falling back to hardcoded canonical order.");
    }
    if (characterPresetsCache) {
      CharacterPresetStore.init(characterPresetsCache);
    } else {
      console.warn("[AnimaPromptHelper] setup: character presets unavailable — dropdown will show disabled.");
    }
    if (situationPresetsCache) {
      SituationPresetStore.init(situationPresetsCache);
    } else {
      console.warn("[AnimaPromptHelper] setup: situation presets unavailable — dropdown will show disabled.");
    }
    if (prefixPresetsCache) {
      PrefixPresetStore.init(prefixPresetsCache);
    } else {
      console.warn("[AnimaPromptHelper] setup: prefix presets unavailable — editor disabled.");
    }
    if (!artistsCache) {
      console.warn("[AnimaPromptHelper] setup: artist suggest index unavailable — artist autocomplete disabled.");
    } else {
      console.info("[AnimaPromptHelper] artist suggest index loaded:", artistsCache.length, "entries");
    }

    // Fire-and-forget health check — surfaces extension diagnostics in DevTools.
    fetch("/anima_prompt_helper/health")
      .then((r) => r.json())
      .then((data) => console.info("[anima-prompt-helper] health:", data))
      .catch((err) => console.warn("[anima-prompt-helper] health check failed:", err));
  },

  /**
   * Called before each node type is registered.
   * Injects the palette panel into AnimaPromptComposer and
   * the negative palette panel into AnimaNegativePromptComposer nodes.
   */
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === "AnimaPromptComposer") {
      const origOnNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (origOnNodeCreated) {
          origOnNodeCreated.apply(this, arguments);
        }

        const node = this;

        // Attach the prefix-preset edit/new buttons (and combo refresh
        // subscription). This is independent of artistsCache.
        attachPrefixPresetUI(node);

        if (artistsCache !== null) {
          attachArtistSuggest(node);
        } else {
          let attempts = 0;
          const maxAttempts = 30;
          const retryTimer = setInterval(() => {
            attempts++;
            if (artistsCache !== null || attempts >= maxAttempts) {
              clearInterval(retryTimer);
              if (artistsCache !== null) {
                attachArtistSuggest(node);
              }
            }
          }, 100);

          if (!node._aphArtistSetupTimers) node._aphArtistSetupTimers = [];
          node._aphArtistSetupTimers.push(retryTimer);

          const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
          node.onRemoved = function () {
            if (node._aphArtistSetupTimers) {
              node._aphArtistSetupTimers.forEach(clearInterval);
              node._aphArtistSetupTimers = [];
            }
            if (origOnRemoved) origOnRemoved();
          };
        }
      };
    } else if (nodeData.name === "AnimaNegativePromptComposer") {
      const origOnNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (origOnNodeCreated) {
          origOnNodeCreated.apply(this, arguments);
        }

        const node = this;

        if (paletteCache !== null || specCache !== null) {
          injectNegativePalettePanel(node);
        } else {
          let attempts = 0;
          const maxAttempts = 30;
          const retryTimer = setInterval(() => {
            attempts++;
            if (paletteCache !== null || specCache !== null || attempts >= maxAttempts) {
              clearInterval(retryTimer);
              injectNegativePalettePanel(node);
            }
          }, 100);

          if (!node._aphNegSetupTimers) node._aphNegSetupTimers = [];
          node._aphNegSetupTimers.push(retryTimer);

          const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
          node.onRemoved = function () {
            if (node._aphNegSetupTimers) {
              node._aphNegSetupTimers.forEach(clearInterval);
              node._aphNegSetupTimers = [];
            }
            if (origOnRemoved) origOnRemoved();
          };
        }
      };
    } else if (nodeData.name === "AnimaTagPalette") {
      const origOnNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (origOnNodeCreated) {
          origOnNodeCreated.apply(this, arguments);
        }

        const node = this;

        if (paletteCache !== null || specCache !== null) {
          injectTagPalettePanel(node);
        } else {
          let attempts = 0;
          const maxAttempts = 30;
          const retryTimer = setInterval(() => {
            attempts++;
            if (paletteCache !== null || specCache !== null || attempts >= maxAttempts) {
              clearInterval(retryTimer);
              injectTagPalettePanel(node);
            }
          }, 100);

          if (!node._aphTpSetupTimers) node._aphTpSetupTimers = [];
          node._aphTpSetupTimers.push(retryTimer);

          const origOnRemoved = node.onRemoved ? node.onRemoved.bind(node) : null;
          node.onRemoved = function () {
            if (node._aphTpSetupTimers) {
              node._aphTpSetupTimers.forEach(clearInterval);
              node._aphTpSetupTimers = [];
            }
            if (origOnRemoved) origOnRemoved();
          };
        }
      };
    }
  },
});
