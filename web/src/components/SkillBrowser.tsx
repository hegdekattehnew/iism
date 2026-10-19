"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { lookalikeNames, StandardCard, type StandardRow } from "@/components/cards/StandardCard";
import { Button, ListSkeleton, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { SearchIcon } from "@/components/ui/icons";

// One screenful on a phone, and a small enough payload to stay quick on mobile
// data. The taxonomy is 21k rows: fetching it all and filtering in the browser
// does not degrade at that size, it breaks.
const PAGE_SIZE = 24;

type Row = StandardRow & { skill_type: "technical" | "core" | "generic" };

export function SkillBrowser({ initialQuery = "" }: { initialQuery?: string }) {
  const t = useTranslations("skillsPage");

  const [query, setQuery] = useState(initialQuery);
  const [type, setType] = useState<string>("");
  const [level, setLevel] = useState<string>("");
  const [offset, setOffset] = useState(0);
  // Keeps typing responsive: the input updates immediately, the request lags.
  const deferred = useDeferredValue(query.trim());

  const searching = deferred.length > 0;

  // Any change to what is being asked for invalidates the position in the
  // result set: narrowing a filter while on page 40 would otherwise land on an
  // empty page that reads as "no results" rather than as a paging artefact.
  // Done in the handlers rather than an effect — React 19's
  // react-hooks/set-state-in-effect rejects the effect form outright.
  const changeQuery = (v: string) => {
    setQuery(v);
    setOffset(0);
  };
  const changeType = (v: string) => {
    setType(v);
    setOffset(0);
  };
  const changeLevel = (v: string) => {
    setLevel(v);
    setOffset(0);
  };

  // The filter options come from the data, not a hardcoded list. 8,055 skills
  // sit at half-levels — a 1..10 dropdown silently hides 38% of the taxonomy.
  const facets = useQuery({
    queryKey: ["skill-facets"],
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const { data } = await api.GET("/skills/facets", {});
      return data ?? null;
    },
  });

  const results = useQuery({
    queryKey: ["skills", { q: deferred, type, level, offset }],
    placeholderData: keepPreviousData,
    queryFn: async (): Promise<{ rows: Row[]; total: number; capped: boolean }> => {
      if (searching) {
        const { data } = await api.GET("/skills/search", {
          params: { query: { q: deferred, limit: 50 } },
        });
        let rows = (data ?? []) as Row[];
        const capped = rows.length >= 50;
        // Ranked relevance cannot be paged with offset/limit without losing the
        // ranking, so search stays a single capped page and filters apply to it.
        if (type) rows = rows.filter((r) => r.skill_type === type);
        if (level) rows = rows.filter((r) => String(r.nsqf_level ?? "") === level);
        return { rows, total: rows.length, capped };
      }
      const { data } = await api.GET("/skills", {
        params: {
          query: {
            limit: PAGE_SIZE,
            offset,
            ...(type ? { skill_type: type as Row["skill_type"] } : {}),
            ...(level ? { nsqf_level: Number(level) } : {}),
          },
        },
      });
      return {
        rows: (data?.items ?? []) as Row[],
        total: data?.total ?? 0,
        capped: false,
      };
    },
  });

  const rows = results.data?.rows ?? [];
  const total = results.data?.total ?? 0;
  const lookalikes = lookalikeNames(rows);
  // Levels arrive as numbers: 4 renders as "4", 4.5 as "4.5". A trailing ".0"
  // on every whole level is noise on a chip.
  const fmtLevel = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

  const hasPrev = !searching && offset > 0;
  const hasNext = !searching && offset + rows.length < total;

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <label htmlFor="skill-search" className="sr-only">
            {t("searchLabel")}
          </label>
          <input
            id="skill-search"
            type="search"
            value={query}
            onChange={(e) => changeQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded-lg border border-border-token bg-surface px-4 py-3 text-base placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          />
        </div>

        <select
          aria-label={t("allTypes")}
          value={type}
          onChange={(e) => changeType(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allTypes")}</option>
          {(facets.data?.types ?? []).map((ty) => (
            <option key={ty.skill_type} value={ty.skill_type}>
              {t("typeWithCount", {
                type: t(`type.${ty.skill_type}`),
                count: ty.count,
              })}
            </option>
          ))}
        </select>

        <select
          aria-label={t("allLevels")}
          value={level}
          onChange={(e) => changeLevel(e.target.value)}
          className="rounded-lg border border-border-token bg-surface px-3 py-3 text-sm"
        >
          <option value="">{t("allLevels")}</option>
          {(facets.data?.levels ?? []).map((lv) => (
            <option key={lv.level} value={String(lv.level)}>
              {t("levelWithCount", {
                level: fmtLevel(lv.level),
                count: lv.count,
              })}
            </option>
          ))}
        </select>

        {(query || type || level) && (
          <Button
            variant="secondary"
            onClick={() => {
              setQuery("");
              setType("");
              setLevel("");
              setOffset(0);
            }}
          >
            {t("clear")}
          </Button>
        )}
      </div>

      {results.isPending && <Skeleton className="mt-4 h-5 w-32" />}
      <p className="mt-4 text-sm text-muted" aria-live="polite" hidden={results.isPending}>
        {results.isFetching && searching
          ? t("searching")
          : searching
            ? t("resultsCount", { count: rows.length })
            : total > 0
              ? t("showingRange", {
                  from: offset + 1,
                  to: offset + rows.length,
                  total,
                })
              : t("resultsCount", { count: 0 })}
      </p>

      {/* A capped, ranked result set is not the same as "these are all of them". */}
      {searching && results.data?.capped && (
        <p className="mt-1 text-xs text-muted">{t("searchCapped", { count: 50 })}</p>
      )}
      {searching && (type || level) && (
        <p className="mt-1 text-xs text-muted">{t("filtersOnSearch")}</p>
      )}

      {results.isError && (
        <p className="mt-6 rounded-lg border border-danger-border bg-danger-surface p-4 text-sm text-danger-text">
          {t("loadError")}
        </p>
      )}

      {!results.isError && rows.length === 0 && !results.isPending && (
        <EmptyState icon={SearchIcon} title={t("noResults")} className="mt-8" />
      )}

      {results.isPending && <ListSkeleton className="md:grid-cols-2 lg:grid-cols-2" />}

      <ul className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2">
        {rows.map((r) => (
          <li key={r.slug}>
            <StandardCard row={r} lookalike={lookalikes.has(r.name.trim().toLowerCase())} />
          </li>
        ))}
      </ul>

      {(hasPrev || hasNext) && (
        <div className="mt-8 flex items-center justify-center gap-3">
          <Button
            variant="secondary"
            disabled={!hasPrev}
            onClick={() => {
              setOffset((o) => Math.max(0, o - PAGE_SIZE));
              window.scrollTo({ top: 0 });
            }}
          >
            {t("prevPage")}
          </Button>
          <Button
            variant="secondary"
            disabled={!hasNext}
            onClick={() => {
              setOffset((o) => o + PAGE_SIZE);
              window.scrollTo({ top: 0 });
            }}
          >
            {t("nextPage")}
          </Button>
        </div>
      )}
    </div>
  );
}
