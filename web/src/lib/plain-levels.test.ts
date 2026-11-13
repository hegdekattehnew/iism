import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import hi from "@/messages/hi.json";
import ms from "@/messages/ms.json";

/**
 * Plain levels on the seeker's pages (Sprint 104, BL-22.5).
 *
 * A job seeker reading a vacancy, a course, a standard or a match is not told the framework's name:
 * the level is said in words with its number beside it (`levels.*`). The framework's name belongs on
 * About, the back office and the employer's and provider's own forms, which are not covered here.
 * Two things a render test cannot say: the words in the catalogue never name it, and the pages'
 * source does not write it in a string (the search page once built `NSQF 4` by hand, in English
 * only, beneath a catalogue that had no such key).
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (p: string) => readFileSync(join(SRC, p), "utf8");

const NAMES_THE_FRAMEWORK = /NSQF/;

/** Message keys a job seeker reads beside a level, in every language. */
const SEEKER_LEVEL_KEYS: [string, string][] = [
  ["levels", "name.l4"],
  ["matchViz", "levelHeading"],
  ["matchViz", "levelLabel"],
  ["matchViz", "levelMet"],
  ["matchViz", "levelShort"],
  ["skillsPage", "levelShort"],
  ["skillsPage", "levelWithCount"],
  ["coursesPage", "teachesToLevel"],
];

type Tree = { [key: string]: string | Tree };
function lookup(messages: unknown, ns: string, key: string): string {
  const root = (messages as Tree)[ns] as Tree;
  const found = key.split(".").reduce<string | Tree | undefined>((t, k) => (t as Tree | undefined)?.[k], root);
  if (typeof found !== "string") throw new Error(`missing ${ns}.${key}`);
  return found;
}
function everyString(tree: Tree): string[] {
  return Object.values(tree).flatMap((v) => (typeof v === "string" ? [v] : everyString(v)));
}

/** The pages and cards where a job seeker reads a level. */
const SEEKER_SOURCES = [
  "app/[locale]/jobs/[slug]/page.tsx",
  "app/[locale]/courses/[slug]/page.tsx",
  "app/[locale]/skills/[slug]/page.tsx",
  "components/cards/CourseCard.tsx",
  "components/cards/StandardCard.tsx",
  "components/SearchResults.tsx",
  "components/CareerLadder.tsx",
  "components/profile/RolePicker.tsx",
];

const withoutComments = (code: string) =>
  code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

describe("a level is said in plain words on the seeker's pages", () => {
  for (const [name, messages] of [
    ["en", en],
    ["hi", hi],
    ["ms", ms],
  ] as const) {
    it(`${name}: the words for a level never name the framework`, () => {
      for (const [ns, key] of SEEKER_LEVEL_KEYS) {
        expect(lookup(messages, ns, key), `${ns}.${key}`).not.toMatch(NAMES_THE_FRAMEWORK);
      }
      const all = everyString((messages as unknown as { levels: Tree }).levels);
      expect(all.length).toBeGreaterThanOrEqual(23); // ten names, ten lines and three joins
      expect(all.filter((s) => NAMES_THE_FRAMEWORK.test(s))).toEqual([]);
    });
  }

  it("the pages' source does not write the framework's name in code or a string", () => {
    for (const file of SEEKER_SOURCES) {
      const code = withoutComments(read(file));
      expect(code.length, file).toBeGreaterThan(200); // found it before judging it
      expect(code, file).not.toMatch(NAMES_THE_FRAMEWORK);
    }
  });

  it("the detector can fail", () => {
    expect(NAMES_THE_FRAMEWORK.test("NSQF level 4")).toBe(true);
    expect(NAMES_THE_FRAMEWORK.test("Skilled worker, level 4")).toBe(false);
    expect(withoutComments("/* NSQF */ const a = `NSQF ${n}`;")).toMatch(NAMES_THE_FRAMEWORK);
    expect(withoutComments("// NSQF only here\nconst a = 1;")).not.toMatch(NAMES_THE_FRAMEWORK);
  });

  it("every level a seeker meets goes through the one function", () => {
    for (const file of [
      "app/[locale]/jobs/[slug]/page.tsx",
      "app/[locale]/courses/[slug]/page.tsx",
      "app/[locale]/skills/[slug]/page.tsx",
      "components/cards/CourseCard.tsx",
      "components/cards/StandardCard.tsx",
      "components/SearchResults.tsx",
      "components/CareerLadder.tsx",
      "components/profile/RolePicker.tsx",
    ]) {
      expect(read(file), file).toMatch(/levelLabel|levelOrAbove/);
    }
  });
});
