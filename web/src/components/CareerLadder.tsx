"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { CoverageBar } from "@/components/CoverageBar";
import { SkillChip } from "@/components/GapPanel";
import { Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import { Badge, Button, ButtonLink, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { paths } from "@/lib/api-schema";
import { ApiError, detailOf, isSignedOut, readDetail } from "@/lib/http";

type RoleHit =
  paths["/roles/search"]["get"]["responses"][200]["content"]["application/json"][number];
type Ladder =
  paths["/me/careers"]["get"]["responses"][200]["content"]["application/json"];
type Step = NonNullable<Ladder["steps"]>[number];

/** "Where you could move next", from the role you are in.
 *
 * The server derives each step from the national qualification data and says
 * why it offered it (`basis`): a role that shares standards with yours, one
 * rung or two up. Nothing here computes a number -- the fit is the server's
 * score, the gap is its list -- so a step and the match page cannot disagree.
 *
 * **A guess is labelled as one, and an unsure guess is not made.** With no role
 * chosen the server tries what the profile says and answers only when it is
 * certain; otherwise this asks. A ladder started from the wrong role is about
 * somebody else, and every step beneath it would look equally confident.
 */
export function CareerLadder() {
  const t = useTranslations("careerPaths");
  const [role, setRole] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);

  const ladder = useQuery({
    queryKey: ["me", "careers", role],
    queryFn: async () => {
      const { data, error, response } = await api.GET("/me/careers", {
        params: { query: role ? { role } : {} },
      });
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    retry: false,
  });

  if (ladder.isPending) return <Skeleton className="h-48 w-full rounded-xl" />;
  if (isSignedOut(ladder.error)) return <SessionExpired />;
  if (ladder.isError) {
    return <p className="text-sm text-muted">{detailOf(ladder.error) ?? t("error")}</p>;
  }

  const data = ladder.data;
  const steps = data.steps ?? [];
  const finding = data.needs_choice || changing;

  return (
    <div className="space-y-6">
      {data.anchor && (
        <div className="rounded-xl border border-border-token bg-surface p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("startingFrom")}
          </p>
          <p className="mt-1 text-lg font-semibold">{data.anchor.job_role}</p>
          <p className="text-sm text-muted">
            {t("level", { level: data.anchor.nsqf_level })}
            {data.anchor.sector_name ? ` · ${data.anchor.sector_name}` : ""}
          </p>
          {data.anchor_source === "guessed" && (
            <p className="mt-2 text-xs text-muted">{t("guessed")}</p>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="mt-2"
            aria-expanded={changing}
            onClick={() => setChanging((v) => !v)}
          >
            {changing ? t("keepRole") : t("changeRole")}
          </Button>
        </div>
      )}

      {finding && (
        <RoleFinder
          intro={data.needs_choice ? t("chooseIntro") : t("changeIntro")}
          onChoose={(slug) => {
            setRole(slug);
            setChanging(false);
          }}
        />
      )}

      {!data.needs_choice && !data.has_skills && (
        <div className="rounded-xl border border-border-token bg-surface-muted p-4 text-sm">
          <p>{t("noSkills")}</p>
          <ButtonLink href="/profile" size="sm" variant="secondary" className="mt-3">
            {t("addSkills")}
          </ButtonLink>
        </div>
      )}

      {!data.needs_choice && steps.length === 0 && (
        <p className="text-sm text-muted">{t("noSteps")}</p>
      )}

      {steps.length > 0 && (
        <ul className="space-y-4">
          {steps.map((step) => (
            <StepCard
              key={step.role.slug}
              step={step}
              anchorName={data.anchor?.job_role ?? ""}
              hasSkills={data.has_skills}
            />
          ))}
        </ul>
      )}

      {!data.needs_choice && <p className="text-xs text-muted">{t("note")}</p>}
    </div>
  );
}

function RoleFinder({ intro, onChoose }: { intro: string; onChoose: (slug: string) => void }) {
  const t = useTranslations("careerPaths");
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());

  // The same key and fetcher the profile's role picker uses, so a role found
  // there is already cached here.
  const hits = useQuery({
    queryKey: ["role-search", deferred],
    enabled: deferred.length > 0,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q: deferred, limit: 8 } } })).data ??
      [],
  });

  return (
    <div className="space-y-3 rounded-xl border border-border-token bg-surface p-4">
      <p className="text-sm">{intro}</p>
      <label className="block text-sm">
        <span className="font-medium">{t("searchLabel")}</span>
        <Text
          type="search"
          value={query}
          placeholder={t("searchPlaceholder")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {deferred.length > 0 && hits.data && hits.data.length === 0 && (
        <p className="text-sm text-muted">{t("noRoles")}</p>
      )}
      {hits.data && hits.data.length > 0 && (
        <ul className="rounded-lg border border-border-token">
          {hits.data.map((hit: RoleHit) => (
            <li key={hit.slug} className="border-t border-border-token first:border-t-0">
              <button
                type="button"
                onClick={() => onChoose(hit.slug)}
                className="flex w-full flex-col items-start gap-0.5 px-3 py-2.5 text-left hover:bg-surface-muted"
              >
                <span className="text-sm font-medium">{hit.job_role}</span>
                <span className="text-xs text-muted">
                  {hit.nsqf_level != null ? t("level", { level: hit.nsqf_level }) : ""}
                  {hit.sector_name ? ` · ${hit.sector_name}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StepCard({
  step,
  anchorName,
  hasSkills,
}: {
  step: Step;
  anchorName: string;
  hasSkills: boolean;
}) {
  const t = useTranslations("careerPaths");
  const tm = useTranslations("matchesPage");
  const [open, setOpen] = useState(false);
  const missing = step.missing ?? [];
  const courses = step.courses ?? [];
  const entry = step.entry;

  return (
    <li className="rounded-xl border border-border-token bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold">{step.role.job_role}</h3>
          <p className="text-sm text-muted">
            {t("level", { level: step.role.nsqf_level })}
            {step.role.sector_name ? ` · ${step.role.sector_name}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {step.basis.same_occupation && <Badge tone="brand">{t("sameOccupation")}</Badge>}
          {step.basis.shared_nco && <Badge tone="brand">{t("sharedNco")}</Badge>}
        </div>
      </div>

      <p className="mt-2 text-sm">
        {t("basis", {
          shared: step.basis.shared_standards,
          total: step.basis.compulsory_count,
          role: anchorName,
        })}
      </p>

      {hasSkills && (
        <div className="mt-3">
          <CoverageBar
            coverage={step.coverage}
            missingMandatory={step.missing_mandatory}
            capped={step.missing_mandatory > 0 && step.score <= 45}
          />
        </div>
      )}

      <Button
        variant="secondary"
        size="sm"
        className="mt-3"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? t("hide") : t("whatItTakes")}
      </Button>

      {open && (
        <div className="mt-3 space-y-4 border-t border-border-token pt-4">
          {missing.length === 0 ? (
            <p className="text-sm">{t("nothingMissing")}</p>
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

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {t("entryHeading")}
            </p>
            {entry ? (
              <div className="mt-1.5 space-y-1 text-sm">
                {entry.education_options.length > 0 && (
                  <p>{t("education", { options: entry.education_options.join(", ") })}</p>
                )}
                {entry.lowest_experience_years != null && (
                  <p>{t("experience", { years: entry.lowest_experience_years })}</p>
                )}
              </div>
            ) : (
              <p className="mt-1.5 text-sm text-muted">{t("noEntry")}</p>
            )}
          </div>
        </div>
      )}
    </li>
  );
}
