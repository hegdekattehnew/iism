import { describe, expect, it } from "vitest";

import cases from "../../../tests/fixtures/level_cases.json";
import en from "@/messages/en.json";
import hi from "@/messages/hi.json";
import ms from "@/messages/ms.json";

import { levelLabel, levelLine, levelName, levelOrAbove, levelStops, shownLevel } from "./level-words";
import type { LevelSay } from "./level-words";

/** A translator over one language's own words, with ICU `{name}` filled the way next-intl does. */
function sayIn(messages: typeof en): LevelSay {
  const table = messages.levels as unknown as Record<string, unknown>;
  return (key, values) => {
    const found = key.split(".").reduce<unknown>((t, k) => (t as Record<string, unknown>)?.[k], table);
    if (typeof found !== "string") throw new Error(`missing message levels.${key}`);
    return found.replace(/\{(\w+)\}/g, (_, name: string) => String(values?.[name]));
  };
}
const say = sayIn(en);

describe("which step a level is", () => {
  it("reads the shared fixture (a checker that read nothing would pass)", () => {
    expect(cases.cases.length).toBeGreaterThanOrEqual(12);
  });

  for (const c of cases.cases) {
    it(c.name, () => {
      expect(levelStops(c.level)).toEqual(c.expect);
      expect(shownLevel(c.level)).toEqual(c.shown);
    });
  }
});

describe("the words", () => {
  it("name a whole level and keep its number beside it", () => {
    expect(levelName(4, say)).toBe("Skilled worker");
    expect(levelLabel(4, say)).toBe("Skilled worker, level 4");
    expect(levelOrAbove(4, say)).toBe("Skilled worker or above (level 4)");
    expect(levelLine(4, say)).toBeTruthy();
  });

  it("shows the number the step is, not the number it was given", () => {
    expect(levelLabel(4.4, say)).toBe("Skilled worker to senior skilled worker, level 4.5");
    expect(levelLabel(4.0, say)).toBe("Skilled worker, level 4");
    expect(levelOrAbove(3.9, say)).toBe("Skilled worker or above (level 4)");
  });

  it("name a half level as the space between its neighbours, and give it no line of its own", () => {
    expect(levelName(4.5, say)).toBe("Skilled worker to senior skilled worker");
    expect(levelLabel(4.5, say)).toBe("Skilled worker to senior skilled worker, level 4.5");
    expect(levelLine(4.5, say)).toBeNull();
  });

  it("say nothing for something that is no level", () => {
    for (const bad of [0, 11, null, undefined, "x"]) {
      expect(levelName(bad, say)).toBeNull();
      expect(levelLabel(bad, say)).toBeNull();
      expect(levelOrAbove(bad, say)).toBeNull();
      expect(levelLine(bad, say)).toBeNull();
    }
  });
});

describe("the table is complete in every language", () => {
  for (const [name, messages] of [
    ["en", en],
    ["hi", hi],
    ["ms", ms],
  ] as const) {
    it(`${name}: a name and a line for each of the ten steps, and the two joins`, () => {
      const t = messages.levels as unknown as {
        name: Record<string, string>;
        line: Record<string, string>;
        between: string;
        labelled: string;
        orAbove: string;
      };
      for (let step = 1; step <= 10; step++) {
        expect(t.name[`l${step}`]?.length, `name l${step}`).toBeGreaterThan(2);
        expect(t.line[`l${step}`]?.length, `line l${step}`).toBeGreaterThan(8);
      }
      for (const join of [t.between, t.labelled, t.orAbove]) expect(join.length).toBeGreaterThan(3);
      expect(t.between).toContain("{lower}");
      expect(t.between).toContain("{upper}");
      expect(t.labelled).toContain("{name}");
      expect(t.labelled).toContain("{level}");
      expect(t.orAbove).toContain("{name}");
      expect(t.orAbove).toContain("{level}");
    });

    it(`${name}: no two steps share a name, or a half level would read as one step`, () => {
      const names = Object.values((messages.levels as unknown as { name: Record<string, string> }).name);
      expect(new Set(names).size).toBe(10);
    });

    it(`${name}: a half level reads in the language, not as two English words`, () => {
      const sayHere = sayIn(messages);
      const text = levelLabel(3.5, sayHere) ?? "";
      expect(text).toContain("3.5");
      // The second name is lowered where the script has a case, so compare without it.
      expect(text.toLocaleLowerCase()).toContain(sayHere("name.l3").toLocaleLowerCase());
      expect(text.toLocaleLowerCase()).toContain(sayHere("name.l4").toLocaleLowerCase());
    });
  }
});
