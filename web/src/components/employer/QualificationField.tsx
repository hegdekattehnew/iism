"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { paths } from "@/lib/api-schema";
import { creditsText, type Translate } from "@/lib/job-text";

type RoleHit =
  paths["/roles/search"]["get"]["responses"][200]["content"]["application/json"][number];

/** The qualification a provider says a course counts toward (Sprint 75, BL-12.8). */
export type ChosenQualification = {
  code: string;
  name: string | null;
  credits: number | null;
};

/**
 * Optional, and **the provider's own statement**: nothing here verifies it, and a learner reads it
 * as "stated by the provider". The search is `/roles/search`, under the `["role-search", q]` key the
 * career page and the profile share, so a role found there is already cached here. The candidate's
 * `RolePicker` is not reused: it adds skills to a profile as a side effect.
 */
export function QualificationField({
  value,
  onChange,
}: {
  value: ChosenQualification | null;
  onChange: (next: ChosenQualification | null) => void;
}) {
  const t = useTranslations("providerWorkspace");
  const tc = useTranslations("coursesPage");
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());

  const hits = useQuery({
    queryKey: ["role-search", deferred],
    enabled: deferred.length > 0 && value === null,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q: deferred, limit: 8 } } })).data ??
      [],
  });

  if (value !== null) {
    const credits = creditsText(value.credits, tc as unknown as Translate);
    return (
      <div className="rounded-lg border border-border-token bg-background px-3 py-2.5">
        <p className="text-sm font-medium">
          {value.name ?? value.code}
          {credits && <span className="font-normal text-muted">{` · ${credits}`}</span>}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="-ml-3 mt-1"
          onClick={() => onChange(null)}
        >
          {t("qualificationRemove")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Text
        type="search"
        value={query}
        aria-label={t("qualification")}
        placeholder={t("qualificationPlaceholder")}
        onChange={(event) => setQuery(event.target.value)}
      />
      {deferred.length > 0 && hits.data && hits.data.length === 0 && (
        <p className="text-sm text-muted">{t("qualificationNone")}</p>
      )}
      {hits.data && hits.data.length > 0 && (
        <ul className="rounded-lg border border-border-token">
          {hits.data.map((hit: RoleHit) => {
            const credits = creditsText(hit.credits, tc as unknown as Translate);
            return (
              <li key={hit.slug} className="border-t border-border-token first:border-t-0">
                <button
                  type="button"
                  onClick={() => {
                    onChange({ code: hit.qp_code, name: hit.job_role, credits: hit.credits ?? null });
                    setQuery("");
                  }}
                  className="flex min-h-11 w-full flex-col items-start justify-center gap-0.5 px-3 py-2 text-left hover:bg-surface-muted"
                >
                  <span className="text-sm font-medium">{hit.job_role}</span>
                  <span className="text-xs text-muted">
                    {[hit.sector_name, credits].filter(Boolean).join(" · ")}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
