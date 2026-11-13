/**
 * A qualification level in plain words (Sprint 104, BL-22.5).
 *
 * A job seeker reading "NSQF level 4" learns nothing; "Skilled worker, level 4" says what it asks
 * of them. NSQF levels run 1 to 10 and the half levels (2.5, 3.5, 4.5, 5.5, 6.5) are real, so a half
 * is **the step between its two neighbours**, never a rounding. The words themselves are messages
 * (`levels.*`, three languages); this file is only *which step* a level is, and it is one rule for
 * both clients: `tests/fixtures/level_cases.json` is read by the web's and the phone's tests alike.
 *
 * **The words are the engineer's and have not been read by anyone who knows the work**
 * (`docs/design/plain-levels-for-review.md` is the reader's copy). The number always stays beside
 * them, so a wrong word never hides the fact.
 */

export type LevelStops =
  | { kind: "whole"; step: number }
  | { kind: "between"; lower: number; upper: number };

/** `levels.*`: the catalogue's namespace, bound by the caller (`useTranslations("levels")`). */
export type LevelSay = (key: string, values?: Record<string, string | number>) => string;

const MIN = 1;
const MAX = 10;

function nearestHalf(level: unknown): number | null {
  const n = typeof level === "number" ? level : Number.NaN;
  if (!Number.isFinite(n) || n < MIN || n > MAX) return null;
  return Math.round(n * 2) / 2;
}

/** Which step of the ladder a level is, or null when it is no level at all. */
export function levelStops(level: unknown): LevelStops | null {
  const half = nearestHalf(level);
  if (half === null) return null;
  if (Number.isInteger(half)) return { kind: "whole", step: half };
  // 10 is the top: there is no 10.5, so a half is always below it.
  return { kind: "between", lower: Math.floor(half), upper: Math.floor(half) + 1 };
}

/** The number as people write it: 4 is "4", 4.5 is "4.5". */
export function shownLevel(level: unknown): string | null {
  const half = nearestHalf(level);
  if (half === null) return null;
  return String(half);
}

/** "Skilled worker", or "Semi-skilled worker to skilled worker" for a half level. */
export function levelName(level: unknown, say: LevelSay): string | null {
  const stops = levelStops(level);
  if (stops === null) return null;
  if (stops.kind === "whole") return say(`name.l${stops.step}`);
  // The second name continues the sentence ("Skilled worker to senior skilled worker"): its first
  // letter is lowered where the script has a case, and a script with none is untouched.
  const upper = say(`name.l${stops.upper}`);
  return say("between", {
    lower: say(`name.l${stops.lower}`),
    upper: upper.charAt(0).toLocaleLowerCase() + upper.slice(1),
  });
}

/** "Skilled worker, level 4": the words, and the number beside them. */
export function levelLabel(level: unknown, say: LevelSay): string | null {
  const name = levelName(level, say);
  const shown = shownLevel(level);
  if (name === null || shown === null) return null;
  return say("labelled", { name, level: shown });
}

/** "Skilled worker or above (level 4)": what a vacancy asks for. */
export function levelOrAbove(level: unknown, say: LevelSay): string | null {
  const name = levelName(level, say);
  const shown = shownLevel(level);
  if (name === null || shown === null) return null;
  return say("orAbove", { name, level: shown });
}

/**
 * One line of what the step means. **A half level has none**: the line belongs to a step, and
 * inventing one for the space between two would be the engineer's guess in a reader's mouth.
 */
export function levelLine(level: unknown, say: LevelSay): string | null {
  const stops = levelStops(level);
  if (stops === null || stops.kind !== "whole") return null;
  return say(`line.l${stops.step}`);
}
