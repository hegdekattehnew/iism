/**
 * A match, said in a sentence (Sprint 70, UI-13).
 *
 * A match card used to be a report: a ten-chip level scale and two lists of full standard names
 * with their codes, with the answer to "why 45%, and what do I do?" at the bottom. This is the
 * answer, in counts and names. **It computes nothing the server did not send**: the counts are the
 * lengths of the two lists the scorer returned, after the same presentation rules a vacancy's
 * standards get (`presentRequirements`): one standard listed under two codes counts once, a
 * standard held under one code is held, and the generic entries every qualification carries are
 * left out, because "you are missing Employability skills" is not what a person can act on. The
 * score still counts them, so the sentence says "skills this job asks for", never "the score is".
 *
 * The phone has the same rule (`mobile/src/core/match-summary.ts`); both run over
 * `tests/fixtures/match_summary_cases.json`.
 */

import { presentRequirements, type Requirement } from "./requirements";

export type ListedSkill = { name: string; is_mandatory: boolean; importance: number };

export type MatchSummary = {
  kind: "all" | "some" | "none";
  have: number;
  total: number;
  /** At most two missing standards, required ones first. */
  names: string[];
  /** How many more are missing than are named. */
  more: number;
};

const NAMED = 2;

const key = (name: string) => name.toLowerCase().replace(/\s+/g, " ").trim();

const asRequirement = (s: ListedSkill): Requirement => ({
  slug: s.name,
  name: s.name,
  mandatory: s.is_mandatory,
  importance: s.importance,
});

export function matchSummary(
  matched: readonly ListedSkill[],
  missing: readonly ListedSkill[],
): MatchSummary {
  const held = presentRequirements(matched.map(asRequirement)).main;
  const heldKeys = new Set(held.map((r) => key(r.name)));
  // Held under any code is held: a name in both lists is the person's.
  const lacking = presentRequirements(missing.map(asRequirement)).main.filter(
    (r) => !heldKeys.has(key(r.name)),
  );
  const have = held.length;
  const total = have + lacking.length;
  const kind = lacking.length === 0 ? "all" : have === 0 ? "none" : "some";
  return {
    kind,
    have,
    total,
    names: lacking.slice(0, NAMED).map((r) => r.name),
    more: Math.max(0, lacking.length - NAMED),
  };
}
