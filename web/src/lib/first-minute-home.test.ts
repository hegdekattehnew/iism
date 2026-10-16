import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import hi from "@/messages/hi.json";
import ms from "@/messages/ms.json";

import { EXAMPLE_JOBS } from "./example-jobs";

/**
 * What a visitor's first minute is made of (Sprint 70, UI-01/02).
 *
 * Three things a render test cannot say: the words on the homepage are the seeker's and not the
 * product's, the example searches are all translated, and the homepage is the sections it is meant
 * to be (the framework band lives on About now).
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (p: string) => readFileSync(join(SRC, p), "utf8");

type Tree = { [key: string]: string | Tree };

function strings(tree: Tree, prefix = ""): [string, string][] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [[`${prefix}${k}`, v] as [string, string]] : strings(v, `${prefix}${k}.`),
  );
}

/** The product's vocabulary: right on About and for employers, wrong in front of a job seeker. */
const JARGON = /NSQF|framework|taxonomy|occupational standard|assessable|criteria|qualification pack/i;

/** The `stats` keys that belong to the framework band (About), not to the people band (homepage). */
const FRAMEWORK_KEYS = new Set([
  "heading",
  "sub",
  "standards",
  "qualifications",
  "criteria",
  "awardingBodies",
  "sectors",
  "entryRoutes",
  "footnote",
]);

function homepageWords(messages: typeof en): [string, string][] {
  const stats = Object.fromEntries(
    Object.entries(messages.stats).filter(([k]) => !FRAMEWORK_KEYS.has(k)),
  ) as Tree;
  return [
    ...strings(messages.hero as Tree, "hero."),
    ...strings(messages.how as Tree, "how."),
    ...strings(messages.browse as Tree, "browse."),
    ...strings(messages.cta as Tree, "cta."),
    ...strings(messages.chooser as Tree, "chooser."),
    ...strings(stats, "stats."),
  ];
}

describe("the homepage speaks the seeker's words", () => {
  for (const [name, messages] of [
    ["en", en],
    ["hi", hi],
    ["ms", ms],
  ] as const) {
    it(`${name}: no framework vocabulary in what a job seeker reads first`, () => {
      const words = homepageWords(messages);
      expect(words.length).toBeGreaterThan(40); // found them before judging any
      const offenders = words.filter(([, text]) => JARGON.test(text)).map(([k, t]) => `${k}: ${t}`);
      expect(offenders).toEqual([]);
    });
  }

  it("the detector can fail", () => {
    expect(JARGON.test("NSQF-aligned skill intelligence")).toBe(true);
    expect(JARGON.test("Built on the national framework, not a guess")).toBe(true);
    expect(JARGON.test("238,370 assessable criteria")).toBe(true);
    expect(JARGON.test("Tell us the job you want")).toBe(false);
  });

  it("the vocabulary is still said where it belongs: the framework band on About", () => {
    const framework = [en.stats.heading, en.stats.sub, en.stats.standards, en.stats.criteria];
    expect(framework.some((t) => JARGON.test(t))).toBe(true);
  });
});

describe("the example searches", () => {
  it("are four or five, each a plain query", () => {
    expect(EXAMPLE_JOBS.length).toBeGreaterThanOrEqual(4);
    expect(EXAMPLE_JOBS.length).toBeLessThanOrEqual(5);
    for (const { query } of EXAMPLE_JOBS) expect(query).toMatch(/^[a-z ]+$/); // English: the corpus is
  });

  it("are all translated, in every language that ships", () => {
    for (const messages of [en, hi, ms]) {
      const chips = messages.hero.chip as Record<string, string>;
      for (const { key } of EXAMPLE_JOBS) expect(chips[key], key).toBeTruthy();
    }
    // And Hindi is Hindi, not English left behind.
    for (const { key } of EXAMPLE_JOBS) {
      expect((hi.hero.chip as Record<string, string>)[key]).toMatch(/[ऀ-ॿ]/);
    }
  });

  it("and no chip is left in the messages that the list does not name", () => {
    expect(Object.keys(en.hero.chip).sort()).toEqual(EXAMPLE_JOBS.map((c) => c.key).sort());
  });
});

describe("the homepage is made of what it is meant to be", () => {
  const home = read("app/[locale]/page.tsx");
  const about = read("app/[locale]/about/page.tsx");

  it("has the hero, the people band, how it works, the browse counts and the closing call", () => {
    for (const part of ["Hero", "StatsBand", "HowItWorks", "BrowsePanels", "CtaBand"]) {
      expect(home).toContain(`<${part} />`);
    }
  });

  it("no longer carries the framework band or the three audience cards", () => {
    expect(home).not.toContain("FrameworkBand");
    expect(home).not.toContain("Audiences");
  });

  it("About carries the framework band instead", () => {
    expect(about).toContain("<FrameworkBand />");
  });

  it("the people band is only the people band", () => {
    const band = read("components/StatsBand.tsx");
    expect(band).not.toContain('"standards"');
    expect(band).not.toContain('"criteria"');
  });
});
