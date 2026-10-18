"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Avatar } from "@/components/ui/avatar";
import { CalendarIcon, MapPinIcon, RupeeIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";
import { creditsText, type Translate } from "@/lib/job-text";

export const COURSE_MODES = ["online", "offline", "hybrid"] as const;

export type Course = {
  slug: string;
  title: string;
  description?: string | null;
  mode: (typeof COURSE_MODES)[number];
  language: "en" | "hi" | "both";
  duration_hours?: number | null;
  fee_inr?: number | null;
  nsqf_level?: number | null;
  qualification_credits?: number | null;
  location_state?: string | null;
  location_district?: string | null;
  starts_on?: string | null;
  started?: boolean;
  tenant: { name: string; city?: string | null };
};

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function feeLabel(c: Pick<Course, "fee_inr">, t: ReturnType<typeof useTranslations<"coursesPage">>) {
  if (c.fee_inr == null || c.fee_inr === 0) return t("feeFree");
  return t("fee", { amount: inr(c.fee_inr) });
}

/**
 * One course on a list, on the same card as a vacancy (Sprint 84, BL-19.15): the provider's mark and
 * the title in one row, **the fee as a tinted chip, the place and the start as icon chips**, and a
 * muted line for the mode, the language, the level, the credits and how long it runs. A fact about
 * the course that changes (started or not, seats) is derived by the server and only drawn here.
 */
export function CourseCard({ course: c }: { course: Course }) {
  const t = useTranslations("coursesPage");
  const format = useFormatter();
  const credits = creditsText(c.qualification_credits, t as unknown as Translate);
  const place = c.mode === "online" ? null : [c.location_district, c.location_state].filter(Boolean).join(", ");
  const start = c.starts_on
    ? t(c.started ? "startedOn" : "startsOn", {
        date: format.dateTime(new Date(`${c.starts_on}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" }),
      })
    : null;

  return (
    <Link
      href={`/courses/${c.slug}`}
      className="block h-full rounded-xl border border-border-token bg-surface p-4 shadow-card transition-shadow hover:border-brand hover:shadow-raised"
    >
      <div className="flex items-start gap-3">
        <Avatar name={c.tenant.name} />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold">{c.title}</h2>
          <p className="text-sm text-muted">{c.tenant.name}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft px-2.5 py-1 text-sm font-semibold text-brand">
          <RupeeIcon className="h-4 w-4" />
          {feeLabel(c, t)}
        </span>
        {place && (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
            <MapPinIcon className="h-4 w-4" />
            {place}
          </span>
        )}
        {start && (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1 text-sm text-muted">
            <CalendarIcon className="h-4 w-4" />
            {start}
          </span>
        )}
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span className="rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-brand">
          {t(`mode.${c.mode}`)}
        </span>
        <span>{t(`language.${c.language}`)}</span>
        {c.nsqf_level != null && <span>{t("level", { level: c.nsqf_level })}</span>}
        {credits && <span>{credits}</span>}
        {c.duration_hours != null && <span>{t("duration", { hours: c.duration_hours })}</span>}
      </p>
      {c.description && <p className="mt-2 line-clamp-2 text-sm text-muted">{c.description}</p>}
    </Link>
  );
}
