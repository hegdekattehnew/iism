"use client";

import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button, ListSkeleton, Skeleton } from "@/components/ui";
import { COURSE_MODES as MODES, CourseCard, type Course } from "@/components/cards/CourseCard";
import { ChipButton, ChipRow, ChipSelect } from "@/components/ui/chip";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { BookOpenIcon } from "@/components/ui/icons";

const LANGS = ["en", "hi"] as const;
const FEE_CAPS = [2000, 5000, 10000] as const;

/** A page. The total says how many more there are; the list used to ask for 200 and stop. */
export const COURSES_PAGE_SIZE = 24;

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function CourseBrowser({ initialSkill = "" }: { initialSkill?: string }) {
  const t = useTranslations("coursesPage");

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

  return (
    <div>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("searchPlaceholder")}
        aria-label={t("searchPlaceholder")}
        className="w-full rounded-lg border border-border-token bg-surface px-4 py-3 text-base placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      />
      <div className="mt-3">
        <ChipRow label={t("filters")}>
          <ChipSelect label={t("allModes")} active={mode !== ""} value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">{t("allModes")}</option>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {t(`mode.${m}`)}
              </option>
            ))}
          </ChipSelect>
          <ChipSelect
            label={t("allLanguages")}
            active={language !== ""}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="">{t("allLanguages")}</option>
            {LANGS.map((l) => (
              <option key={l} value={l}>
                {t(`language.${l}`)}
              </option>
            ))}
          </ChipSelect>
          <ChipSelect label={t("anyFee")} active={maxFee !== ""} value={maxFee} onChange={(e) => setMaxFee(e.target.value)}>
            <option value="">{t("anyFee")}</option>
            {FEE_CAPS.map((f) => (
              <option key={f} value={String(f)}>
                {t("under", { amount: inr(f) })}
              </option>
            ))}
          </ChipSelect>
          {(query || mode || language || maxFee) && (
            <ChipButton
              onClick={() => {
                setQuery("");
                setMode("");
                setLanguage("");
                setMaxFee("");
              }}
            >
              {t("clear")}
            </ChipButton>
          )}
        </ChipRow>
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
            <CourseCard course={c} />
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
