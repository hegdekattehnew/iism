"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

const MODES = ["online", "offline", "hybrid"] as const;
const LANGS = ["en", "hi"] as const;
const FEE_CAPS = [2000, 5000, 10000] as const;

type Course = {
  slug: string;
  title_en: string;
  title_hi?: string | null;
  description_en?: string | null;
  description_hi?: string | null;
  mode: (typeof MODES)[number];
  language: "en" | "hi" | "both";
  duration_hours?: number | null;
  fee_inr?: number | null;
  nsqf_level?: number | null;
  tenant: { name: string; city?: string | null };
};

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function feeLabel(
  c: Course,
  t: ReturnType<typeof useTranslations<"coursesPage">>,
) {
  if (c.fee_inr == null || c.fee_inr === 0) return t("feeFree");
  return t("fee", { amount: inr(c.fee_inr) });
}

export function CourseBrowser({ initialSkill = "" }: { initialSkill?: string }) {
  const t = useTranslations("coursesPage");
  const isHi = useLocale() === "hi";

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("");
  const [language, setLanguage] = useState("");
  const [maxFee, setMaxFee] = useState("");
  const deferred = useDeferredValue(query.trim());

  const results = useQuery({
    queryKey: ["courses", { q: deferred, mode, language, maxFee, skill: initialSkill }],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data } = await api.GET("/courses", {
        params: {
          query: {
            limit: 200,
            ...(deferred ? { q: deferred } : {}),
            ...(mode ? { mode: mode as (typeof MODES)[number] } : {}),
            ...(language ? { language: language as (typeof LANGS)[number] } : {}),
            ...(maxFee ? { max_fee_inr: Number(maxFee) } : {}),
            ...(initialSkill ? { skill: initialSkill } : {}),
          },
        },
      });
      return (data?.items ?? []) as Course[];
    },
  });

  const rows = results.data ?? [];
  const title = (c: Course) => (isHi && c.title_hi ? c.title_hi : c.title_en);
  const desc = (c: Course) =>
    isHi && c.description_hi ? c.description_hi : c.description_en;

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("searchPlaceholder")}
          className="w-full flex-1 rounded-lg border border-border-token bg-surface px-4 py-3 text-base placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        />
        <select
          aria-label={t("allModes")}
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allModes")}</option>
          {MODES.map((m) => (
            <option key={m} value={m}>
              {t(`mode.${m}`)}
            </option>
          ))}
        </select>
        <select
          aria-label={t("allLanguages")}
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allLanguages")}</option>
          {LANGS.map((l) => (
            <option key={l} value={l}>
              {t(`language.${l}`)}
            </option>
          ))}
        </select>
        <select
          aria-label={t("anyFee")}
          value={maxFee}
          onChange={(e) => setMaxFee(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("anyFee")}</option>
          {FEE_CAPS.map((f) => (
            <option key={f} value={String(f)}>
              {t("under", { amount: inr(f) })}
            </option>
          ))}
        </select>
        {(query || mode || language || maxFee) && (
          <Button
            variant="secondary"
            onClick={() => {
              setQuery("");
              setMode("");
              setLanguage("");
              setMaxFee("");
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
        {rows.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/courses/${c.slug}`}
              className="block h-full rounded-xl border border-border-token bg-surface p-5 transition-colors hover:border-brand"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-brand">
                  {t(`mode.${c.mode}`)}
                </span>
                <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                  {t(`language.${c.language}`)}
                </span>
                {c.nsqf_level != null && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                    {t("level", { level: c.nsqf_level })}
                  </span>
                )}
              </div>
              <h2 className="mt-2.5 text-base font-semibold">{title(c)}</h2>
              <p className="text-sm text-muted">{c.tenant.name}</p>
              {desc(c) && (
                <p className="mt-2 line-clamp-2 text-sm text-muted">{desc(c)}</p>
              )}
              <p className="mt-3 text-xs font-medium">
                {feeLabel(c, t)}
                {c.duration_hours != null && (
                  <span className="font-normal text-muted">
                    {" · "}
                    {t("duration", { hours: c.duration_hours })}
                  </span>
                )}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
