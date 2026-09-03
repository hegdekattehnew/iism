"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

const TYPES = ["full_time", "part_time", "contract", "apprenticeship"] as const;

type Job = {
  slug: string;
  title_en: string;
  title_hi?: string | null;
  description_en?: string | null;
  description_hi?: string | null;
  location_state?: string | null;
  location_district?: string | null;
  employment_type: (typeof TYPES)[number];
  experience_min_years: number;
  experience_max_years?: number | null;
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
  nsqf_level_min?: number | null;
  tenant: { name: string; city?: string | null };
};

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function experienceLabel(
  j: Job,
  t: ReturnType<typeof useTranslations<"jobsPage">>,
) {
  if (j.experience_min_years === 0 && !j.experience_max_years)
    return t("experienceNone");
  if (j.experience_max_years)
    return t("experienceRange", {
      min: j.experience_min_years,
      max: j.experience_max_years,
    });
  return t("experience", { min: j.experience_min_years });
}

export function salaryLabel(
  j: Job,
  t: ReturnType<typeof useTranslations<"jobsPage">>,
) {
  if (j.salary_min_inr && j.salary_max_inr)
    return t("salary", { min: inr(j.salary_min_inr), max: inr(j.salary_max_inr) });
  if (j.salary_min_inr) return t("salaryFrom", { min: inr(j.salary_min_inr) });
  return t("salaryUndisclosed");
}

export function JobBrowser({ initialSkill = "" }: { initialSkill?: string }) {
  const t = useTranslations("jobsPage");
  const isHi = useLocale() === "hi";

  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  const deferred = useDeferredValue(query.trim());

  const results = useQuery({
    queryKey: ["jobs", { q: deferred, type, state, skill: initialSkill }],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data } = await api.GET("/jobs", {
        params: {
          query: {
            limit: 200,
            ...(deferred ? { q: deferred } : {}),
            ...(type ? { employment_type: type as (typeof TYPES)[number] } : {}),
            ...(state ? { location_state: state } : {}),
            ...(initialSkill ? { skill: initialSkill } : {}),
          },
        },
      });
      return (data?.items ?? []) as Job[];
    },
  });

  const rows = results.data ?? [];
  // Derived from the current result set rather than a separate endpoint —
  // there is no facet API yet and this stays correct for the data on screen.
  const states = [...new Set(rows.map((r) => r.location_state).filter(Boolean))].sort();
  const title = (j: Job) => (isHi && j.title_hi ? j.title_hi : j.title_en);
  const desc = (j: Job) =>
    isHi && j.description_hi ? j.description_hi : j.description_en;

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPlaceholder")}
          className="w-full flex-1 rounded-lg border border-border-token bg-surface px-4 py-3 text-base placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        />
        <select
          aria-label={t("allTypes")}
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allTypes")}</option>
          {TYPES.map((ty) => (
            <option key={ty} value={ty}>
              {t(`employmentType.${ty}`)}
            </option>
          ))}
        </select>
        <select
          aria-label={t("allStates")}
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allStates")}</option>
          {states.map((s) => (
            <option key={s} value={s as string}>
              {s}
            </option>
          ))}
        </select>
        {(query || type || state) && (
          <Button
            variant="secondary"
            onClick={() => {
              setQuery("");
              setType("");
              setState("");
            }}
          >
            {t("clear")}
          </Button>
        )}
      </div>

      <p className="mt-4 text-sm text-muted" aria-live="polite">
        {t("resultsCount", { count: rows.length })}
      </p>

      {results.isError && (
        <p className="mt-6 rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {t("loadError")}
        </p>
      )}
      {!results.isError && !results.isPending && rows.length === 0 && (
        <p className="mt-8 text-sm text-muted">{t("noResults")}</p>
      )}

      <ul className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {rows.map((j) => (
          <li key={j.slug}>
            <Link
              href={`/jobs/${j.slug}`}
              className="block h-full rounded-xl border border-border-token bg-surface p-5 transition-colors hover:border-brand"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-brand">
                  {t(`employmentType.${j.employment_type}`)}
                </span>
                {j.nsqf_level_min != null && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                    {t("minLevel", { level: j.nsqf_level_min })}
                  </span>
                )}
              </div>
              <h2 className="mt-2.5 text-base font-semibold">{title(j)}</h2>
              <p className="text-sm text-muted">
                {j.tenant.name}
                {j.location_district ? ` · ${j.location_district}` : ""}
              </p>
              {desc(j) && (
                <p className="mt-2 line-clamp-2 text-sm text-muted">{desc(j)}</p>
              )}
              <p className="mt-3 text-xs text-muted">
                {experienceLabel(j, t)} · {salaryLabel(j, t)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
