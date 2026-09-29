import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * `globals.css` is the only place in `web/src` that may name a colour.
 *
 * `CLAUDE.md` has stated that rule since Sprint 11 and nothing enforced it, so
 * Sprint 26 found it broken **305 times across 38 files** — 35 distinct
 * palette values, each site re-deriving its own light and dark pair by hand.
 * That is not tidiness: it is why success, warning and danger could not be
 * themed at all, and it is exactly how one half of a pair gets missed and a
 * message renders invisible in one theme.
 *
 * This test is what stops the 305 coming back one component at a time. A new
 * tone belongs in `globals.css` as a token; if a genuinely new *kind* of
 * colour is needed, add the token and use it here — do not widen the pattern.
 */

// `fileURLToPath`, not `.pathname`: the latter is not a usable path on
// every platform and resolved to "/src" here.
const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

// Every Tailwind palette family. Deliberately the whole list rather than the
// handful in use: the point is to catch the next one, not the last one.
const FAMILIES = [
  "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
  "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
  "indigo", "violet", "purple", "fuchsia", "pink", "rose",
].join("|");

const PALETTE = new RegExp(
  // Any utility that takes a colour, in any variant (`dark:`, `hover:`, …).
  String.raw`(?:^|\s|"|'|\`)(?:[a-z-]+:)*(?:bg|text|border|ring|outline|divide|from|via|to|decoration|shadow|accent|caret|fill|stroke|placeholder)-(?:${FAMILIES})-\d{2,3}\b`,
);

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return tsxFiles(full);
    return /\.(tsx?|css)$/.test(entry) && entry !== "globals.css" ? [full] : [];
  });
}

describe("colour tokens", () => {
  it("no file outside globals.css names a palette colour", () => {
    const offenders = tsxFiles(SRC)
      .filter((f) => !f.endsWith("tokens.test.ts"))
      .flatMap((file) =>
        readFileSync(file, "utf8")
          .split("\n")
          .flatMap((line, i) =>
            // The Alert primitive's docstring quotes the old class string on
            // purpose, to say what it replaced.
            PALETTE.test(line) && !line.trimStart().startsWith("*")
              ? [`${relative(SRC, file)}:${i + 1}  ${line.trim()}`]
              : [],
          ),
      );

    expect(offenders).toEqual([]);
  });

  it("catches a palette colour when one is added", () => {
    // Without this the test above passes vacuously the day the pattern stops
    // matching anything — a regex that matches nothing looks identical to a
    // codebase that is clean.
    expect(PALETTE.test('className="bg-rose-50 text-rose-800"')).toBe(true);
    expect(PALETTE.test('className="dark:border-emerald-900"')).toBe(true);
    expect(PALETTE.test('className="bg-danger-surface text-danger-text"')).toBe(false);
  });
});
