"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { Text } from "@/components/profile/fields";
import { Alert, Badge, Button, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { detailOf, statusOf } from "@/lib/http";
import {
  ALIAS_NOTE_MAX,
  ALIAS_TERM_MAX,
  ALIAS_TERM_MIN,
  useAddAlias,
  useAliasCheck,
  useAliasHistory,
  useRetireAlias,
  useRoleAliases,
} from "@/lib/ops";

type RoleHit = {
  slug: string;
  job_role: string;
  nsqf_level?: number | null;
  sector_name?: string | null;
};

/**
 * What people type, and the role it should find (Sprint 47, ADR-054).
 *
 * Role search is a typeahead over the national corpus, and "ward boy" shares no letters
 * with "General Duty Assistant", so a list has to bridge them. Until now that list lived in
 * a Python file only an engineer could change; this is where somebody who knows the labour
 * market changes it.
 *
 * **The target is picked, never typed.** A job title with a stray character resolves to
 * nothing, silently, which is the failure this exists to remove -- so the operator searches
 * the real roles and chooses one. **The checks run as they type** (`useAliasCheck`), so they
 * hear that a role is a disability-track pack, or that a term is already somebody's exact
 * title, before they press anything -- the same rules `make check-role-aliases` applies.
 *
 * It is admin-tier only. A support operator reaches `/admin` and gets 403 from every alias
 * route, which this renders as a sentence rather than a broken panel.
 */
export function RoleAliasEditor() {
  const t = useTranslations("ops");
  const [filter, setFilter] = useState("");
  const aliases = useRoleAliases(useDeferredValue(filter.trim()));

  // 403 is "this tier may not", and the right response is to say so -- not an error state.
  if (statusOf(aliases.error) === 403) {
    return (
      <section className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight">{t("aliasesTitle")}</h2>
        <p className="text-sm text-muted">{t("aliasAdminOnly")}</p>
      </section>
    );
  }

  return (
    <section className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">{t("aliasesTitle")}</h2>
        <p className="mt-2 text-sm text-muted">{t("aliasesIntro")}</p>
      </div>
      <AddAlias />
      <AliasList filter={filter} onFilter={setFilter} aliases={aliases} />
      <AliasHistory />
    </section>
  );
}

function AddAlias() {
  const t = useTranslations("ops");
  const [term, setTerm] = useState("");
  const [note, setNote] = useState("");
  const [target, setTarget] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const check = useAliasCheck(term, target);
  const add = useAddAlias();

  // The dry run answers for the pair on screen. While it is in flight, or when it no
  // longer matches what is typed, nothing is claimed.
  const verdict = check.data;
  const ready = verdict?.ok === true && !check.isFetching;

  const submit = () => {
    if (!target) return;
    setAdded(null);
    add.mutate(
      { surface_form: term.trim(), job_role: target, note: note.trim() || undefined },
      {
        onSuccess: (alias) => {
          setAdded(alias.surface_form);
          setTerm("");
          setNote("");
          setTarget(null);
        },
      },
    );
  };

  return (
    <form
      className="space-y-4 rounded-xl border border-border-token bg-surface p-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) submit();
      }}
    >
      <label className="block text-sm">
        <span className="font-medium">{t("aliasTermLabel")}</span>
        <Text
          name="surface_form"
          value={term}
          minLength={2}
          maxLength={80}
          placeholder={t("aliasTermPlaceholder")}
          onChange={(event) => setTerm(event.target.value)}
        />
        <span className="mt-1 block text-xs text-muted">
          {t("aliasTermHint", { min: ALIAS_TERM_MIN, max: ALIAS_TERM_MAX })}
        </span>
      </label>

      <TargetPicker target={target} onChoose={setTarget} />

      {check.isFetching && <p className="text-sm text-muted">{t("aliasChecking")}</p>}

      {verdict && !check.isFetching && (
        <div className="space-y-2" aria-live="polite">
          {(verdict.problems ?? []).map((problem) => (
            <Alert key={problem} role="alert">
              {problem}
            </Alert>
          ))}
          {verdict.ok && verdict.target && (
            <p className="text-sm">
              {t("aliasWillFind", { role: verdict.target.job_role })}{" "}
              <span className="text-muted">
                {t("aliasTargetMeta", {
                  code: verdict.target.qp_code,
                  count: verdict.target.standards_count,
                })}
              </span>
            </p>
          )}
          {(verdict.warnings ?? []).map((warning) => (
            <p key={warning} className="text-sm text-warning-text">
              {warning}
            </p>
          ))}
        </div>
      )}

      <label className="block text-sm">
        <span className="font-medium">{t("aliasNoteLabel")}</span>
        <Text
          name="note"
          value={note}
          maxLength={300}
          placeholder={t("aliasNotePlaceholder")}
          onChange={(event) => setNote(event.target.value)}
        />
        <span className="mt-1 block text-xs text-muted">
          {t("aliasNoteHint", { max: ALIAS_NOTE_MAX })}
        </span>
      </label>

      {add.isError && (
        <Alert role="alert">{detailOf(add.error) ?? t("aliasAddFailed")}</Alert>
      )}
      {added && !add.isError && (
        <p role="status" className="text-sm text-success-text">
          {t("aliasAdded", { term: added })}
        </p>
      )}

      <Button type="submit" disabled={!ready || add.isPending}>
        {add.isPending ? t("aliasAdding") : t("aliasAdd")}
      </Button>
    </form>
  );
}

