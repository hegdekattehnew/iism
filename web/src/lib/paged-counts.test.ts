import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * A list that pages never prints the length of what it has loaded as a total (Sprint 69, UI-06/17).
 *
 * Three lists did: `/jobs` and `/courses` asked for 200 rows and printed their number, and the
 * operator's queue printed its one page of 100 as "100 waiting" beside an overview that said 162.
 * Each looked right on a seeded database and was wrong the moment there was more. A component that
 * reads a paged query takes its count from the server's `total`; `rows.length` may still be used
 * for "is it empty" and for arithmetic (how many are left), which is what these patterns allow.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return files(full);
    return /\.tsx$/.test(entry) && !/\.test\./.test(entry) ? [full] : [];
  });
}

/** `count: rows.length`, `total: rows.length` or `{rows.length}` as text. */
const PRINTS_A_PAGE_AS_A_TOTAL = /\b(?:count|total):\s*rows\.length\b|\{\s*rows\.length\s*\}/;

// A paged list is a component that runs an infinite query itself or reads the pages of a hook that does.
const PAGED = /useInfiniteQuery|hasNextPage|\.pages\b/;
const paged = files(SRC).filter((f) => PAGED.test(readFileSync(f, "utf8")));

describe("paged lists count from the server", () => {
  it("finds the paged lists it checks (a checker that read nothing would pass)", () => {
    const names = paged.map((f) => relative(SRC, f));
    for (const expected of [
      "components/JobBrowser.tsx",
      "components/CourseBrowser.tsx",
      "components/ops/VerificationQueue.tsx",
    ]) {
      expect(names).toContain(expected);
    }
  });

  it("none prints the length of the loaded rows as a count", () => {
    const offenders = paged.flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .flatMap((line, i) =>
          PRINTS_A_PAGE_AS_A_TOTAL.test(line) ? [`${relative(SRC, file)}:${i + 1}  ${line.trim()}`] : [],
        ),
    );
    expect(offenders).toEqual([]);
  });

  it("the detector can fail", () => {
    expect(PRINTS_A_PAGE_AS_A_TOTAL.test('t("resultsCount", { count: rows.length })')).toBe(true);
    expect(PRINTS_A_PAGE_AS_A_TOTAL.test("<p>{rows.length}</p>")).toBe(true);
    expect(PRINTS_A_PAGE_AS_A_TOTAL.test("rows.length === 0")).toBe(false);
    expect(PRINTS_A_PAGE_AS_A_TOTAL.test("const left = total - rows.length")).toBe(false);
  });
});
