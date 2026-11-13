import cases from "../../../tests/fixtures/level_cases.json";
import en from "../messages/en.json";
import hi from "../messages/hi.json";
import { levelLabel, levelLine, levelName, levelOrAbove, levelStops, shownLevel } from "../core/level-words";
import type { LevelSay } from "../core/level-words";

/** A translator over the phone's own catalogue (the web's words, synced), ICU `{name}` filled in. */
function sayIn(messages: typeof en): LevelSay {
  const table = messages.levels as unknown as Record<string, unknown>;
  return (key, values) => {
    const found = key.split(".").reduce<unknown>((t, k) => (t as Record<string, unknown>)?.[k], table);
    if (typeof found !== "string") throw new Error(`missing message levels.${key}`);
    return found.replace(/\{(\w+)\}/g, (_, name: string) => String(values?.[name]));
  };
}

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

describe("the words, from the phone's catalogue", () => {
  it("name a whole level with its number beside it, and a line of what it means", () => {
    const say = sayIn(en);
    expect(levelName(4, say)).toBe("Skilled worker");
    expect(levelLabel(4, say)).toBe("Skilled worker, level 4");
    expect(levelOrAbove(3, say)).toBe("Semi-skilled worker or above (level 3)");
    expect(levelLine(4, say)).toBe("Does the job well on their own and handles usual problems.");
  });

  it("shows the number the step is, not the number it was given", () => {
    const say = sayIn(en);
    expect(levelLabel(4.4, say)).toBe("Skilled worker to senior skilled worker, level 4.5");
    expect(levelLabel(4.0, say)).toBe("Skilled worker, level 4");
  });

  it("name a half level as the space between two steps, with no line of its own", () => {
    const say = sayIn(en);
    expect(levelLabel(4.5, say)).toBe("Skilled worker to senior skilled worker, level 4.5");
    expect(levelLine(4.5, say)).toBeNull();
  });

  it("read in Hindi, with the number kept", () => {
    const say = sayIn(hi as unknown as typeof en);
    expect(levelLabel(4, say)).toBe("कुशल कामगार, स्तर 4");
    expect(levelLabel(3.5, say)).toContain("3.5");
  });

  it("say nothing for something that is no level", () => {
    const say = sayIn(en);
    for (const bad of [0, 11, null, undefined, "x"]) {
      expect(levelLabel(bad, say)).toBeNull();
      expect(levelLine(bad, say)).toBeNull();
    }
  });
});
