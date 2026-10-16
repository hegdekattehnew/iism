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

export function experienceText(
  job: Pick<JobCardData, "experience_min_years" | "experience_max_years">,
  t: Translate,
): string {
  if (job.experience_min_years === 0 && !job.experience_max_years) return t("experienceNone");
  if (job.experience_max_years)
    return t("experienceRange", { min: job.experience_min_years, max: job.experience_max_years });
  return t("experience", { min: job.experience_min_years });
}

