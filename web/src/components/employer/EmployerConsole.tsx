"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { CoverageBar } from "@/components/CoverageBar";
import { Badge, Card, CardBody, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

/**
 * The employer side of the same engine.
 *
 * Every number on this screen comes back from `score_match` — the identical
 * function that ranks jobs for a candidate, called with its arguments the other
 * way round. Nothing is computed here, because a figure derived in the browser
 * can disagree with the score it claims to explain.
 *
 * The only thing assumed is *which employer you are*, and the banner says so.
 */

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div>
      <p className="text-2xl font-bold tabular-nums tracking-tight">{value}</p>
      <p className="mt-0.5 text-xs text-muted">{label}</p>
    </div>
  );
}

function CandidateList({
  employer,
  jobSlug,
}: {
  employer: string;
  jobSlug: string;
}) {
  const t = useTranslations("employerConsole");

  const q = useQuery({
    queryKey: ["employer-candidates", employer, jobSlug],
    queryFn: async () => {
      const { data, error } = await api.GET(
        "/employer/{slug}/jobs/{job_slug}/candidates",
        {
          params: {
            path: { slug: employer, job_slug: jobSlug },
            query: { limit: 20 },
          },
        },
      );
      // openapi-fetch resolves rather than throws on a non-2xx, so an error
      // left unchecked arrives as an empty shortlist — which reads as "nobody
      // matches" when the truth is that the request failed.
      if (error || !data) throw new Error("candidate ranking failed");
      return data;
    },
    retry: false,
  });

  if (q.isPending) {
    return (
      <ul className="space-y-2">
        {[0, 1, 2].map((i) => (
          <li key={i}>
            <Skeleton className="h-20 w-full rounded-lg" />
          </li>
        ))}
      </ul>
    );
  }
  if (q.isError) return <p className="text-sm text-muted">{t("loadError")}</p>;

  const items = q.data?.items ?? [];
  if (items.length === 0)
    return <p className="text-sm text-muted">{t("emptyPool")}</p>;

  return (
    <ul className="space-y-2">
      {items.map((c) => {
        const missing = c.missing ?? [];
        const mandatoryGaps = missing.filter((m) => m.is_mandatory);
        return (
          <li
            key={c.reference}
            className="rounded-lg border border-border-token p-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                  <span className="font-mono text-xs text-muted">
                    {c.reference}
                  </span>
                  {c.missing_mandatory === 0 ? (
                    <Badge tone="good">{t("ready")}</Badge>
                  ) : c.missing_mandatory === 1 ? (
                    <Badge tone="warn">{t("nearly")}</Badge>
                  ) : null}
                </p>
                <p className="mt-1 text-sm">{c.headline}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {[c.location_district, c.location_state]
                    .filter(Boolean)
                    .join(", ")}
                  {" · "}
                  {t("years", { years: c.years_experience })}
                </p>
              </div>
              <span className="shrink-0 text-right">
                <span className="text-lg font-bold tabular-nums">
                  {c.score}
                </span>
                <span className="text-xs text-muted">/100</span>
              </span>
            </div>

            <div className="mt-3">
              <CoverageBar
                coverage={c.coverage}
                missingMandatory={c.missing_mandatory}
                capped={c.capped_by_mandatory}
              />
              <p className="mt-1 text-xs text-muted">
                {t("coverage", {
                  held: (c.matched ?? []).length,
                  total: (c.matched ?? []).length + missing.length,
                })}
              </p>
            </div>

            {mandatoryGaps.length > 0 && (
              <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                {t("missingMandatory")}:{" "}
                {mandatoryGaps.map((m) => m.name_en).join(" · ")}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function EmployerConsole() {
  const t = useTranslations("employerConsole");
  const locale = useLocale();
  const isHi = locale === "hi";
  const [employer, setEmployer] = useState<string | null>(null);
  const [openJob, setOpenJob] = useState<string | null>(null);

  const employers = useQuery({
    queryKey: ["employers"],
    queryFn: async () => {
      const { data, error } = await api.GET("/employer/employers");
      if (error || !data) throw new Error("employer list failed");
      return data;
    },
    retry: false,
  });

  // Whichever employer is picked, defaulting to the first the API returns
  // rather than a slug hardcoded here — a seed change should not blank the page.
  const slug = employer ?? employers.data?.[0]?.slug ?? null;

  const overview = useQuery({
    queryKey: ["employer-overview", slug],
    enabled: slug !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/employer/{slug}/overview", {
        params: { path: { slug: slug as string } },
      });
      if (error || !data) throw new Error("employer overview failed");
      return data;
    },
    retry: false,
  });

  if (employers.isError || overview.isError) {
    return (
      <p className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
        {t("loadError")}
      </p>
    );
  }

  const jobs = overview.data?.jobs ?? [];
  const scarce = overview.data?.scarce ?? [];

  return (
    <div className="space-y-6">
      {/* Visible without scrolling, and above the data rather than beneath it:
          nobody should read a shortlist and only afterwards learn what it is. */}
      <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
        <p className="font-semibold">{t("demoTitle")}</p>
        <p className="mt-1">{t("demoBody")}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">
          {t("actingAs")}
        </span>
        {employers.isPending && <Skeleton className="h-8 w-40 rounded-lg" />}
        {(employers.data ?? []).map((e) => (
          <button
            key={e.slug}
            type="button"
            onClick={() => {
              setEmployer(e.slug);
              setOpenJob(null);
            }}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              e.slug === slug
                ? "border-brand bg-accent-soft font-medium text-brand"
                : "border-border-token text-muted hover:text-foreground"
            }`}
          >
            {e.name}
          </button>
        ))}
      </div>

      {overview.isPending ? (
        <Skeleton className="h-28 w-full rounded-xl" />
      ) : (
        <Card>
          <CardBody className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat value={jobs.length} label={t("openRoles")} />
            <Stat
              value={jobs.reduce((n, j) => n + j.ready, 0)}
              label={t("readyTotal")}
            />
            <Stat
              value={jobs.reduce((n, j) => n + j.nearly, 0)}
              label={t("nearlyTotal")}
            />
            <Stat
              value={overview.data?.candidates_total ?? 0}
              label={t("candidatesTotal")}
            />
          </CardBody>
        </Card>
      )}

      <div>
        <h2 className="text-lg font-semibold">{t("rolesHeading")}</h2>
        <p className="mt-1 text-sm text-muted">{t("rolesNote")}</p>
        <ul className="mt-4 space-y-3">
          {overview.isPending &&
            [0, 1, 2].map((i) => (
              <li key={i}>
                <Skeleton className="h-24 w-full rounded-xl" />
              </li>
            ))}
          {jobs.map((j) => {
            const open = openJob === j.job.slug;
            return (
              <li key={j.job.slug}>
                <Card>
                  <CardBody>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold">
                          {isHi && j.job.title_hi
                            ? j.job.title_hi
                            : j.job.title_en}
                        </h3>
                        <p className="mt-0.5 text-sm text-muted">
                          {[j.job.location_district, j.job.location_state]
                            .filter(Boolean)
                            .join(", ")}
                          {j.job.nsqf_level_min != null &&
                            ` · ${t("levelMin", { level: j.job.nsqf_level_min })}`}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="good">
                          {t("readyCount", { count: j.ready })}
                        </Badge>
                        <Badge tone="warn">
                          {t("nearlyCount", { count: j.nearly })}
                        </Badge>
                        <Badge>{t("poolCount", { count: j.pool })}</Badge>
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-4">
                      <button
                        type="button"
                        onClick={() => setOpenJob(open ? null : j.job.slug)}
                        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline"
                      >
                        {open ? t("hideShortlist") : t("viewShortlist")}
                      </button>
                      <Link
                        href={`/jobs/${j.job.slug}`}
                        className="text-sm text-muted underline-offset-4 hover:underline"
                      >
                        {t("viewJob")}
                      </Link>
                    </div>

                    {open && slug && (
                      <div className="mt-4 border-t border-border-token pt-4">
                        <CandidateList employer={slug} jobSlug={j.job.slug} />
                      </div>
                    )}
                  </CardBody>
                </Card>
              </li>
            );
          })}
        </ul>
      </div>

      {scarce.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold">{t("scarcityHeading")}</h2>
          <p className="mt-1 text-sm text-muted">{t("scarcityNote")}</p>
          <Card className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[32rem] text-sm">
              <thead>
                <tr className="border-b border-border-token text-left text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-semibold">{t("standard")}</th>
                  <th className="px-5 py-3 text-right font-semibold">
                    {t("requiredBy")}
                  </th>
                  <th className="px-5 py-3 text-right font-semibold">
                    {t("heldBy")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {scarce.map((s) => (
                  <tr
                    key={s.nos_code ?? s.name_en}
                    className="border-b border-border-token last:border-0"
                  >
                    <td className="px-5 py-3">
                      <span>{s.name_en}</span>
                      {s.nos_code && (
                        <span className="ml-2 font-mono text-[11px] text-muted">
                          {s.nos_code}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {s.required_by}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums">
                      {s.held_by === 0 ? (
                        <Badge tone="bad">{s.held_by}</Badge>
                      ) : (
                        s.held_by
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  );
}
