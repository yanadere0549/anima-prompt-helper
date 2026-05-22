/**
 * persist.js — Per-node UI state serialization helpers
 *
 * Hooks node.serialize and node.onConfigure to preserve selectedTab,
 * searchQuery, lastPresetId, favorites, history, and selectedSubcategory
 * across workflow save/load cycles.
 */

const HISTORY_LIMIT = 50;

/**
 * Returns the default animaUiState object.
 * @returns {{selectedTab: null, searchQuery: string, lastPresetId: null, favorites: string[], history: string[], selectedSubcategory: null}}
 */
function _defaultState() {
  return {
    selectedTab: null,
    searchQuery: "",
    lastPresetId: null,
    favorites: [],
    history: [],
    selectedSubcategory: null,
  };
}

/**
 * Attaches persistence hooks to a node.
 * After calling this, node.animaUiState is available for reading/writing
 * the selectedTab, searchQuery, lastPresetId, favorites, history,
 * and selectedSubcategory.
 *
 * @param {Object} node - LiteGraph node instance
 */
export function attachPersistence(node) {
  // Initialize default UI state
  node.animaUiState = _defaultState();

  // Wrap node.serialize
  const origSerialize = node.serialize ? node.serialize.bind(node) : null;
  node.serialize = function () {
    const data = origSerialize ? origSerialize() : {};
    if (!data.properties) data.properties = {};
    data.properties.anima_state = {
      selectedTab: node.animaUiState.selectedTab,
      searchQuery: node.animaUiState.searchQuery,
      lastPresetId: node.animaUiState.lastPresetId || null,
      favorites: (node.animaUiState.favorites || []).slice(),
      history: (node.animaUiState.history || []).slice(),
      selectedSubcategory: node.animaUiState.selectedSubcategory || null,
    };
    return data;
  };

  // Wrap node.onConfigure
  const origOnConfigure = node.onConfigure ? node.onConfigure.bind(node) : null;
  node.onConfigure = function (data) {
    if (origOnConfigure) origOnConfigure(data);
    const saved = data && data.properties && data.properties.anima_state;
    if (saved) {
      node.animaUiState = {
        selectedTab: saved.selectedTab || null,
        searchQuery: saved.searchQuery || "",
        lastPresetId: saved.lastPresetId || null,
        favorites: Array.isArray(saved.favorites) ? saved.favorites.slice() : [],
        history: Array.isArray(saved.history) ? saved.history.slice() : [],
        selectedSubcategory: saved.selectedSubcategory || null,
      };
    }
  };
}

/**
 * Gets the selectedTab from node.animaUiState.
 * @param {Object} node
 * @returns {string|null}
 */
export function getSelectedTab(node) {
  return node.animaUiState ? node.animaUiState.selectedTab : null;
}

/**
 * Sets the selectedTab on node.animaUiState.
 * @param {Object} node
 * @param {string|null} tabId
 */
export function setSelectedTab(node, tabId) {
  if (!node.animaUiState) node.animaUiState = _defaultState();
  node.animaUiState.selectedTab = tabId;
}

/**
 * Gets the searchQuery from node.animaUiState.
 * @param {Object} node
 * @returns {string}
 */
export function getSearchQuery(node) {
  return node.animaUiState ? (node.animaUiState.searchQuery || "") : "";
}

/**
 * Sets the searchQuery on node.animaUiState.
 * @param {Object} node
 * @param {string} query
 */
export function setSearchQuery(node, query) {
  if (!node.animaUiState) node.animaUiState = _defaultState();
  node.animaUiState.searchQuery = query || "";
}

// ---------------------------------------------------------------------------
// Favorites
// ---------------------------------------------------------------------------

/**
 * Returns favorites array for the node (defensive copy).
 * @param {Object} node
 * @returns {string[]}
 */
export function getFavorites(node) {
  if (!node.animaUiState) return [];
  return (node.animaUiState.favorites || []).slice();
}

/**
 * Toggles a tag in favorites. Returns true if added, false if removed.
 *
 * Preconditions:
 *   - tag is a trimmed non-empty string (otherwise no-op, returns false).
 * Postconditions:
 *   - favorites contains tag exactly once after add, or not at all after remove.
 *
 * @param {Object} node
 * @param {string} tag
 * @returns {boolean} true if added, false if removed (or no-op)
 */
export function toggleFavorite(node, tag) {
  const t = (tag || "").trim();
  if (!t) return false;
  if (!node.animaUiState) {
    node.animaUiState = _defaultState();
  }
  const favs = node.animaUiState.favorites || [];
  const idx = favs.findIndex((f) => f.toLowerCase() === t.toLowerCase());
  if (idx >= 0) {
    favs.splice(idx, 1);
    node.animaUiState.favorites = favs;
    return false;
  }
  favs.push(t);
  node.animaUiState.favorites = favs;
  return true;
}

/**
 * Checks if a tag is favorited (case-insensitive).
 * @param {Object} node
 * @param {string} tag
 * @returns {boolean}
 */
export function isFavorite(node, tag) {
  if (!node.animaUiState) return false;
  const t = (tag || "").trim().toLowerCase();
  if (!t) return false;
  return (node.animaUiState.favorites || []).some((f) => f.toLowerCase() === t);
}

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------

/**
 * Returns history array (defensive copy, newest first).
 * @param {Object} node
 * @returns {string[]}
 */
export function getHistory(node) {
  if (!node.animaUiState) return [];
  return (node.animaUiState.history || []).slice();
}

/**
 * Adds a tag to history. If already present, moves it to the front.
 * Trims to HISTORY_LIMIT (50) entries.
 *
 * Preconditions:
 *   - tag is a trimmed non-empty string (otherwise no-op).
 * Postconditions:
 *   - history contains tag exactly once at position [0].
 *   - history length <= HISTORY_LIMIT.
 *
 * @param {Object} node
 * @param {string} tag
 */
export function addToHistory(node, tag) {
  const t = (tag || "").trim();
  if (!t) return;
  if (!node.animaUiState) {
    node.animaUiState = _defaultState();
  }
  let hist = node.animaUiState.history || [];
  // Remove duplicates (case-insensitive)
  hist = hist.filter((h) => h.toLowerCase() !== t.toLowerCase());
  // Prepend
  hist.unshift(t);
  // Trim
  if (hist.length > HISTORY_LIMIT) {
    hist = hist.slice(0, HISTORY_LIMIT);
  }
  node.animaUiState.history = hist;
}

/**
 * Clears the history array.
 * @param {Object} node
 */
export function clearHistory(node) {
  if (!node.animaUiState) return;
  node.animaUiState.history = [];
}

// ---------------------------------------------------------------------------
// selectedSubcategory
// ---------------------------------------------------------------------------

/**
 * Gets the selected subcategory id (or null).
 * @param {Object} node
 * @returns {string|null}
 */
export function getSelectedSubcategory(node) {
  return node.animaUiState ? (node.animaUiState.selectedSubcategory || null) : null;
}

/**
 * Sets the selected subcategory id.
 * @param {Object} node
 * @param {string|null} subcatId
 */
export function setSelectedSubcategory(node, subcatId) {
  if (!node.animaUiState) {
    node.animaUiState = _defaultState();
  }
  node.animaUiState.selectedSubcategory = subcatId || null;
}
