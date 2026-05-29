/**
 * test_randomizer_recompute.mjs — regression tests for the shared queue-time
 * recompute decision used by the artist / character / situation randomizer
 * panels.
 *
 * Run: node tests/test_randomizer_recompute.mjs
 *
 * Guards the bug where control_after_generate advanced the seed but the panel
 * skipped recompute (pool fingerprint unchanged), freezing the picks until
 * 再シャッフル was pressed.
 */
import {
  shouldRecomputePicked,
  recordPickedState,
} from "../web/modules/randomizer_recompute.js";

let passed = 0;
let failed = 0;

function assert(cond, msg) {
  if (cond) {
    passed += 1;
  } else {
    failed += 1;
    console.error(`  ✗ FAIL: ${msg}`);
  }
}

// A fingerprint stands in for a pool; we just need stable strings here.
const FP_A = "poolA";
const FP_B = "poolB";

// --- 1. Fresh node (no recorded picks) must compute --------------------------
{
  const node = {};
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: false, fingerprint: FP_A, seed: 0, count: 1,
  });
  assert(recompute === true, "fresh node with empty picked recomputes");
}

// --- 2. Right after a recompute, an unchanged re-queue skips ------------------
{
  const node = {};
  // simulate the first populate: empty → recompute → record
  shouldRecomputePicked(node, { force: false, hasPicked: false, fingerprint: FP_A, seed: 5, count: 2 });
  recordPickedState(node, { fingerprint: FP_A, seed: 5, count: 2 });
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 5, count: 2,
  });
  assert(recompute === false, "unchanged pool/seed/count skips (fixed seed)");
}

// --- 3. control_after_generate advanced the seed → must recompute ------------
{
  const node = {};
  recordPickedState(node, { fingerprint: FP_A, seed: 5, count: 2 });
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 6, count: 2,
  });
  assert(recompute === true, "advanced seed recomputes (THE reported bug)");
}

// --- 4. PNG reload: tracking undefined + picked present → trust & skip --------
{
  const node = {}; // __animaLast* all undefined, as on a fresh page load
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 42, count: 3,
  });
  assert(recompute === false, "PNG-restored picks are trusted on first queue");
  assert(node.__animaLastPoolFingerprint === FP_A, "first-sight seeds fingerprint");
  assert(node.__animaLastSeed === 42, "first-sight seeds seed");
  assert(node.__animaLastCount === 3, "first-sight seeds count");
}

// --- 5. After PNG reload, the NEXT queue (seed advanced) recomputes -----------
{
  const node = {};
  shouldRecomputePicked(node, { force: false, hasPicked: true, fingerprint: FP_A, seed: 42, count: 3 });
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 43, count: 3,
  });
  assert(recompute === true, "PNG reload then advanced seed recomputes");
}

// --- 6. Pool changed (same seed) → recompute ---------------------------------
{
  const node = {};
  recordPickedState(node, { fingerprint: FP_A, seed: 7, count: 1 });
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_B, seed: 7, count: 1,
  });
  assert(recompute === true, "changed pool recomputes");
}

// --- 7. Count changed (same seed/pool) → recompute ---------------------------
{
  const node = {};
  recordPickedState(node, { fingerprint: FP_A, seed: 7, count: 1 });
  const recompute = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 7, count: 4,
  });
  assert(recompute === true, "changed count recomputes");
}

// --- 8. force bypasses the skip even when nothing changed --------------------
{
  const node = {};
  recordPickedState(node, { fingerprint: FP_A, seed: 7, count: 1 });
  const recompute = shouldRecomputePicked(node, {
    force: true, hasPicked: true, fingerprint: FP_A, seed: 7, count: 1,
  });
  assert(recompute === true, "force always recomputes (再シャッフル/強制)");
}

// --- 9. Batch of N iterations with advancing seed: every iteration recomputes -
{
  const node = {};
  let recomputes = 0;
  let seed = 100;
  for (let i = 0; i < 4; i++) {
    const hasPicked = i > 0; // first iteration starts empty
    if (shouldRecomputePicked(node, { force: false, hasPicked, fingerprint: FP_A, seed, count: 1 })) {
      recomputes += 1;
      recordPickedState(node, { fingerprint: FP_A, seed, count: 1 });
    }
    seed += 1; // control_after_generate advances seed before next graphToPrompt
  }
  assert(recomputes === 4, `batch of 4 advancing-seed iterations all recompute (got ${recomputes})`);
}

// --- 10. Shuffle preview honored on immediate next queue, then randomize -----
{
  const node = {};
  // shuffle: sets a new seed, records state with it
  recordPickedState(node, { fingerprint: FP_A, seed: 999, count: 2 });
  // immediate next queue, seed not yet advanced (shuffle does not queue)
  const skipShuffled = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 999, count: 2,
  });
  assert(skipShuffled === false, "shuffled picks honored on the immediate next queue");
  // then control_after_generate advances → recompute
  const afterAdvance = shouldRecomputePicked(node, {
    force: false, hasPicked: true, fingerprint: FP_A, seed: 1000, count: 2,
  });
  assert(afterAdvance === true, "after the queue, randomize takes over again");
}

console.log(`\nrandomizer_recompute: ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
