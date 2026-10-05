"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Select } from "@/components/profile/fields";
import { Skeleton } from "@/components/ui";
import { useDistrictSkillGap, useDistrictsWithDemand } from "@/lib/ops";

/**
 * Where a district's open vacancies ask for standards its residents do not hold
 * (Sprint 49, BL-12.7). Operator-only, beside the programme report.
 *
 * It renders what the server says and computes nothing: the shortfall, the ranking and
 * -- the part that matters -- the suppression of small counts are all the API's. A
 * supply of one to four residents arrives as `null` with `supply_below_minimum`, and is
 * written "fewer than five"; the shortfall beside it is a minimum, and says so. A panel
 * that did its own arithmetic here could print the number the server withheld.
 */
export function DistrictSkillGap() {
  const t = useTranslations("ops.districtGap");
  const [selected, setSelected] = useState<string | null>(null);
  const districts = useDistrictsWithDemand();
  const gap = useDistrictSkillGap(selected);

  if (districts.isPending) {
    return <Skeleton className="h-20 w-full" />;
  }
  if (districts.isError) {
    return <p className="text-sm text-danger-text">{t("failed")}</p>;
  }

  const options = districts.data?.districts ?? [];
  // Optional in the schema (`default_factory`), so read it once with a fallback.
  const standards = gap.data?.standards ?? [];

  return (
    <div>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>

      {options.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t("none")}</p>
      ) : (
        <>
          <Select
            className="mt-4 max-w-xs"
            value={selected ?? ""}
            onChange={(e) => setSelected(e.target.value || null)}
          >
            <option value="">{t("choose")}</option>
            {options.map((d) => (
              <option key={d.id} value={d.id}>
                {d.state ? `${d.name} (${d.state})` : d.name}
              </option>
            ))}
          </Select>

          {gap.isError && <p className="mt-4 text-sm text-danger-text">{t("failed")}</p>}

          {gap.data && (
            <div className="mt-4">
              <p className="text-sm text-muted">
                {t("vacancies", { count: gap.data.district.vacancies })} ·{" "}
                {t("places", { count: gap.data.positions })} ·{" "}
                {gap.data.residents === null || gap.data.residents === undefined
                  ? t("residentsHidden", { min: gap.data.minimum_cell })
                  : t("residents", { count: gap.data.residents })}
              </p>
              {standards.length === 0 ? (
                <p className="mt-3 text-sm text-muted">{t("empty")}</p>
              ) : (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="text-xs uppercase tracking-wide text-muted">
                        <th className="py-2 pr-3 font-medium">{t("standard")}</th>
                        <th className="py-2 pr-3 text-right font-medium">{t("demand")}</th>
                        <th className="py-2 pr-3 text-right font-medium">{t("supply")}</th>
                        <th className="py-2 text-right font-medium">{t("shortfall")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {standards.map((row) => (
                        <tr
                          key={`${row.nos_code ?? ""}-${row.name}`}
                          className="border-t border-border-token"
                        >
                          <td className="py-2 pr-3">
                            {row.name}
                            {row.nos_code && (
                              <span className="ml-2 text-xs text-muted">{row.nos_code}</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-right tabular-nums">{row.demand}</td>
                          <td className="py-2 pr-3 text-right tabular-nums">
                            {row.supply_below_minimum || row.supply === null || row.supply === undefined
                              ? t("fewerThan", { min: gap.data.minimum_cell })
                              : row.supply}
                          </td>
                          <td className="py-2 text-right font-medium tabular-nums">
                            {row.shortfall_is_minimum
                              ? t("atLeast", { count: row.shortfall })
                              : row.shortfall}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="mt-3 text-xs text-muted">{t("note", { min: gap.data.minimum_cell })}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
