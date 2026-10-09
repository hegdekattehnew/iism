"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { Select } from "@/components/profile/fields";
import { Skeleton, StatTile } from "@/components/ui";
import { useKnownProgrammes, useProgrammeDistricts, useProgrammeReport } from "@/lib/ops";

/**
 * A government-agency programme's outcomes (Sprint 39, BL-10.5) -- the
 * cheapest story in the epic. `programme_report` has been complete since
 * Sprint 33; only the screen was missing, since no agency login exists yet
 * and an operator views this on the agency's behalf.
 */
export function ProgrammeDashboard() {
  const t = useTranslations("ops.programmeDashboard");
  const [selected, setSelected] = useState<string | null>(null);
  const programmes = useKnownProgrammes();
  const report = useProgrammeReport(selected);
  const districts = useProgrammeDistricts(selected);

  if (programmes.isPending) {
    return <Skeleton className="h-20 w-full" />;
  }

  if (programmes.isError) {
    return <p className="text-sm text-danger-text">{t("failed")}</p>;
  }

  const names = programmes.data ?? [];
  const districtRows = districts.data?.districts ?? [];

  return (
    <div>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>

      {names.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("none")}</p>
      ) : (
        <>
          <Select
            aria-label={t("title")}
            className="mt-4 max-w-xs"
            value={selected ?? ""}
            onChange={(e) => setSelected(e.target.value || null)}
          >
            <option value="">{t("choose")}</option>
            {names.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>

          {report.isError && <p className="mt-4 text-sm text-danger-text">{t("failed")}</p>}

          {report.data && (
            <div className="mt-4 flex flex-wrap gap-x-8 gap-y-4">
              <StatTile value={report.data.enrolled} label={t("enrolled")} />
              <StatTile value={report.data.matched} label={t("matched")} />
              <StatTile value={report.data.applied} label={t("applied")} />
              <StatTile value={report.data.hired} label={t("hired")} />
            </div>
          )}
          {districtRows.length > 0 && (
            <>
              <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
                {t("byDistrict")}
              </h3>
              <RankedBarList
                className="mt-3"
                emptyLabel={t("noDistricts")}
                items={districtRows.map((d) => ({
                  key: d.district,
                  label: d.district,
                  // A count of one to four arrives as `null` and is written, never computed.
                  value: d.enrolled ?? 0,
                  valueLabel:
                    d.enrolled === null || d.enrolled === undefined
                      ? t("fewerThan", { min: districts.data?.minimum_cell ?? 5 })
                      : undefined,
                }))}
              />
              <p className="mt-3 text-xs text-muted">
                {t("districtNote", { min: districts.data?.minimum_cell ?? 5 })}
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}
