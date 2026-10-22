import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import hi from "@/messages/hi.json";
import ms from "@/messages/ms.json";

/**
 * The designer's review, first fixes (Sprint 91): the parts of them that are words and a rule in the
 * stylesheet, which no component test sees.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const css = readFileSync(join(SRC, "app/globals.css"), "utf8");

const JARGON = /National Occupational Standards|NSQF|taxonomy|framework|criteria/i;

describe("first fixes", () => {
  it("the employer's workspace opens in plain words, in every language", () => {
    for (const [name, messages] of [["en", en], ["hi", hi], ["ms", ms]] as const) {
      expect(messages.employerWorkspace.subtitle, name).not.toMatch(JARGON);
      expect(messages.employerWorkspace.roleStartTitle.length, name).toBeGreaterThan(5);
      expect(messages.employerWorkspace.roleStartHint, name).not.toMatch(JARGON);
    }
  });

  it("every new message exists in all three catalogues", () => {
    const keys = (m: typeof en) => [
      ...Object.keys(m.chooser).filter((k) => k.startsWith("welcome")),
      ...Object.keys(m.employerWorkspace).filter((k) => k.startsWith("roleStart")),
      ...Object.keys(m.courseInterest).filter((k) => ["replyBy", "replyHelp", "notHeard"].includes(k)),
      ...Object.keys(m.coursesPage).filter((k) => k.startsWith("started")),
      ...Object.keys(m.providerInbox).filter((k) => k === "waitingDays"),
    ];
    expect(keys(en).length).toBeGreaterThan(15);
    expect(keys(hi).sort()).toEqual(keys(en).sort());
    expect(keys(ms).sort()).toEqual(keys(en).sort());
  });

  it("the words added in Sprint 92 exist in all three catalogues", () => {
    for (const [name, m] of [["en", en], ["hi", hi], ["ms", ms]] as const) {
      expect(m.applications.signInToApplyHint.length, name).toBeGreaterThan(10);
      expect(m.reviews.notEnough.length, name).toBeGreaterThan(10);
      expect(m.jobsPage.verifiedBy.length, name).toBeGreaterThan(5);
      expect(m.coursesPage.verifiedBy.length, name).toBeGreaterThan(5);
    }
  });

  it("the stylesheet hides the visitor's chooser, at the welcome card's height, for a browser that holds a sign-in", () => {
    const rule = css.match(/html\[data-auth\] \[data-home-chooser\]:not\(\[data-shown\]\) \{[^}]*\}/)?.[0] ?? "";
    expect(rule).toContain("height: 11rem");
    expect(rule).toContain("visibility: hidden");
    expect(rule).toContain("overflow: hidden");
  });

  it("a visitor, with no sign-in, is not hidden from the chooser", () => {
    // The rule is keyed to `html[data-auth]`; nothing hides `[data-home-chooser]` without it.
    const bare = [...css.matchAll(/(^|\n)\[data-home-chooser\][^{]*\{/g)];
    expect(bare).toEqual([]);
  });
});
