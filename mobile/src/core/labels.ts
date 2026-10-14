/**
 * The phrases a vacancy or a course card is built from, ported from the web's `JobBrowser.tsx`,
 * `CourseBrowser.tsx` and detail pages so the two clients say the same thing the same way, and so
 * the rules (what "free" means, when a place is hidden, which verb a start date takes) are tested
 * once instead of read off a screen.
 *
 * Every function takes the translator it should speak through (`useTranslations("jobsPage")` and
 * `("coursesPage")`) and returns text. No React Native import: this file is tested in Node.
 */

import { formatDate, formatInr, type MonthStyle } from "./format";

export type Translate = (key: string, values?: Record<string, string | number>) => string;
export type MonthName = (month: number, style: MonthStyle) => string;

export type JobTerms = {
  experience_min_years: number;
  experience_max_years?: number | null;
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
};

export function experienceLabel(job: JobTerms, t: Translate): string {
  if (job.experience_min_years === 0 && !job.experience_max_years) return t("experienceNone");
  if (job.experience_max_years) {
    return t("experienceRange", { min: job.experience_min_years, max: job.experience_max_years });
  }
  return t("experience", { min: job.experience_min_years });
}

export function salaryLabel(job: JobTerms, t: Translate): string {
  if (job.salary_min_inr && job.salary_max_inr) {
    return t("salary", { min: formatInr(job.salary_min_inr), max: formatInr(job.salary_max_inr) });
  }
  if (job.salary_min_inr) return t("salaryFrom", { min: formatInr(job.salary_min_inr) });
  return t("salaryUndisclosed");
}

export type CourseTerms = {
  mode: "online" | "offline" | "hybrid";
  fee_inr?: number | null;
  location_state?: string | null;
  location_district?: string | null;
  starts_on?: string | null;
  started?: boolean;
};

/** Zero and unstated both read as free: a course with no fee is not a course with a hidden one. */
export function feeLabel(course: Pick<CourseTerms, "fee_inr">, t: Translate): string {
  if (course.fee_inr == null || course.fee_inr === 0) return t("feeFree");
  return t("fee", { amount: formatInr(course.fee_inr) });
}

/**
 * Where it is held. An online course has no place, so there is nothing to say (never "place not
 * stated", which would read as a gap in the listing). An in-person one with no place says so, but
 * only where `statedFallback` is wanted (the detail page; a card just omits the line).
 */
export function whereLabel(
  course: CourseTerms,
  t: Translate,
  statedFallback = false,
): string | null {
  if (course.mode === "online") return null;
  const place = [course.location_district, course.location_state].filter(Boolean).join(", ");
  return place || (statedFallback ? t("placeNotStated") : null);
}

/** "Starts 14 Oct 2026" or "Started 14 Oct 2026"; `null` when the course gives no date. */
export function intakeLabel(
  course: CourseTerms,
  t: Translate,
  monthName: MonthName,
  style: MonthStyle = "short",
): string | null {
  if (!course.starts_on) return null;
  const date = formatDate(course.starts_on, monthName, style);
  if (date === null) return null;
  return t(course.started ? "startedOn" : "startsOn", { date });
}

/** `null` seats left means the provider did not say; zero is "Full". */
export function seatsLabel(seatsLeft: number | null | undefined, t: Translate): string | null {
  if (seatsLeft == null) return null;
  return seatsLeft === 0 ? t("full") : t("seatsLeft", { count: seatsLeft });
}

/** Mandatory standards first (they are what gate a hire), then by importance, highest first. */
export function mandatoryFirst<T extends { is_mandatory: boolean; importance: number }>(
  skills: readonly T[],
): T[] {
  return [...skills].sort(
    (a, b) => Number(b.is_mandatory) - Number(a.is_mandatory) || b.importance - a.importance,
  );
}

/** Names that appear more than once in a list, compared as a reader would (the web's rule). */
export function lookalikeNames(rows: readonly { name: string }[]): Set<string> {
  const seen = new Map<string, number>();
  for (const row of rows) {
    const key = row.name.trim().toLowerCase();
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  return new Set([...seen].filter(([, n]) => n > 1).map(([key]) => key));
}