function TargetPicker({
  target,
  onChoose,
}: {
  target: string | null;
  onChoose: (jobRole: string | null) => void;
}) {
  const t = useTranslations("ops");
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query.trim());

  // The key and fetcher the profile's role picker and the career page use, so a role
  // found there is already cached here.
  const hits = useQuery({
    queryKey: ["role-search", deferred],
    enabled: deferred.length > 0 && target === null,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q: deferred, limit: 8 } } })).data ??
      [],
  });

  if (target !== null) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          <span className="font-medium">{t("aliasTargetLabel")}</span> {target}
        </span>
        <Button type="button" size="sm" variant="ghost" onClick={() => onChoose(null)}>
          {t("aliasTargetChange")}
        </Button>
      </div>
    );
  }

  return (
    <div className="text-sm">
      <label className="block">
        <span className="font-medium">{t("aliasTargetLabel")}</span>
        <Text
          type="search"
          value={query}
          placeholder={t("aliasTargetSearch")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {deferred.length > 0 && hits.data && hits.data.length === 0 && (
        <p className="mt-2 text-muted">{t("aliasTargetNone")}</p>
      )}
      {hits.data && hits.data.length > 0 && (
        <ul className="mt-2 rounded-lg border border-border-token">
          {hits.data.map((hit: RoleHit) => (
            <li key={hit.slug} className="border-t border-border-token first:border-t-0">
              <button
                type="button"
                onClick={() => {
                  onChoose(hit.job_role);
                  setQuery("");
                }}
                className="flex w-full flex-col items-start gap-0.5 px-3 py-2.5 text-left hover:bg-surface-muted"
              >
                <span className="font-medium">{hit.job_role}</span>
                <span className="text-xs text-muted">
                  {hit.sector_name ?? ""}
                  {hit.nsqf_level != null ? ` · ${t("aliasLevel", { level: hit.nsqf_level })}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AliasList({
  filter,
  onFilter,
  aliases,
}: {
  filter: string;
  onFilter: (value: string) => void;
  aliases: ReturnType<typeof useRoleAliases>;
}) {
  const t = useTranslations("ops");
  const retire = useRetireAlias();

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">{t("aliasListTitle")}</h3>
      <label className="block text-sm">
        <span className="sr-only">{t("aliasFilter")}</span>
        <Text
          type="search"
          value={filter}
          placeholder={t("aliasFilter")}
          onChange={(event) => onFilter(event.target.value)}
        />
      </label>

      {aliases.isPending && <Skeleton className="h-24 w-full" />}
      {aliases.isError && <p className="text-sm text-muted">{t("aliasLoadFailed")}</p>}
      {aliases.data && (
        <>
          <p className="text-xs text-muted">
            {t("aliasShowing", { shown: aliases.data.items.length, total: aliases.data.total })}
          </p>
          {aliases.data.items.length === 0 ? (
            <p className="text-sm text-muted">{t("aliasEmpty")}</p>
          ) : (
            <ul className="rounded-lg border border-border-token">
              {aliases.data.items.map((alias) => (
                <li
                  key={alias.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-t border-border-token px-3 py-2.5 first:border-t-0"
                >
                  <div className="min-w-0 text-sm">
                    <span className="font-medium">{alias.surface_form}</span>
                    <span className="text-muted"> → {alias.job_role}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={alias.source === "operator" ? "brand" : "neutral"}>
                      {t(alias.source === "operator" ? "aliasSourceOperator" : "aliasSourceSeed")}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={retire.isPending}
                      onClick={() => {
                        if (confirm(t("aliasConfirmRetire", { term: alias.surface_form })))
                          retire.mutate({ id: alias.id });
                      }}
                    >
                      {t("aliasRetire")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {retire.isError && (
        <Alert role="alert">{detailOf(retire.error) ?? t("aliasRetireFailed")}</Alert>
      )}
    </div>
  );
}

function AliasHistory() {
  const t = useTranslations("ops");
  const format = useFormatter();
  const history = useAliasHistory();

  if (!history.data || history.data.length === 0) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold">{t("aliasHistoryTitle")}</h3>
      <ul className="space-y-1 text-sm">
        {history.data.map((event, index) => (
          <li key={`${event.created_at}-${index}`} className="text-muted">
            <span className="text-foreground">
              {t(event.action === "added" ? "aliasHistoryAdded" : "aliasHistoryRetired", {
                term: event.surface_form,
                role: event.job_role,
              })}
            </span>{" "}
            {format.dateTime(new Date(event.created_at), {
              dateStyle: "medium",
              timeStyle: "short",
            })}
            {event.note ? ` · ${event.note}` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
