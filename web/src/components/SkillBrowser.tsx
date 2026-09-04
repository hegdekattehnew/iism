"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

// One screenful on a phone, and a small enough payload to stay quick on mobile
// data. The taxonomy is 21k rows: fetching it all and filtering in the browser
// does not degrade at that size, it breaks.
const PAGE_SIZE = 24;

type Row = {
  slug: string;
  name_en: string;
  name_hi?: string | null;
  description_en?: string | null;
  description_hi?: string | null;
  skill_type: "technical" | "core" | "generic";
  nsqf_level?: number | null;
  qp_count?: number;
  matched_on?: string | null;
  match_kind?: "exact" | "prefix" | "alias" | "text";
};

function TypeChip({ type }: { type: Row["skill_type"] }) {
  const t = useTranslations("skillsPage.type");
  const tone =
    type === "technical"
      ? "bg-accent-soft text-brand"
      : type === "core"
        ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300"
        : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  return (
    <span className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${tone}`}>
      {t(type)}
    </span>
  );
}

export function SkillBrowser({ initialQuery = "" }: { initialQuery?: string }) {
  const t = useTranslations("skillsPage");
  const locale = useLocale();
  const isHi = locale === "hi";

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
  const name = (r: Row) => (isHi && r.name_hi ? r.name_hi : r.name_en);
  const desc = (r: Row) =>
    isHi && r.description_hi ? r.description_hi : r.description_en;

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

      <p className="mt-4 text-sm text-muted" aria-live="polite">
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
        <p className="mt-6 rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {t("loadError")}
        </p>
      )}

      {!results.isError && rows.length === 0 && !results.isPending && (
        <p className="mt-8 text-sm text-muted">{t("noResults")}</p>
      )}

      <ul className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2">
        {rows.map((r) => (
          <li key={r.slug}>
            <Link
              href={`/skills/${r.slug}`}
              className="block h-full rounded-xl border border-border-token bg-surface p-5 transition-colors hover:border-brand"
            >
              <div className="flex flex-wrap items-center gap-2">
                <TypeChip type={r.skill_type} />
                {r.nsqf_level != null && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                    {t("levelShort", { level: fmtLevel(r.nsqf_level) })}
                  </span>
                )}
                {/* Why this sorts where it does, and a real signal of how
                    central the unit is to the framework. */}
                {(r.qp_count ?? 0) > 0 && (
                  <span className="text-[11px] text-muted">
                    {t("usedInQps", { count: r.qp_count ?? 0 })}
                  </span>
                )}
              </div>

              <h2 className="mt-2.5 text-base font-semibold">{name(r)}</h2>
              {isHi && r.name_hi && (
                <p className="text-xs text-muted">{r.name_en}</p>
              )}

              {desc(r) && (
                <p className="mt-1.5 line-clamp-2 text-sm text-muted">{desc(r)}</p>
              )}

              {/* Why this matched. Without it a transliterated hit looks wrong. */}
              {r.matched_on && r.match_kind === "alias" && (
                <p className="mt-3 text-xs text-brand">
                  {t("matchedVia", { term: r.matched_on })}
                </p>
              )}
            </Link>
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
