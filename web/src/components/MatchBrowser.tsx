"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { CoverageBar, LevelScale } from "@/components/CoverageBar";
import { SkillChip } from "@/components/GapPanel";
import { CourseBudgetControl, SuggestedCourses } from "@/components/SuggestedCourses";
import { Button, ButtonLink, Skeleton } from "@/components/ui";
import { ScoreDial } from "@/components/cards/ScoreDial";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useCourseBudget } from "@/lib/course-budget";
import { fetchMatches } from "@/lib/matches";
import { matchSummary } from "@/lib/match-summary";


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

/** How many matches are shown before "Show more" (how many arrive is `MATCHES_FETCH`, in `lib/matches`). */
const FIRST = 5;

/**
 * Why this score, and what to do, in a sentence (Sprint 70, UI-13). The words come from
 * `matchSummary`, which counts the two lists the scorer returned and computes nothing else; it says
 * "skills this job asks for", never "the score is", because the score counts the generic standards
 * the sentence leaves out.
 */
function Sentence({
  matched,
  missing,
}: {
  matched: Parameters<typeof matchSummary>[0];
  missing: Parameters<typeof matchSummary>[1];
}) {
  const t = useTranslations("matchesPage");
  const summary = matchSummary(matched, missing);
  if (summary.kind === "all") return <p className="mt-3 text-sm">{t("sentenceAll")}</p>;
  const names = summary.names.join(", ");
  const list = summary.more > 0 ? t("missingAnd", { names, more: summary.more }) : names;
  return (
    <p className="mt-3 text-sm">
      {t(summary.kind === "none" ? "sentenceNone" : "sentenceSome", {
        have: summary.have,
        total: summary.total,
        missing: list,
      })}
    </p>
  );
}

export function MatchBrowser() {
  const t = useTranslations("matchesPage");
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const [shown, setShown] = useState(FIRST);

  const matches = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
    retry: false,
  });

  // Detail is fetched only when a match is opened: it costs a gap analysis and
  // a course search per job, and nobody reads twenty of them.
  const budget = useCourseBudget();
  const detail = useQuery({
    queryKey: ["match", openSlug, budget],
    enabled: openSlug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/matches/{slug}", {
        params: {
          path: { slug: openSlug as string },
          query: budget === null ? {} : { budget_inr: budget },
        },
      });
      if (error || !data) throw new Error("match detail request failed");
      return data;
    },
    retry: false,
  });

  if (matches.isError) {
    return (
      <p className="rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
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
  // The server's figure. `items.length` is only what arrived (the best fifty at most).
  const total = matches.data?.total ?? items.length;
  const visible = items.slice(0, shown);
  const left = items.length - visible.length;

  return (
    <>
    <ul className="space-y-4">
      {visible.map((m) => {
        const open = openSlug === m.job.slug;
        const d = open ? detail.data : null;
        const matched = m.matched ?? [];
        const missing = m.missing ?? [];
        const courses = d?.courses ?? [];
        const hasGap = matchSummary(matched, missing).kind !== "all";
        return (
          <li
            key={m.job.slug}
            className="rounded-xl border border-border-token bg-surface p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">
                  {m.job.title}
                </h2>
                <p className="mt-0.5 text-sm text-muted">
                  {[m.job.location_district, m.job.location_state]
                    .filter(Boolean)
                    .join(", ")}
                  {/* Rendered from the field; nothing computed here. Locality
                      only orders equal scores, so the badge says where, never
                      "better". */}
                  {(m.locality ?? 0) > 0 && (
                    <span className="ml-2 inline-block rounded bg-accent-soft px-1.5 py-0.5 text-xs font-medium text-brand">
                      {m.locality === 2 ? t("nearDistrict") : t("nearState")}
                    </span>
                  )}
                </p>
              </div>
              <ScoreDial score={m.score} />
            </div>

            <Sentence matched={matched} missing={missing} />

            {/* One primary action. With a gap it is the courses that close it; with none it is the
                job itself. Everything the report used to lead with is behind "Details". */}
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {hasGap ? (
                <>
                  <Button
                    size="md"
                    aria-expanded={open}
                    onClick={() => setOpenSlug(open ? null : m.job.slug)}
                  >
                    {open ? t("backToMatches") : t("seeCourses")}
                  </Button>
                  <Link
                    href={`/jobs/${m.job.slug}`}
                    className="inline-flex min-h-11 items-center text-sm font-medium text-muted underline-offset-4 hover:underline"
                  >
                    {t("viewJob")}
                  </Link>
                </>
              ) : (
                <ButtonLink href={`/jobs/${m.job.slug}`}>{t("viewJob")}</ButtonLink>
              )}
            </div>

            <details className="mt-3">
              <summary className="inline-flex min-h-11 cursor-pointer items-center rounded-sm text-sm font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                {t("details")}
              </summary>
              <div className="mt-2">
                <CoverageBar
                  coverage={m.coverage}
                  missingMandatory={m.missing_mandatory}
                  capped={m.capped_by_mandatory}
                />

                {m.capped_by_mandatory && (
                  <p className="mt-3 rounded-lg border border-warning-border bg-warning-surface px-3 py-2 text-xs text-warning-text">
                    {t("capped")}
                  </p>
                )}

                {m.experience_shortfall != null && (
                  <p className="mt-3 text-xs text-muted">
                    {t("experienceShort", { years: m.experience_shortfall })}
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
                        <SkillChip key={s.name} skill={s} held />
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
                        <SkillChip key={s.name} skill={s} held={false} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>

            {open && (
              <div className="mt-4 border-t border-border-token pt-4">
                {detail.isPending && (
                  <Skeleton className="h-24 w-full rounded-lg" />
                )}

                {d && courses.length === 0 && (
                  <p className="text-sm text-muted">{t("noCourses")}</p>
                )}
                {d && courses.length > 0 && (
                  <div className="space-y-3">
                    <CourseBudgetControl />
                    <SuggestedCourses
                      courses={courses}
                      onOpen={(slug) => reportCourseOpened(slug, m.job.slug)}
                    />
                  </div>
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

      {total > items.length && (
        <p className="mt-4 text-sm text-muted">{t("bestOf", { shown: items.length, total })}</p>
      )}
      {left > 0 && (
        <div className="mt-6 flex justify-center">
          <Button variant="secondary" onClick={() => setShown((n) => n + FIRST)}>
            {t("showMore", { left })}
          </Button>
        </div>
      )}
    </>
  );
}
