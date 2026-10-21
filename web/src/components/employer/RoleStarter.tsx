"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import type { Standard } from "@/components/StandardPicker";
import { Badge, Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { paths } from "@/lib/api-schema";

type RoleHit =
  paths["/roles/search"]["get"]["responses"][200]["content"]["application/json"][number];

/**
 * "Start from a job role" (Sprint 91, B22.3).
 *
 * To post a vacancy an employer had to find National Occupational Standards one at a time, by
 * names like "Follow infection control policies & procedures including biomedical waste disposal
 * protocols". The designer's review called it the highest-friction step in the product. An
 * employer can name the job; every qualification pack carries a job role and names the standards
 * a person in it must be able to do, the same expansion bulk upload makes (`job_role` in
 * ADR-063: **compulsory standards only, importance 3, mandatory off**).
 *
 * **It adds; it never replaces or hides.** The standards land in the editor's list below, where
 * each can be re-weighted, made mandatory or removed, and the ones already chosen are skipped.
 * Nothing is saved until the employer saves, and the publish rule (at least one standard) is
 * unchanged. A role that is not found leaves the standards search in place as before.
 */
export function RoleStarter({
  chosen,
  titleIsEmpty,
  onAdd,
  onUseTitle,
}: {
  /** Slugs already on the vacancy, so a role never adds one twice. */
  chosen: Set<string>;
  /** Whether the title box is still empty, which is when offering the role as the title helps. */
  titleIsEmpty: () => boolean;
  onAdd: (standards: Standard[]) => void;
  onUseTitle: (title: string) => void;
}) {
  const t = useTranslations("employerWorkspace");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleHit | null>(null);
  const [added, setAdded] = useState<number | null>(null);
  const deferred = useDeferredValue(query.trim());

  const roles = useQuery({
    queryKey: ["role-search", deferred],
    enabled: deferred.length > 0 && role === null,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q: deferred, limit: 6 } } })).data ?? [],
  });

  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  const choose = async (hit: RoleHit) => {
    setRole(hit);
    setAdded(null);
    setQuery("");
    setState("loading");
    const { data, error } = await api.GET("/roles/{slug}/standards", {
      params: { path: { slug: hit.slug } },
    });
    if (error || !data) {
      setState("error"); // nothing is added
      return;
    }
    setState("idle");
    const core = data.standards.filter((s) => s.requirement === "compulsory" && !chosen.has(s.slug));
    onAdd(core);
    setAdded(core.length);
  };

  const hits = roles.data ?? [];

  return (
    <div className="rounded-lg border border-border-token bg-background p-4">
      <label htmlFor="role-starter" className="text-sm font-semibold">
        {t("roleStartTitle")}
      </label>
      <p className="mt-1 text-xs text-muted">{t("roleStartHint")}</p>
      <input
        id="role-starter"
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setRole(null);
          setAdded(null);
          setState("idle");
        }}
        placeholder={t("roleStartPlaceholder")}
        className="mt-3 min-h-11 w-full rounded-lg border border-input-border bg-surface px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      />

      {deferred && role === null && (
        <ul className="mt-2 space-y-1.5">
          {hits.map((hit) => (
            <li key={hit.slug}>
              <button
                type="button"
                onClick={() => void choose(hit)}
                className="flex min-h-11 w-full flex-wrap items-center gap-2 rounded-lg border border-border-token bg-surface px-3 py-2 text-left hover:border-brand"
              >
                <span className="text-sm font-medium">{hit.job_role}</span>
                {hit.match_kind === "alias" && hit.matched_on && (
                  <span className="text-xs text-brand">{hit.matched_on}</span>
                )}
                <Badge>{t("standardsCount", { count: hit.standards_count })}</Badge>
              </button>
            </li>
          ))}
          {!roles.isPending && hits.length === 0 && (
            <li className="text-sm text-muted">{t("roleStartNone")}</li>
          )}
        </ul>
      )}

      {role && state === "loading" && <p className="mt-3 text-sm text-muted">{t("roleStartLoading")}</p>}
      {role && state === "error" && <p className="mt-3 text-sm text-danger-text">{t("roleStartError")}</p>}
      {role && added !== null && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p className="text-sm text-success-text" role="status">
            {t("roleStartAdded", { count: added, role: role.job_role })}
          </p>
          {titleIsEmpty() && (
            <Button type="button" variant="secondary" size="sm" onClick={() => onUseTitle(role.job_role)}>
              {t("roleStartUseTitle", { role: role.job_role })}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
