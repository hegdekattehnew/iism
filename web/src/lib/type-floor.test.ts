import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Nothing in `web/src` sets text below 12 px (Sprint 69, UI-07).
 *
 * The design review measured 296 text nodes under 12 px on `/jobs` alone, all of them the same
 * few badge classes (`text-[11px]`, `text-[10px]`, and the `2xs` step, which was 11 px). A
 * literal pixel size under the floor, or a `2xs` token set below it, fails here. Like
 * `tokens.test.ts`, the point is to catch the next one.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const FLOOR_PX = 12;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return files(full);
    return /\.(tsx?|css)$/.test(entry) && !/\.test\./.test(entry) ? [full] : [];
  });
}

const LITERAL = /text-\[(\d+(?:\.\d+)?)px\]/g;
const REM_LITERAL = /text-\[(\d*\.?\d+)rem\]/g;

describe("type floor", () => {
  it("finds the sources it checks (a checker that read nothing would pass)", () => {
    expect(files(SRC).length).toBeGreaterThan(100);
  });

  it("no class sets text below 12 px", () => {
    const offenders = files(SRC).flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .flatMap((line, i) => {
          const hits = [
            ...[...line.matchAll(LITERAL)].filter((m) => Number(m[1]) < FLOOR_PX),
            ...[...line.matchAll(REM_LITERAL)].filter((m) => Number(m[1]) * 16 < FLOOR_PX),
          ];
          return hits.length ? [`${relative(SRC, file)}:${i + 1}  ${line.trim()}`] : [];
        }),
    );
    expect(offenders).toEqual([]);
  });

  it("the 2xs step is at least 12 px", () => {
    const css = readFileSync(join(SRC, "app", "globals.css"), "utf8");
    const match = css.match(/--text-2xs:\s*([\d.]+)rem/);
    expect(match).not.toBeNull();
    expect(Number(match![1]) * 16).toBeGreaterThanOrEqual(FLOOR_PX);
  });

  it("the detector can fail", () => {
    const sample = '<span className="text-[11px] font-semibold">';
    expect([...sample.matchAll(LITERAL)].filter((m) => Number(m[1]) < FLOOR_PX)).toHaveLength(1);
  });
});
