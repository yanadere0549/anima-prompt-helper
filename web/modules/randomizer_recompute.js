/**
 * randomizer_recompute.js — shared queue-time recompute decision for the
 * Anima *Randomizer panels (artist / character / situation).
 *
 * All three panels write their seed-determined ``picked`` selection into a
 * serialized widget at queue time (via the ``graphToPrompt`` hook). The
 * decision of *whether* to recompute that selection is identical across the
 * three and lives here so it stays consistent and unit-testable without a DOM.
 *
 * A node is SKIPPED (its recorded picks preserved) only when every one of
 * these holds:
 *   - ``force`` is false, and
 *   - it already has a non-empty ``picked`` value, and
 *   - its pool, seed and count are all unchanged since the last populate.
 *
 * The per-node tracking state is stored on three expando properties:
 *   ``node.__animaLastPoolFingerprint``, ``node.__animaLastSeed``,
 *   ``node.__animaLastCount``.
 *
 * The crucial case this fixes: when ``control_after_generate`` advances the
 * ``seed`` between queues, the pool fingerprint is unchanged but the seed is
 * not — so the node MUST recompute. Tracking only the fingerprint (the old
 * behaviour) wrongly skipped, freezing the picks until 再シャッフル was pressed.
 */

/**
 * Decide whether a randomizer node's ``picked`` widget must be recomputed at
 * queue time. On the first sight of a node that already carries a non-empty
 * ``picked`` (tracking state undefined — e.g. a workflow restored from a PNG)
 * its picks are trusted and the tracking state is seeded from the current
 * pool/seed/count, so the *next* queue (after ``control_after_generate``
 * advances the seed) recomputes.
 *
 * @param {Object} node - LiteGraph node (only the __animaLast* expandos are touched)
 * @param {Object} state
 * @param {boolean} state.force       - bypass skip logic entirely
 * @param {boolean} state.hasPicked   - whether ``picked`` currently holds a value
 * @param {string}  state.fingerprint - order-independent pool fingerprint
 * @param {number}  state.seed        - current seed widget value
 * @param {number}  state.count       - current count widget value
 * @returns {boolean} true → caller must recompute picked; false → skip (preserve)
 */
export function shouldRecomputePicked(
  node,
  { force = false, hasPicked, fingerprint, seed, count } = {}
) {
  if (force) return true;
  if (!hasPicked) return true; // nothing recorded yet → must compute

  if (node.__animaLastPoolFingerprint === undefined) {
    // 初回 (PNG 復元など): 既存 picked を信頼し、追跡状態だけ初期化して skip。
    // 次回 queue 以降は seed / count / pool の変化で再計算される。
    node.__animaLastPoolFingerprint = fingerprint;
    node.__animaLastSeed = seed;
    node.__animaLastCount = count;
    return false;
  }

  if (
    node.__animaLastPoolFingerprint === fingerprint &&
    node.__animaLastSeed === seed &&
    node.__animaLastCount === count
  ) {
    return false; // pool / seed / count いずれも変更なし → skip
  }
  return true;
}

/**
 * Record the pool/seed/count that produced the node's current ``picked``
 * value. Call right after writing a fresh selection (populate or 再シャッフル)
 * so the next queue's skip check compares against the correct baseline.
 *
 * @param {Object} node
 * @param {Object} state
 * @param {string} state.fingerprint
 * @param {number} state.seed
 * @param {number} state.count
 */
export function recordPickedState(node, { fingerprint, seed, count } = {}) {
  node.__animaLastPoolFingerprint = fingerprint;
  node.__animaLastSeed = seed;
  node.__animaLastCount = count;
}
