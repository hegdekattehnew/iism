"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Select } from "@/components/profile/fields";
import { Badge, Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { paths } from "@/lib/api-schema";
import { useProfileMutations } from "@/lib/profile";

type RoleHit =
  paths["/roles/search"]["get"]["responses"][200]["content"]["application/json"][number];
type RoleStandards =
  paths["/roles/{slug}/standards"]["get"]["responses"][200]["content"]["application/json"];
type Standard = RoleStandards["standards"][number];

/**
 * "What work do you do?" -- and the national standards behind the answer.
 *
 * A candidate cannot name a National Occupational Standard; they are called
 * things like "Follow infection control policies & procedures including
 * biomedical waste disposal protocols". They can name their job. Every
 * qualification pack carries a job role, and the pack names its standards, so
 * the candidate names the role and ticks what they can already do.
 *
 * **Nothing starts ticked.** Pre-ticking the whole qualification would let the
 * easy path claim standards nobody affirmed -- the same reason the server
 * writes every one of these as `self_declared`, never `inferred`.
 *
 * **Electives stay in their groups.** Flattened, "choose one of these" reads as
 * "all of these are required", which is not what the qualification says.
 */
export function RolePicker({ held }: { held: Set<string> }) {
  const t = useTranslations("profilePage.roles");
  const tp = useTranslations("profilePage");
  const { addSkillsBulk } = useProfileMutations();

  const [query, setQuery] = useState("");
  const [role, setRole] = useState<RoleHit | null>(null);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [proficiency, setProficiency] = useState(3);
  const [asPreferred, setAsPreferred] = useState(true);
  const [added, setAdded] = useState<number | null>(null);
  const deferred = useDeferredValue(query.trim());

  const roles = useQuery({
    queryKey: ["role-search", deferred],
    enabled: deferred.length > 0 && role === null,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q: deferred, limit: 8 } } }))
        .data ?? [],
  });

  const standards = useQuery({
    queryKey: ["role-standards", role?.slug],
    enabled: role !== null,
    queryFn: async () => {
      const { data, error } = await api.GET("/roles/{slug}/standards", {
        params: { path: { slug: role!.slug } },
      });
      if (error || !data) throw new Error("standards failed");
      return data;
    },
  });

  const choose = (hit: RoleHit) => {
    setRole(hit);
    setTicked(new Set());
    setAdded(null);
  };

  const reset = () => {
    setRole(null);
    setTicked(new Set());
    addSkillsBulk.reset();
  };

  const toggle = (slug: string) =>
    setTicked((current) => {
      const next = new Set(current);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });

  const confirm = () => {
    const items = [...ticked].map((skill_slug) => ({ skill_slug, proficiency }));
    addSkillsBulk.mutate(
      {
        items,
        preferred_role_title: asPreferred && role ? role.job_role : null,
      },
      {
        onSuccess: () => {
          setAdded(items.length);
          setTicked(new Set());
        },
      },
    );
  };

  // ------------------------------------------------ step 2: the standards
  if (role) {
    const list = standards.data?.standards ?? [];
    const groups = groupStandards(list);
    return (
      <div className="rounded-lg border border-border-token bg-background p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold">{role.job_role}</p>
            <p className="mt-0.5 font-mono text-[11px] text-muted">
              {role.qp_code}
              {role.nsqf_level != null && ` · ${t("level", { level: role.nsqf_level })}`}
            </p>
          </div>
          <button
            type="button"
            onClick={reset}
            className="text-xs text-brand hover:underline"
          >
            {t("changeRole")}
          </button>
        </div>
        <p className="mt-3 text-sm">{t("tickPrompt")}</p>

        {standards.isPending && <p className="mt-3 text-sm text-muted">{t("loading")}</p>}
        {standards.isError && <p className="mt-3 text-sm text-rose-700">{t("loadError")}</p>}

        {groups.map((group) => (
          <fieldset key={group.key} className="mt-4">
            <legend className="text-xs font-semibold uppercase tracking-wide text-muted">
              {group.requirement === "compulsory"
                ? t("groupCore")
                : group.requirement === "elective"
                  ? t("groupElective", { group: group.name ?? t("electives") })
                  : t("groupOptional")}
            </legend>
            <ul className="mt-2">
              {group.items.map((s) => {
                const already = held.has(s.slug);
                return (
                  <li
                    key={s.slug}
                    className="border-t border-border-token py-2 first:border-t-0"
                  >
                    <label className="flex items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        checked={already || ticked.has(s.slug)}
                        disabled={already}
                        onChange={() => toggle(s.slug)}
                        className="mt-0.5 h-4 w-4 shrink-0 rounded border-input-border accent-brand"
                      />
                      <span className="min-w-0 flex-1">
                        {s.name}
                        {s.nos_code && (
                          <span className="ml-2 font-mono text-[11px] text-muted">
                            {s.nos_code}
                          </span>
                        )}
                        {already && (
                          <span className="ml-2 text-xs text-muted">{t("alreadyHeld")}</span>
                        )}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        ))}

        {list.length > 0 && (
          <div className="mt-5 space-y-3 border-t border-border-token pt-4">
            <label className="flex items-center gap-2 text-sm">
              <span className="whitespace-nowrap text-muted">{tp("proficiencyLabel")}</span>
              <Select
                value={proficiency}
                onChange={(e) => setProficiency(Number(e.target.value))}
                className="mt-0 w-auto"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={asPreferred}
                onChange={(e) => setAsPreferred(e.target.checked)}
                className="h-4 w-4 rounded border-input-border accent-brand"
              />
              {t("asPreferred")}
            </label>
            <Button
              disabled={ticked.size === 0 || addSkillsBulk.isPending}
              onClick={confirm}
            >
              {addSkillsBulk.isPending ? t("adding") : t("confirm", { count: ticked.size })}
            </Button>
            {addSkillsBulk.isError && (
              <p className="text-sm text-rose-700">{t("saveError")}</p>
            )}
            {added !== null && !addSkillsBulk.isError && (
              <p className="text-sm text-emerald-700 dark:text-emerald-400" role="status">
                {t("added", { count: added })}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  // ---------------------------------------------------- step 1: the role
  const hits = roles.data ?? [];
  return (
    <div>
      <label htmlFor="role-search" className="text-sm font-medium">
        {t("prompt")}
      </label>
      <input
        id="role-search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("placeholder")}
        className="mt-2 w-full rounded-lg border border-input-border bg-background px-4 py-2.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      />
      {deferred && (
        <ul className="mt-2 space-y-1.5">
          {hits.map((hit) => (
            <li key={hit.slug}>
              <button
                type="button"
                onClick={() => choose(hit)}
                className="w-full rounded-lg border border-border-token bg-background px-3 py-2 text-left hover:border-brand"
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{hit.job_role}</span>
                  <Badge>{t("standardsCount", { count: hit.standards_count })}</Badge>
                </span>
                <span className="mt-0.5 block font-mono text-[11px] text-muted">
                  {hit.qp_code}
                  {hit.nsqf_level != null && ` · ${t("level", { level: hit.nsqf_level })}`}
                </span>
                {hit.match_kind === "alias" && (
                  <span className="mt-0.5 block text-xs text-brand">
                    {t("matchedVia", { term: hit.matched_on })}
                  </span>
                )}
                {hit.variants > 1 && (
                  <span className="mt-0.5 block text-xs text-muted">
                    {t("variants", { count: hit.variants })}
                  </span>
                )}
              </button>
            </li>
          ))}
          {roles.isFetched && hits.length === 0 && (
            <li className="px-1 py-2 text-sm text-muted">{t("noRoles")}</li>
          )}
        </ul>
      )}
    </div>
  );
}

type Group = {
  key: string;
  requirement: Standard["requirement"];
  name: string | null;
  items: Standard[];
};

/** Consecutive standards sharing a requirement and a group, in server order. */
function groupStandards(list: Standard[]): Group[] {
  const groups: Group[] = [];
  for (const s of list) {
    const name = s.group_name ?? null;
    const last = groups[groups.length - 1];
    if (last && last.requirement === s.requirement && last.name === name) {
      last.items.push(s);
    } else {
      groups.push({ key: `${s.requirement}:${name ?? ""}`, requirement: s.requirement, name, items: [s] });
    }
  }
  return groups;
}
