"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { CoverageBar, LevelScale } from "@/components/CoverageBar";
import { ButtonLink, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

type Missing = {
  name_en: string;
  nos_code?: string | null;
  importance: number;
  is_mandatory: boolean;
};
type Matched = Missing & { evidence: string; proficiency: number };

function ScoreDial({ score }: { score: number }) {
  const t = useTranslations("matchesPage");
  // Colour carries no information the number does not: it is a second
  // encoding for scanning, never the only one.
  const tone =
    score >= 75
      ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
      : score >= 45
        ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300"
        : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  return (
    <span
      className={`shrink-0 rounded-lg px-2.5 py-1 text-sm font-semibold ${tone}`}
    >
      {t("matchScore", { score })}
    </span>
  );
}

function SkillChip({
  skill,
  held,
}: {
  skill: Matched | Missing;
  held: boolean;
}) {
  const t = useTranslations("matchesPage");
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs ${
        held
          ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
          : "border-border-token bg-surface text-muted"
      }`}
    >
      {skill.is_mandatory && (
        <span className="font-semibold uppercase tracking-wide">
          {t("mandatory")}
        </span>
      )}
      <span>{skill.name_en}</span>
      {skill.nos_code && (
        <span className="font-mono text-[10px] opacity-70">
          {skill.nos_code}
        </span>
      )}
    </span>
  );
}

/** ADR-025 names candidate-to-course click-through as one of three metrics that
 *  stand in for a revenue signal while v1 is free. It is the one event the
 *  server cannot observe for itself: following a link out of a recommendation
 *  is a client-side act, and inferring it from a later course page view would
 *  credit organic browsing to a recommendation it had nothing to do with.
 *
 *  Fire-and-forget. A failed measurement must never cost the person the click. */
function reportCourseOpened(courseSlug: string, fromJobSlug: string) {
  void api.POST("/me/events/course-opened", {
    body: { course_slug: courseSlug, from_job_slug: fromJobSlug },
  });
}

export function MatchBrowser() {
  const t = useTranslations("matchesPage");
  const locale = useLocale();
  const isHi = locale === "hi";
  const [openSlug, setOpenSlug] = useState<string | null>(null);

  const matches = useQuery({
    queryKey: ["matches"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/matches", {
        params: { query: { limit: 20 } },
      });
      // openapi-fetch resolves rather than throws on a non-2xx, so without
      // this a 401 arrives as `data: undefined` and renders as "nothing
      // matches" -- telling a signed-out visitor they have no matches rather
      // than that they are not signed in.
      if (error || !data) throw new Error("matches request failed");
      return data;
    },
    retry: false,
  });

  // Detail is fetched only when a match is opened: it costs a gap analysis and
  // a course search per job, and nobody reads twenty of them.
  const detail = useQuery({
    queryKey: ["match", openSlug],
    enabled: openSlug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/matches/{slug}", {
        params: { path: { slug: openSlug as string } },
      });
      if (error || !data) throw new Error("match detail request failed");
      return data;
    },
    retry: false,
  });

  if (matches.isError) {
    return (
      <p className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
        {t("loadError")}
      </p>
    );
  }
  // A shape rather than an ellipsis: the page stops reflowing when the data
  // lands, which on a slow connection is most of the perceived jank.
  if (matches.isPending) {
    return (
      <ul className="space-y-4">
        {[0, 1, 2].map((i) => (
          <li key={i}>
            <Skeleton className="h-44 w-full rounded-xl" />
          </li>
        ))}
      </ul>
    );
  }

  // No declared skills is a different state from no matches, and saying so is
  // the difference between a dead end and a next step.
  if (matches.data && !matches.data.has_skills) {
    return (
      <div className="rounded-xl border border-border-token bg-surface p-6">
        <p className="text-sm text-muted">{t("noSkills")}</p>
        <ButtonLink href="/profile" className="mt-4">
          {t("addSkills")}
        </ButtonLink>
      </div>
    );
  }

  const items = matches.data?.items ?? [];
  if (items.length === 0) {
    return <p className="text-sm text-muted">{t("noMatches")}</p>;
  }

  return (
    <ul className="space-y-4">
      {items.map((m) => {
        const open = openSlug === m.job.slug;
        const d = open ? detail.data : null;
        const matched = m.matched ?? [];
        const missing = m.missing ?? [];
        const courses = d?.courses ?? [];
        return (
          <li
            key={m.job.slug}
            className="rounded-xl border border-border-token bg-surface p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">
                  {isHi && m.job.title_hi ? m.job.title_hi : m.job.title_en}
                </h2>
                <p className="mt-0.5 text-sm text-muted">
                  {[m.job.location_district, m.job.location_state]
                    .filter(Boolean)
                    .join(", ")}
                </p>
              </div>
              <ScoreDial score={m.score} />
            </div>

            <div className="mt-4">
              <CoverageBar
                coverage={m.coverage}
                missingMandatory={m.missing_mandatory}
                capped={m.capped_by_mandatory}
              />
            </div>

            {m.capped_by_mandatory && (
              <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
                {t("capped")}
              </p>
            )}

            {m.job.nsqf_level_min != null && (
              <div className="mt-4">
                <LevelScale
                  required={m.job.nsqf_level_min}
                  shortfall={m.level_shortfall}
                />
              </div>
            )}

            {matched.length > 0 && (
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t("youHave")}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {matched.map((s) => (
                    <SkillChip key={s.name_en} skill={s} held />
                  ))}
                </div>
              </div>
            )}

            {missing.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {t("youNeed")}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {missing.map((s) => (
                    <SkillChip key={s.name_en} skill={s} held={false} />
                  ))}
                </div>
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setOpenSlug(open ? null : m.job.slug)}
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline"
              >
                {open ? t("backToMatches") : t("coursesHeading")}
              </button>
              <Link
                href={`/jobs/${m.job.slug}`}
                className="text-sm text-muted underline-offset-4 hover:underline"
              >
                {t("viewJob")}
              </Link>
            </div>

            {open && (
              <div className="mt-4 border-t border-border-token pt-4">
                {detail.isPending && (
                  <Skeleton className="h-24 w-full rounded-lg" />
                )}

                {d && courses.length === 0 && (
                  <p className="text-sm text-muted">{t("noCourses")}</p>
                )}
                {d && courses.length > 0 && (
                  <ul className="space-y-2">
                    {courses.map((c) => (
                      <li
                        key={c.slug}
                        className="rounded-lg border border-border-token p-3"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <Link
                            href={`/courses/${c.slug}`}
                            onClick={() =>
                              reportCourseOpened(c.slug, m.job.slug)
                            }
                            className="text-sm font-semibold underline-offset-4 hover:underline"
                          >
                            {isHi && c.title_hi ? c.title_hi : c.title_en}
                          </Link>
                          {c.duration_hours != null && (
                            <span className="text-xs text-muted">
                              {t("hours", { hours: c.duration_hours })}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-brand">
                          {t("closesGap", {
                            closed: c.closes_count,
                            total: c.gap_size,
                          })}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}

                {/* How to become qualified at all, which is a different
                    question from how well you match today. */}
                {d?.entry && (
                  <div className="mt-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                      {t("entryHeading")}
                    </p>
                    <p className="mt-1 text-sm">
                      {t("entryVia", {
                        name: d.entry.qp_name,
                        code: d.entry.qp_code,
                      })}
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      {t("entryRoutes", { count: d.entry.routes_total })}
                      {d.entry.lowest_experience_years != null &&
                        ` · ${t("entryExperience", {
                          years: d.entry.lowest_experience_years,
                        })}`}
                    </p>
                    {d.entry.education_options.length > 0 && (
                      <p className="mt-1.5 text-xs text-muted">
                        {t("entryEducation")}:{" "}
                        {d.entry.education_options.slice(0, 3).join(" · ")}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
