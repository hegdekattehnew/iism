"use client";

import { useLocale, useTranslations } from "next-intl";

import { ScoreDial } from "@/components/cards/ScoreDial";
import { Avatar } from "@/components/ui/avatar";
import { CheckCircleIcon, MapPinIcon, RupeeIcon } from "@/components/ui/icons";
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
 *
 * **Card v3** (Sprint 84, BL-19.15, the design brief's avatar-and-icon-chip card): the employer's
 * mark and the title in one row, **the pay as a tinted chip and the place as an icon chip** beneath,
 * and a muted line for experience, how long ago and the two small badges. Designed for height: it is
 * taller than the card it replaced, and `/jobs` was measured before and after (BL-19.15's capture).
 *
 * A signed-in job seeker's card carries **the match score** (UI-04) when the person has one for this
 * vacancy. `scoreSlot` says the person is a seeker, so the title leaves room for a score **before it
 * arrives**: the score is a second request and a title that re-wrapped when it landed would move the
 * list under the reader's thumb (ADR-065).
 */

export function JobCard({
  job,
  now,
  score,
  scoreSlot = false,
}: {
  job: JobCardData;
  now?: number;
  /** The signed-in seeker's match score for this vacancy, when there is one. */
  score?: number | null;
  /** Reserve the score's place (the person is a job seeker), whether or not a score has arrived. */
  scoreSlot?: boolean;
}) {
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
      className="relative block h-full rounded-xl border border-border-token bg-surface p-4 shadow-card transition-shadow hover:border-brand hover:shadow-raised"
    >
      <div className="flex items-start gap-3">
        <Avatar name={job.tenant.name} />
        <div className={`min-w-0 flex-1 ${scoreSlot ? "pr-24" : ""}`}>
          <h2 className="text-base font-semibold">{job.title}</h2>
          <p className="text-sm text-muted">
            {job.tenant.name}
            {job.tenant.is_verified && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs font-medium text-success-text">
                <CheckCircleIcon className="h-3.5 w-3.5" />
                {tj("verifiedEmployer")}
              </span>
            )}
          </p>
        </div>
      </div>
      {typeof score === "number" && <ScoreDial score={score} className="absolute right-4 top-4" />}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft px-2.5 py-1 text-sm font-semibold text-brand">
          <RupeeIcon className="h-4 w-4" />
          {pay}
        </span>
        {place && (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
            <MapPinIcon className="h-4 w-4" />
            {place}
          </span>
        )}
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
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
