/**
 * A vacancy's standards, as a seeker can read them (Sprint 69, UI-09).
 *
 * The list comes from the national standards: names pasted in capitals, the same standard under two
 * codes, and generic entries ("Employability skills", "OJT") that every qualification carries. This
 * collapses the duplicates, sentence-cases a shouted name and moves the generic ones to a second
 * group. Pure; the phone has the same rule (`mobile/src/core/requirements.ts`) and both are tested
 * against `tests/fixtures/requirements_cases.json`.
 */

export type Requirement = {
  slug: string;
  name: string;
  mandatory: boolean;
  importance: number;
};

/** "Employability skills …", "OJT …", "On-the-job training": at the start of the name, not inside it. */
const GENERIC = /^(employability skills|ojt\b|on[- ]the[- ]job)/i;

const key = (name: string) => name.toLowerCase().replace(/\s+/g, " ").trim();

function sentenceCase(name: string): string {
  if (!/[A-Za-z]/.test(name) || name !== name.toUpperCase()) return name;
  const lower = name.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function presentRequirements(list: Requirement[]): {
  main: Requirement[];
  also: Requirement[];
} {
  const merged = new Map<string, Requirement>();
  for (const r of list) {
    const k = key(r.name);
    const seen = merged.get(k);
    if (!seen) {
      merged.set(k, { ...r });
      continue;
    }
    const winner = r.mandatory && !seen.mandatory ? r : seen;
    merged.set(k, {
      slug: winner.slug,
      name: winner.name,
      mandatory: seen.mandatory || r.mandatory,
      importance: Math.max(seen.importance, r.importance),
    });
  }
  const order = (a: Requirement, b: Requirement) =>
    Number(b.mandatory) - Number(a.mandatory) || b.importance - a.importance;
  const all = [...merged.values()]
    .map((r) => ({ ...r, name: sentenceCase(r.name) }))
    .sort(order);
  return {
    main: all.filter((r) => !GENERIC.test(r.name)),
    also: all.filter((r) => GENERIC.test(r.name)),
  };
}
