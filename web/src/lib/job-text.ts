/**
 * The words a vacancy is described in, as pure functions (Sprint 69).
 *
 * Not in `JobCard.tsx`: that file is `"use client"`, and the vacancy page is a server component
 * that must *call* these (`buttonVariants` taught this in Sprint 11: a function exported from a
 * client module cannot be called on the server).
 */

import { formatCount } from "@/lib/count";
import { type PayLine } from "@/lib/pay";

export type JobCardData = {
  slug: string;
  title: string;
  location_state?: string | null;
  location_district?: string | null;
  employment_type: string;
  experience_min_years: number;
  experience_max_years?: number | null;
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
  closes_at?: string | null;
  published_at?: string | null;
  tenant: { name: string; is_verified?: boolean };
};

export type Translate = (key: string, values?: Record<string, string | number>) => string;

/** The posted figure as words, in the unit `payLine` chose. */
export function payText(line: PayLine, t: Translate, locale: string): string {
  const n = (v: number) => formatCount(v, locale);
  switch (line.unit) {
    case "none":
      return t("salaryUndisclosed");
    case "month":
      if (line.shape === "range")
        return t("salaryMonthly", { min: n(line.min), max: n(line.max) });
      if (line.shape === "exact") return t("salaryMonthlyExact", { min: n(line.min) });
      return t("salaryMonthlyFrom", { min: n(line.min) });
    case "posted":
      return line.shape === "range"
        ? t("salaryPosted", { min: n(line.min), max: n(line.max) })
        : t("salaryPostedFrom", { min: n(line.min) });
    case "year":
      return line.shape === "range"
        ? t("salary", { min: n(line.min), max: n(line.max) })
        : t("salaryFrom", { min: n(line.min) });
  }
}

/** Whole days until `closes_at`, only when it is near enough to matter (30 days) and still ahead. */
export function daysToClose(closesAt: string | null | undefined, now = Date.now()): number | null {
  if (!closesAt) return null;
  const ms = new Date(closesAt).getTime() - now;
  if (Number.isNaN(ms) || ms <= 0) return null;
  const days = Math.ceil(ms / 86_400_000);
  return days <= 30 ? days : null;
}

/** How long a vacancy has been live (Sprint 74), as a fact the clients phrase in their own language. */
export type Posted =
  | { kind: "today" }
  | { kind: "yesterday" }
  | { kind: "days"; days: number }
  | { kind: "month" };

/**
 * Whole elapsed days since `published_at`, never a calendar guess: under a day (or a stamp in the
 * future, which is clock skew) is today, 1 is yesterday, 2 to 29 is a number, 30 or more is "over a
 * month" and never a precise old figure. `null` when there is no date or it cannot be read: a vacancy
 * published before the column existed says nothing rather than something made up. The same rule runs
 * on the phone (`mobile/src/core/labels.ts`) over `tests/fixtures/posted_cases.json`.
 */
export function postedAgo(postedAt: string | null | undefined, now = Date.now()): Posted | null {
  if (!postedAt) return null;
  const ms = now - new Date(postedAt).getTime();
  if (Number.isNaN(ms)) return null;
  const days = Math.floor(ms / 86_400_000);
  if (days < 1) return { kind: "today" };
  if (days === 1) return { kind: "yesterday" };
  return days < 30 ? { kind: "days", days } : { kind: "month" };
}

export function postedText(
  postedAt: string | null | undefined,
  t: Translate,
  now = Date.now(),
): string | null {
  const posted = postedAgo(postedAt, now);
  if (posted === null) return null;
  switch (posted.kind) {
    case "today":
      return t("postedToday");
    case "yesterday":
      return t("postedYesterday");
    case "days":
      return t("postedDays", { days: posted.days });
    case "month":
      return t("postedOverMonth");
  }
}

/**
 * What a course's qualification is worth (Sprint 75, BL-12.8): a number, or `null` when there is
 * nothing a person can make sense of (no figure, zero, negative, not a number). The server already
 * says `null` for those; this is the guard that keeps "0 credits" and "NaN credits" off a screen. The
 * same rule runs on the phone over `tests/fixtures/credit_cases.json`.
 */
export function creditCount(credits: number | null | undefined): number | null {
  return typeof credits === "number" && Number.isFinite(credits) && credits > 0 ? credits : null;
}

export function creditsText(credits: number | null | undefined, t: Translate): string | null {
  const count = creditCount(credits);
  return count === null ? null : t("creditsChip", { count });
}

export function experienceText(
  job: Pick<JobCardData, "experience_min_years" | "experience_max_years">,
  t: Translate,
): string {
  if (job.experience_min_years === 0 && !job.experience_max_years) return t("experienceNone");
  if (job.experience_max_years)
    return t("experienceRange", { min: job.experience_min_years, max: job.experience_max_years });
  return t("experience", { min: job.experience_min_years });
}

