"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { CoverageBar } from "@/components/CoverageBar";
import { SessionExpired } from "@/components/SessionExpired";
import { Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { ApiError, detailOf, isSignedOut, readDetail } from "@/lib/http";

/** One standard, as a chip: required ones say so, and the code is shown because
 *  it is what an assessor and a certificate both say. Shared by the matches page,
 *  the rejection panel and the career ladder, so a gap reads the same wherever it
 *  appears. It wraps (`flex-wrap`, `max-w-full`): standards are named like
 *  "Implement the interventions planned for patients with diverse needs", and on a
 *  360px phone three unwrapped columns squeezed the name to a word a line and ran
 *  the code off the card. */
export function SkillChip({
  skill,
  held,
}: {
  skill: { name: string; nos_code?: string | null; is_mandatory: boolean };
  held: boolean;
}) {
  const t = useTranslations("matchesPage");
  return (
    <span
      className={`inline-flex max-w-full flex-wrap items-center gap-x-1.5 gap-y-0.5 rounded-lg border px-2.5 py-1 text-xs ${
        held
          ? "border-success-border bg-success-surface text-success-text"
          : "border-border-token bg-surface text-muted"
      }`}
    >
      {skill.is_mandatory && (
        <span className="font-semibold uppercase tracking-wide">{t("mandatory")}</span>
      )}
      <span className="min-w-0 break-words">{skill.name}</span>
      {skill.nos_code && (
        <span className="font-mono text-[10px] opacity-70">{skill.nos_code}</span>
      )}
    </span>
  );
}

/**
 * "Why not me": what one application was missing, and the courses that teach it.
 *
 * Fetched when opened, not with the list, because most people open none. The gap
 * is computed by the server from the candidate's skills **as they are now**, so
 * it shrinks as they add to them -- which is what they came here to find out.
 *
 * Course links here do **not** report `course_opened`. That event is the second
 * half of a pair with `course_recommended`, which the server records when it
 * builds a match's course list, and this list was never recorded as a
 * recommendation: counting its clicks would inflate the candidate-to-course
 * click-through ADR-025 treats as a signal.
 */
export function GapPanel({ applicationId }: { applicationId: string }) {
  const t = useTranslations("applications");
  const tm = useTranslations("matchesPage");

  const gap = useQuery({
    queryKey: ["me", "applications", applicationId, "gap"],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/me/applications/{application_id}/gap", {
        params: { path: { application_id: applicationId } },
      });
      const status = response.status;
      if (error || !data) throw new ApiError(status, readDetail(error));
      return data;
    },
    retry: false,
  });

  if (gap.isPending) return <Skeleton className="mt-3 h-24 w-full rounded-lg" />;
  if (isSignedOut(gap.error)) return <SessionExpired variant="inline" />;
  if (gap.isError) {
    return <p className="mt-3 text-sm text-muted">{detailOf(gap.error) ?? t("gapError")}</p>;
  }

  const data = gap.data;
  const missing = data.missing ?? [];
  const courses = data.courses ?? [];
  return (
    <div className="mt-3 space-y-4 border-t border-border-token pt-4">
      <p className="text-xs text-muted">{t("gapIntro")}</p>

      <CoverageBar
        coverage={data.coverage}
        missingMandatory={data.missing_mandatory}
        capped={data.capped_by_mandatory}
      />

      {missing.length === 0 ? (
        <p className="text-sm">{t("gapNothing")}</p>
      ) : (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {tm("youNeed")}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {missing.map((s) => (
              <SkillChip key={s.skill_id} skill={s} held={false} />
            ))}
          </div>
        </div>
      )}

      {missing.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {tm("coursesHeading")}
          </p>
          {courses.length === 0 ? (
            <p className="mt-1.5 text-sm text-muted">{tm("noCourses")}</p>
          ) : (
            <ul className="mt-1.5 space-y-2">
              {courses.map((c) => (
                <li key={c.slug} className="rounded-lg border border-border-token p-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <Link
                      href={`/courses/${c.slug}`}
                      className="text-sm font-semibold underline-offset-4 hover:underline"
                    >
                      {c.title}
                    </Link>
                    {c.duration_hours != null && (
                      <span className="text-xs text-muted">
                        {tm("hours", { hours: c.duration_hours })}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-brand">
                    {tm("closesGap", { closed: c.closes_count, total: c.gap_size })}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
