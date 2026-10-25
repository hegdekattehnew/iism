"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { PublicBatchCard } from "@/components/cards/PublicBatchCard";
import { RegisterBatch } from "@/components/RegisterBatch";
import { Button, Skeleton } from "@/components/ui";
import { ChipRow, ChipSelect } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { CalendarIcon } from "@/components/ui/icons";
import { api } from "@/lib/api";
import { useIsSignedIn } from "@/lib/auth";
import { usePublicBatches, type PublicFilters } from "@/lib/batches";

const START_WITHIN = ["7", "14", "30", "90"] as const;
const MAX_FEES = ["0", "2000", "5000", "10000"] as const;
const MODES = ["in_person", "hybrid", "online"] as const;

function useStates() {
  return useQuery({
    queryKey: ["geography", "states"] as const,
    queryFn: async () => {
      const { data, error } = await api.GET("/geography/states");
      if (error || !data) throw new Error("states");
      return data;
    },
    staleTime: Infinity,
  });
}

function useDistricts(stateId: string) {
  return useQuery({
    queryKey: ["geography", "districts", stateId] as const,
    enabled: stateId !== "",
    queryFn: async () => {
      const { data, error } = await api.GET("/geography/districts", {
        params: { query: { state_id: stateId } },
      });
      if (error || !data) throw new Error("districts");
      return data;
    },
    staleTime: Infinity,
  });
}

/**
 * Batches near you (Sprint 100, BL-20.2). The server orders them **by how near they are, then by
 * how soon they start, then by what they cost**, and nothing is hidden by where the person is: a
 * batch in another state is last and labelled, never gone. A signed-in learner's own places order the
 * list; a visitor can say where they are with the state and district chips (which also narrow it).
 * Every chip is a native select (a phone opens its own picker), and the count is the server's.
 */
export function BatchBrowser({ course }: { course?: string }) {
  const t = useTranslations("publicBatches");
  const signedIn = useIsSignedIn();
  const [filters, setFilters] = useState<PublicFilters>({
    stateId: "",
    districtId: "",
    startsWithin: "",
    maxFee: "",
    mode: "",
    course,
  });
  const set = (patch: Partial<PublicFilters>) => setFilters((f) => ({ ...f, ...patch }));
  const states = useStates();
  const districts = useDistricts(filters.stateId);
  const list = usePublicBatches(filters, signedIn);
  const rows = list.data?.pages.flatMap((p) => p.items) ?? [];
  const total = list.data?.pages[0]?.total ?? 0;

  return (
    <div className="mt-8 space-y-6">
      <ChipRow label={t("filtersLabel")}>
        <ChipSelect
          label={t("state")}
          active={filters.stateId !== ""}
          value={filters.stateId}
          onChange={(e) => set({ stateId: e.target.value, districtId: "" })}
        >
          <option value="">{t("anyState")}</option>
          {(states.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </ChipSelect>
        {filters.stateId !== "" && (
          <ChipSelect
            label={t("district")}
            active={filters.districtId !== ""}
            value={filters.districtId}
            onChange={(e) => set({ districtId: e.target.value })}
          >
            <option value="">{t("anyDistrict")}</option>
            {(districts.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </ChipSelect>
        )}
        <ChipSelect
          label={t("startsWithin")}
          active={filters.startsWithin !== ""}
          value={filters.startsWithin}
          onChange={(e) => set({ startsWithin: e.target.value })}
        >
          <option value="">{t("anyStart")}</option>
          {START_WITHIN.map((d) => (
            <option key={d} value={d}>
              {t("withinDays", { days: d })}
            </option>
          ))}
        </ChipSelect>
        <ChipSelect
          label={t("maxFee")}
          active={filters.maxFee !== ""}
          value={filters.maxFee}
          onChange={(e) => set({ maxFee: e.target.value })}
        >
          <option value="">{t("anyFee")}</option>
          {MAX_FEES.map((f) => (
            <option key={f} value={f}>
              {f === "0" ? t("feeFree") : t("upTo", { amount: f })}
            </option>
          ))}
        </ChipSelect>
        <ChipSelect
          label={t("modeLabel")}
          active={filters.mode !== ""}
          value={filters.mode}
          onChange={(e) => set({ mode: e.target.value })}
        >
          <option value="">{t("anyMode")}</option>
          {MODES.map((m) => (
            <option key={m} value={m}>
              {t(`mode.${m}`)}
            </option>
          ))}
        </ChipSelect>
      </ChipRow>

      {list.isPending ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : list.isError ? (
        <p className="text-sm text-muted">{t("loadFailed")}</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={CalendarIcon} title={t("empty")}>
          {t("emptyHint")}
        </EmptyState>
      ) : (
        <>
          <p className="text-sm text-muted" role="status">
            {t("count", { total })}
          </p>
          <ul className="space-y-3">
            {rows.map((b) => (
              <li key={b.id}>
                <PublicBatchCard batch={b} footer={<RegisterBatch batch={b} />} />
              </li>
            ))}
          </ul>
          {list.hasNextPage && (
            <Button
              variant="secondary"
              disabled={list.isFetchingNextPage}
              onClick={() => list.fetchNextPage()}
            >
              {t("showMore", { left: total - rows.length })}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
