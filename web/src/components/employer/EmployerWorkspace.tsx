"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { JobEditor } from "@/components/employer/JobEditor";
import {
  Badge,
  Button,
  ButtonLink,
  Card,
  CardBody,
  Skeleton,
} from "@/components/ui";
import { Link } from "@/i18n/navigation";
import {
  type JobPayload,
  type OrgJob,
  useMemberships,
  useOrgJobMutations,
  useOrgJobs,
} from "@/lib/org";

/**
 * The signed-in employer's own workspace.
 *
 * Distinct from `/employers/demo`, which acts as a seeded employer with no
 * authentication and mounts in local environments only. This one is the
 * product: the organisation is named in the URL and granted by the caller's
 * membership, so it can ship.
 */

function WorkspaceSwitcher({
  active,
  onSwitch,
}: {
  active: string | null;
  onSwitch: (slug: string) => void;
}) {
  const t = useTranslations("employerWorkspace");
  const { organisations } = useMemberships();

  // With one organisation there is nothing to switch between, and a control
  // offering a single choice is noise.
  if (organisations.length < 2) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-muted">
        {t("actingAs")}
      </span>
      {organisations.map((m) => (
        <button
          key={m.tenant.slug}
          type="button"
          onClick={() => onSwitch(m.tenant.slug)}
          className={`rounded-lg border px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
            m.tenant.slug === active
              ? "border-brand bg-accent-soft font-medium text-brand"
              : "border-border-token text-muted hover:text-foreground"
          }`}
        >
          {m.tenant.name}
          <span className="ml-2 text-[11px] opacity-70">{m.role}</span>
        </button>
      ))}
    </div>
  );
}

export function EmployerWorkspace({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("employerWorkspace");
  const me = useMemberships();
  const jobs = useOrgJobs(orgSlug);
  const { create, update, setPublished } = useOrgJobMutations(orgSlug);

  // null = closed, "new" = creating, otherwise the slug being edited.
  const [editing, setEditing] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);

  if (me.isError) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{t("signInPrompt")}</p>
          <ButtonLink href="/employers/signin" className="mt-4">
            {t("signIn")}
          </ButtonLink>
        </CardBody>
      </Card>
    );
  }

  if (jobs.isError) {
    // A 404 here means "not a member of this organisation", which is
    // deliberately indistinguishable from "no such organisation".
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{t("noAccess")}</p>
        </CardBody>
      </Card>
    );
  }

  const items: OrgJob[] = jobs.data ?? [];
  const current =
    editing && editing !== "new" ? items.find((j) => j.slug === editing) : null;

  const save = (payload: JobPayload) => {
    const done = () => setEditing(null);
    if (editing === "new") create.mutate(payload, { onSuccess: done });
    else if (current)
      update.mutate({ slug: current.slug, body: payload }, { onSuccess: done });
  };

  if (editing) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold">
          {editing === "new" ? t("newJob") : t("editJob")}
        </h2>
        <JobEditor
          job={current ?? null}
          saving={create.isPending || update.isPending}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <WorkspaceSwitcher
        active={orgSlug}
        onSwitch={(slug) => {
          // The workspace lives in the URL so it is shareable and survives a
          // reload, rather than in React state that a refresh would forget.
          window.location.href = window.location.pathname.replace(
            /\/employer\/[^/]+/,
            `/employer/${slug}`,
          );
        }}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("yourVacancies")}</h2>
          <p className="mt-1 text-sm text-muted">{t("yourVacanciesNote")}</p>
        </div>
        <Button onClick={() => setEditing("new")}>{t("newJob")}</Button>
      </div>

      {refused && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
          {t("publishRefused")}
        </p>
      )}

      {jobs.isPending && (
        <ul className="space-y-3">
          {[0, 1].map((i) => (
            <li key={i}>
              <Skeleton className="h-28 w-full rounded-xl" />
            </li>
          ))}
        </ul>
      )}

      {jobs.isFetched && items.length === 0 && (
        <Card>
          <CardBody>
            <p className="text-sm text-muted">{t("noVacancies")}</p>
          </CardBody>
        </Card>
      )}

      <ul className="space-y-3">
        {items.map((job) => (
          <li key={job.slug}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-base font-semibold">{job.title_en}</h3>
                    <p className="mt-0.5 text-sm text-muted">
                      {[job.location_district, job.location_state]
                        .filter(Boolean)
                        .join(", ")}
                      {job.nsqf_level_min != null &&
                        ` · ${t("nsqfLevel", { level: job.nsqf_level_min })}`}
                    </p>
                  </div>
                  {job.status === "published" ? (
                    <Badge tone="good">{t("published")}</Badge>
                  ) : (
                    <Badge tone="warn">{t("draft")}</Badge>
                  )}
                </div>

                <p className="mt-3 text-sm text-muted">
                  {t("standardsCount", { count: (job.skills ?? []).length })}
                  {(job.skills ?? []).some((s) => s.is_mandatory) &&
                    ` · ${t("mandatoryCount", {
                      count: (job.skills ?? []).filter((s) => s.is_mandatory)
                        .length,
                    })}`}
                </p>

                <div className="mt-4 flex flex-wrap items-center gap-4">
                  <button
                    type="button"
                    onClick={() => setEditing(job.slug)}
                    className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {t("edit")}
                  </button>
                  <button
                    type="button"
                    disabled={setPublished.isPending}
                    onClick={() => {
                      setRefused(null);
                      setPublished.mutate(
                        {
                          slug: job.slug,
                          published: job.status !== "published",
                        },
                        { onError: () => setRefused(job.slug) },
                      );
                    }}
                    className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {job.status === "published" ? t("unpublish") : t("publish")}
                  </button>
                  {job.status === "published" && (
                    <>
                      <Link
                        href={`/employer/${orgSlug}/candidates/${job.slug}`}
                        className="text-sm text-muted underline-offset-4 hover:underline"
                      >
                        {t("seeCandidates")}
                      </Link>
                      <Link
                        href={`/jobs/${job.slug}`}
                        className="text-sm text-muted underline-offset-4 hover:underline"
                      >
                        {t("viewPublic")}
                      </Link>
                    </>
                  )}
                </div>
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
