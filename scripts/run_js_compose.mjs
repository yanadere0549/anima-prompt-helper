/**
 * run_js_compose.mjs — Node.js harness for JS/Python parity testing.
 *
 * Reads test cases from stdin as JSON-lines OR a single JSON object with a
 * "cases" array.  Each case: { fields, preset }.
 * Writes one JSON line per case: { "output": "<assembled string>" }
 *
 * Usage:
 *   node scripts/run_js_compose.mjs < scripts/parity_cases.json
 */

import { createRequire } from "module";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";
import readline from "readline";

// Resolve extension root relative to this script
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

// Import assemblePreview from the composer module
import { assemblePreview } from "../web/modules/composer.js";

// Load spec once
const specPath = path.join(ROOT, "data", "anima_spec.json");
const spec = JSON.parse(readFileSync(specPath, "utf-8"));

/**
 * The 9 canonical field names in order.
 */
const WIDGET_NAMES = [
  "quality",
  "year",
  "rating",
  "count",
  "character",
  "series",
  "artist",
  "general",
  "natural_language",
];

/**
 * Build a minimal fakeNode that mimics ComfyUI's node.widgets structure.
 * @param {Object} fields - key→value map of field values
 * @param {string} preset  - "none" | "ooo_anima_default" | "custom"
 * @returns {{ widgets: Array<{name: string, value: string}> }}
 */
function buildFakeNode(fields, preset) {
  const widgets = WIDGET_NAMES.map((name) => ({
    name,
    value: typeof fields[name] === "string" ? fields[name] : "",
  }));
  // Add the prefix_preset widget that assemblePreview reads
  widgets.push({ name: "prefix_preset", value: preset || "none" });
  return { widgets };
}

/**
 * Process a single test case and return the assembled string.
 * @param {{ fields: Object, preset: string }} testCase
 * @returns {string}
 */
function processCase(testCase) {
  const { fields, preset } = testCase;
  const fakeNode = buildFakeNode(fields, preset);
  return assemblePreview(fakeNode, spec);
}

// Read all stdin, then process
let stdinData = "";
process.stdin.setEncoding("utf-8");
process.stdin.on("data", (chunk) => { stdinData += chunk; });
process.stdin.on("end", () => {
  const trimmed = stdinData.trim();
  let cases = [];

  // Support both JSON-lines and a single JSON object with "cases" array
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        cases = parsed;
      } else if (parsed.cases && Array.isArray(parsed.cases)) {
        cases = parsed.cases;
      } else {
        // Single object treated as one case
        cases = [parsed];
      }
    } catch (_) {
      // Fall back to JSON-lines parsing below
      const lines = trimmed.split("\n").filter((l) => l.trim().length > 0);
      for (const line of lines) {
        try {
          cases.push(JSON.parse(line));
        } catch (e) {
          process.stderr.write(`[run_js_compose] Failed to parse line: ${line}\n`);
        }
      }
    }
  } else {
    // JSON-lines
    const lines = trimmed.split("\n").filter((l) => l.trim().length > 0);
    for (const line of lines) {
      try {
        cases.push(JSON.parse(line));
      } catch (e) {
        process.stderr.write(`[run_js_compose] Failed to parse line: ${line}\n`);
      }
    }
  }

  for (const testCase of cases) {
    const output = processCase(testCase);
    process.stdout.write(JSON.stringify({ output }) + "\n");
  }
  process.exit(0);
});
