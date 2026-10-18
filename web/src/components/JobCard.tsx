"use client";

import { useLocale, useTranslations } from "next-intl";

import { CheckCircleIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";
import {
  daysToClose,
  experienceText,
  payText,
  postedText,
  type JobCardData,
  type Translate,
} from "@/lib/job-text";
import { payLine } from "@/lib/pay";

/**
 * One vacancy on a list (Sprint 69, UI-04/05/10).
 *
 * The review's finding was that a card read as a database row: a boilerplate sentence, two grey
 * badges ("NSQF level 4 and above") that mean nothing to a job seeker, and pay per year where
 * the work is quoted per month. A card now carries what decides whether to open it, in the order
 * people ask: **what, who, where, how much, by when**. The NSQF level lives on the vacancy page and
 * the standards pages; the sentence is the employer's own words and is read on the page.
 *
 * A card never says "not verified". The mark is a credit to an employer that has earned it; the
 * absence of a mark on a list is not an accusation, and the vacancy page is where the fact is stated.
 */

export function JobCard({ job, now }: { job: JobCardData; now?: number }) {
  const tj = useTranslations("jobsPage");
  const t = tj as unknown as Translate;
  const locale = useLocale();
  const pay = payText(payLine(job.salary_min_inr, job.salary_max_inr, job.employment_type), t, locale);
  const days = daysToClose(job.closes_at, now);
  const posted = postedText(job.published_at, t, now);
  const place = [job.location_district, job.location_state].filter(Boolean).join(", ");

  return (
    <Link
      href={`/jobs/${job.slug}`}
      className="block h-full rounded-xl border border-border-token bg-surface p-5 transition-colors hover:border-brand"
    >
      <h2 className="text-base font-semibold">{job.title}</h2>
      <p className="mt-1 text-sm text-muted">
        {job.tenant.name}
        {job.tenant.is_verified && (
          <span className="ml-2 inline-flex items-center gap-1 text-xs font-medium text-success-text">
            <CheckCircleIcon className="h-3.5 w-3.5" />
            {tj("verifiedEmployer")}
          </span>
        )}
      </p>
      {place && <p className="text-sm text-muted">{place}</p>}
      <p className="mt-3 text-base font-semibold">{pay}</p>
      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>{experienceText(job, t)}</span>
        {posted !== null && <span>{posted}</span>}
        {job.employment_type !== "full_time" && (
          <span className="rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-brand">
            {tj(`employmentType.${job.employment_type as "part_time"}`)}
          </span>
        )}
        {days !== null && (
          <span className="rounded-md bg-warning-surface px-2 py-0.5 text-xs font-medium text-warning-text">
            {tj("closesIn", { days })}
          </span>
        )}
      </p>
    </Link>
  );
}
