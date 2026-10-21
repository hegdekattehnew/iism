import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * The marigold highlight is decoration, never a state (Sprint 92, ADR-101).
 *
 * It is the colour the product already uses for a warning (1.07:1 against `--warning-solid`), so a
 * state drawn in it could not be told from a caution, and as text on white it is 2:1. The rule is
 * held two ways: the status components may not mention it at all, and the only files that may use
 * it are named here, so a new use is a decision made in a diff to this list.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const ROOT = dirname(dirname(SRC));

function files(dir: string, accept: RegExp): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (entry === "node_modules" || entry.startsWith(".next")) return [];
    if (statSync(full).isDirectory()) return files(full, accept);
    return accept.test(entry) && !/\.test\./.test(entry) ? [full] : [];
  });
}

/** `highlight` as a token or a class (`bg-highlight`, `--highlight`, `highlightTint`), not the word in a comment's prose. */
const USES = /(?:^|[^A-Za-z])(?:bg-|text-|border-|fill-|ring-|var\(--|--)highlight|\bhighlight(?:On|Tint|Text)\b/;

const ALLOWED = new Set([
  "web/src/components/ui/layout.tsx", // the logo's one warm node
  "web/src/components/Hero.tsx", // the mark beside the reassurance
]);

describe("the highlight", () => {
  const sources = [
    ...files(join(SRC), /\.(tsx?|css)$/),
    ...files(join(ROOT, "mobile", "src"), /\.(tsx?)$/),
  ];

  it("finds the sources it checks (a checker that read nothing would pass)", () => {
    expect(sources.length).toBeGreaterThan(200);
  });

  it("is used only where it has been decided", () => {
    const users = sources
      .filter((f) => !f.endsWith("globals.css") && !f.endsWith("tokens.ts"))
      .filter((f) => USES.test(readFileSync(f, "utf8")))
      .map((f) => relative(ROOT, f));
    expect(users.sort()).toEqual([...ALLOWED].sort());
  });

  it("is in no status component, look table or notice, on the web or the phone", () => {
    const status = sources.filter((f) =>
      /(status-chip|badge|alert|-look)\.tsx?$|mobile\/src\/ui\/(primitives|notice|badge)/.test(f),
    );
    expect(status.length).toBeGreaterThanOrEqual(8);
    for (const f of status) expect(USES.test(readFileSync(f, "utf8")), relative(ROOT, f)).toBe(false);
  });

  it("the matcher can fail", () => {
    expect(USES.test('<span className="bg-highlight text-highlight-on">')).toBe(true);
    expect(USES.test("fill: var(--highlight)")).toBe(true);
    expect(USES.test("colours.highlightTint")).toBe(true);
    expect(USES.test("the highlighted row")).toBe(false);
  });
});
