"use client";

import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button, ListSkeleton, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { creditsText, type Translate } from "@/lib/job-text";
import { EmptyState } from "@/components/ui/empty-state";
import { BookOpenIcon } from "@/components/ui/icons";

const MODES = ["online", "offline", "hybrid"] as const;
const LANGS = ["en", "hi"] as const;
const FEE_CAPS = [2000, 5000, 10000] as const;

type Course = {
  slug: string;
  title: string;
  description?: string | null;
  mode: (typeof MODES)[number];
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

/** A page. The total says how many more there are; the list used to ask for 200 and stop. */
export const COURSES_PAGE_SIZE = 24;

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
  const format = useFormatter();

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("");
  const [language, setLanguage] = useState("");
  const [maxFee, setMaxFee] = useState("");
  const deferred = useDeferredValue(query.trim());

  const results = useInfiniteQuery({
    queryKey: ["courses", { q: deferred, mode, language, maxFee, skill: initialSkill }],
    placeholderData: keepPreviousData,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/courses", {
        params: {
          query: {
            limit: COURSES_PAGE_SIZE,
            offset: pageParam,
            ...(deferred ? { q: deferred } : {}),
            ...(mode ? { mode: mode as (typeof MODES)[number] } : {}),
            ...(language ? { language: language as (typeof LANGS)[number] } : {}),
            ...(maxFee ? { max_fee_inr: Number(maxFee) } : {}),
            ...(initialSkill ? { skill: initialSkill } : {}),
          },
        },
      });
      // openapi-fetch resolves on a non-2xx; an answer with no body is a failure, not "no courses".
      if (!data) throw new Error("courses");
      return data;
    },
    getNextPageParam: (last) => {
      const seen = last.offset + last.items.length;
      return last.items.length > 0 && seen < last.total ? seen : undefined;
    },
  });

  const rows = (results.data?.pages ?? []).flatMap((p) => p.items) as Course[];
  // The server's figure; `rows.length` is only what has loaded so far.
  const total = results.data?.pages[0]?.total ?? 0;
  const left = Math.max(0, total - rows.length);
  const title = (c: Course) => (c.title);
  const desc = (c: Course) =>
    c.description;

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

      {results.isPending ? (
        <Skeleton className="mt-4 h-5 w-32" />
      ) : (
        <p className="mt-4 text-sm text-muted" aria-live="polite">
          {t("resultsCount", { count: total })}
        </p>
      )}

      {results.isError && (
        <p className="mt-6 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("loadError")}
        </p>
      )}
      {!results.isError && !results.isPending && rows.length === 0 && (
        <EmptyState icon={BookOpenIcon} title={t("noResults")} className="mt-8" />
      )}

      {results.isPending && <ListSkeleton />}

      <ul className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {rows.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/courses/${c.slug}`}
              className="block h-full rounded-xl border border-border-token bg-surface p-5 transition-colors hover:border-brand"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-brand">
                  {t(`mode.${c.mode}`)}
                </span>
                <span className="rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium text-muted">
                  {t(`language.${c.language}`)}
                </span>
                {c.nsqf_level != null && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium text-muted">
                    {t("level", { level: c.nsqf_level })}
                  </span>
                )}
                {creditsText(c.qualification_credits, t as unknown as Translate) && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium text-muted">
                    {creditsText(c.qualification_credits, t as unknown as Translate)}
                  </span>
                )}
              </div>
              <h2 className="mt-2.5 text-base font-semibold">{title(c)}</h2>
              <p className="text-sm text-muted">{c.tenant.name}</p>
              {(c.location_district || c.location_state || c.starts_on) && (
                <p className="mt-1 text-xs text-muted">
                  {[
                    c.mode === "online"
                      ? null
                      : [c.location_district, c.location_state].filter(Boolean).join(", "),
                    c.starts_on
                      ? t(c.started ? "startedOn" : "startsOn", {
                          date: format.dateTime(new Date(`${c.starts_on}T00:00:00Z`), {
                            dateStyle: "medium",
                            timeZone: "UTC",
                          }),
                        })
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}
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

      {results.isFetchNextPageError && (
        <p className="mt-4 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("loadMoreError")}
        </p>
      )}
      {results.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            disabled={results.isFetchingNextPage}
            onClick={() => void results.fetchNextPage()}
          >
            {results.isFetchNextPageError ? t("retry") : t("showMore", { left })}
          </Button>
        </div>
      )}
    </div>
  );
}
