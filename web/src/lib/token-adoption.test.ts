import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * A page family that has moved onto the design tokens may not go back (Sprint 78, BL-19.9, ADR-087).
 *
 * Sprint 77 made colour, the type scale, radii and shadows tokens in `globals.css`. A token only
 * means something while nothing beside it is chosen by hand, so each family that the revamp
 * migrates is added to `MIGRATED` below and is then held to the scale: a corner from the three radii
 * (or `full`), text from the named steps, a shadow from the three elevations, and **no pixel size in
 * square brackets**. Colour is already held for the whole app by `tokens.test.ts` and the 12 px floor
 * by `type-floor.test.ts`; this is the rest.
 *
 * A family is added in the same change that migrates it (`BL-19.10` onward). Adding one that still
 * breaks a rule fails this test, which names the line: fix the line, not the rule.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

/** Directories under `src/`, relative, whose files are held to the scale. Grows with the revamp. */
export const MIGRATED = ["components/ui"];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return files(full);
    return /\.(tsx?)$/.test(entry) && !/\.test\./.test(entry) ? [full] : [];
  });
}

/** Source with its comments blanked, so prose that names a class is not read as using it. */
export function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " ")).replace(/\/\/.*$/gm, "");
}

const RADII = new Set(["none", "md", "lg", "xl", "full"]);
const TEXT_STEPS = new Set(["2xs", "xs", "sm", "base", "lg", "2xl", "3xl"]);
const SHADOWS = new Set(["none", "soft", "card", "raised"]);

/** The rules, each a name and a function from a line to the classes on it that break it. */
export const RULES: Array<{ name: string; hits: (line: string) => string[] }> = [
  {
    name: "a corner from the radius scale (md, lg, xl, full)",
    hits: (line) =>
      [...line.matchAll(/(?<![\w-])rounded(?:-(?:[trbl]|tl|tr|bl|br|s|e|ss|se|es|ee))?(?:-(\[[^\]]+\]|[a-z0-9]+))?(?![\w-])/g)]
        .filter((m) => m[1] === undefined || !RADII.has(m[1]))
        .map((m) => m[0]),
  },
  {
    name: "text from the named steps (2xs, xs, sm, base, lg, 2xl, 3xl)",
    hits: (line) =>
      [...line.matchAll(/(?<![\w-])text-(\[[^\]]+\]|\d?xl)(?![\w-])/g)]
        .filter((m) => m[1].startsWith("[") || !TEXT_STEPS.has(m[1]))
        .map((m) => m[0]),
  },
  {
    name: "a shadow from the elevations (soft, card, raised)",
    hits: (line) =>
      [...line.matchAll(/(?<![\w-])shadow(?:-([a-z0-9]+|\[[^\]]+\]))?(?![\w-])/g)]
        .filter((m) => m[1] === undefined || !SHADOWS.has(m[1]))
        .map((m) => m[0]),
  },
  {
    name: "no pixel size in square brackets",
    hits: (line) => [...line.matchAll(/(?<![\w-])[a-z-]+-\[-?\d+(?:\.\d+)?px\]/g)].map((m) => m[0]),
  },
];

export function offences(source: string): string[] {
  return code(source)
    .split("\n")
    .flatMap((line, i) =>
      RULES.flatMap((rule) => rule.hits(line).map((hit) => `line ${i + 1}: ${hit}  (wanted: ${rule.name})`)),
    );
}

describe("token adoption in the migrated families", () => {
  it("finds the sources it checks (a checker that read nothing would pass)", () => {
    // An empty list holds no family to the scale and every check below would pass over nothing.
    expect(MIGRATED, "the component library is the first family held to the scale").toContain("components/ui");
    for (const family of MIGRATED) {
      expect(files(join(SRC, family)).length, family).toBeGreaterThan(5);
    }
  });

  it("no migrated file chooses a radius, size or shadow by hand", () => {
    const found = MIGRATED.flatMap((family) =>
      files(join(SRC, family)).flatMap((file) => offences(readFileSync(file, "utf8")).map((o) => `${relative(SRC, file)} ${o}`)),
    );
    expect(found).toEqual([]);
  });

  it("the detector can fail, on each rule", () => {
    expect(offences('<div className="rounded-2xl">')).toHaveLength(1);
    expect(offences('<div className="rounded">')).toHaveLength(1);
    expect(offences('<div className="rounded-t-3xl">')).toHaveLength(1);
    expect(offences('<div className="rounded-[7px]">')).toHaveLength(2); // the corner, and a pixel size
    expect(offences('<p className="text-xl">')).toHaveLength(1);
    expect(offences('<p className="text-[13px]">')).toHaveLength(2);
    expect(offences('<div className="shadow-lg">')).toHaveLength(1);
    expect(offences('<div className="shadow">')).toHaveLength(1);
    expect(offences('<div className="h-[44px]">')).toHaveLength(1);
  });

  it("the detector leaves the scale alone", () => {
    const fine = '<div className="rounded-lg rounded-t-xl rounded-full shadow-card text-sm text-2xl text-muted text-center max-w-[12rem]">';
    expect(offences(fine)).toEqual([]);
  });

  it("a class named in a comment is not a use", () => {
    expect(offences("// use rounded-3xl never\n/* text-[13px] */")).toEqual([]);
  });
});
