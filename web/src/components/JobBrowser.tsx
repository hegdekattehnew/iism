"use client";

import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { JobCard } from "@/components/cards/JobCard";
import { Button, ListSkeleton, Skeleton } from "@/components/ui";
import { ChipButton, ChipRow, ChipSelect } from "@/components/ui/chip";
import { api } from "@/lib/api";
import type { JobCardData } from "@/lib/job-text";
import { useMyScores } from "@/lib/matches";
import { EMPLOYMENT_TYPES as TYPES } from "@/lib/profile";
import { EmptyState } from "@/components/ui/empty-state";
import { BriefcaseIcon } from "@/components/ui/icons";

/** A page. Small enough to arrive quickly on mobile data; the total says how many more there are. */
export const JOBS_PAGE_SIZE = 24;

export function JobBrowser({
  initialSkill = "",
  initialQuery = "",
}: {
  initialSkill?: string;
  /** From `?q=`: the search results page links here with its query. */
  initialQuery?: string;
}) {
  const t = useTranslations("jobsPage");
  const { scores, isSeeker } = useMyScores();

  const [query, setQuery] = useState(initialQuery);
  const [type, setType] = useState("");
  const [state, setState] = useState("");
  // Per visit, never remembered: the title order is the default everyone (and the released app) gets.
  const [sort, setSort] = useState<"title" | "newest">("title");
  const deferred = useDeferredValue(query.trim());

  const results = useInfiniteQuery({
    queryKey: ["jobs", { q: deferred, type, state, skill: initialSkill, sort }],
    placeholderData: keepPreviousData,
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/jobs", {
        params: {
          query: {
            limit: JOBS_PAGE_SIZE,
            offset: pageParam,
            ...(sort === "newest" ? { sort } : {}),
            ...(deferred ? { q: deferred } : {}),
            ...(type ? { employment_type: type as (typeof TYPES)[number] } : {}),
            ...(state ? { location_state: state } : {}),
            ...(initialSkill ? { skill: initialSkill } : {}),
          },
        },
      });
      // openapi-fetch resolves on a non-2xx; an answer with no body is a failure, not "no jobs".
      if (!data) throw new Error("jobs");
      return data;
    },
    getNextPageParam: (last) => {
      const seen = last.offset + last.items.length;
      return last.items.length > 0 && seen < last.total ? seen : undefined;
    },
  });

  // The states that have an open vacancy and how many: a fact about the whole catalogue, not about
  // whichever page happens to be on screen (it used to be read off the first 200 rows).
  const facet = useQuery({
    queryKey: ["job-states"],
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const { data } = await api.GET("/jobs/states");
      return data ?? [];
    },
  });

  const rows = (results.data?.pages ?? []).flatMap((p) => p.items) as JobCardData[];
  // The server's figure. `rows.length` is the length of what has loaded, which is a page.
  const total = results.data?.pages[0]?.total ?? 0;
  const left = Math.max(0, total - rows.length);
  const states = facet.data ?? [];

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
          <ChipSelect label={t("allTypes")} active={type !== ""} value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">{t("allTypes")}</option>
            {TYPES.map((ty) => (
              <option key={ty} value={ty}>
                {t(`employmentType.${ty}`)}
              </option>
            ))}
          </ChipSelect>
          <ChipSelect label={t("allStates")} active={state !== ""} value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">{t("allStates")}</option>
            {states.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name} ({s.count})
              </option>
            ))}
          </ChipSelect>
          {/* Always drawn, so the row is the same shape before and after the list arrives. */}
          <ChipSelect
            label={t("sortLabel")}
            active={sort !== "title"}
            value={sort}
            onChange={(e) => setSort(e.target.value as "title" | "newest")}
          >
            <option value="title">{t("sortTitle")}</option>
            <option value="newest">{t("sortNewest")}</option>
          </ChipSelect>
          {(query || type || state) && (
            <ChipButton
              onClick={() => {
                setQuery("");
                setType("");
                setState("");
              }}
            >
              {t("clear")}
            </ChipButton>
          )}
        </ChipRow>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        {results.isPending ? (
          <Skeleton className="h-5 w-32" />
        ) : (
          <p className="text-sm text-muted" aria-live="polite">
            {t("resultsCount", { count: total })}
          </p>
        )}
      </div>

      {results.isError && (
        <p className="mt-6 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("loadError")}
        </p>
      )}
      {!results.isError && !results.isPending && rows.length === 0 && (
        <EmptyState icon={BriefcaseIcon} title={t("noResults")} className="mt-8" />
      )}

      {results.isPending && <ListSkeleton />}

      <ul className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
        {rows.map((j) => (
          <li key={j.slug}>
            <JobCard job={j} score={scores.get(j.slug)} scoreSlot={isSeeker} />
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
            {results.isFetchNextPageError
              ? t("retry")
              : t("showMore", { left: left })}
          </Button>
        </div>
      )}
    </div>
  );
}
