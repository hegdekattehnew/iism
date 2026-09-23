"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { JobEditor } from "@/components/employer/JobEditor";
import { SessionExpired } from "@/components/SessionExpired";
import { isSignedOut } from "@/lib/http";
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
 * authentication. Its *API* refuses to mount outside local environments; the
 * page itself is unconditional, so the demo is only as absent as the data
 * behind it. This one is the product: the organisation is named in the URL and
 * granted by the caller's membership, so it can ship.
 *
 * Switching organisations lives in the header (`ContextSwitcher`), not here.
 * A switcher inside the page could not be reached from the one screen that
 * most needs it -- the "no access" state below returns before rendering
 * anything else.
 */

export function EmployerWorkspace({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("employerWorkspace");
  const me = useMemberships();
  const jobs = useOrgJobs(orgSlug);
  const { create, update, setPublished, setOpen } = useOrgJobMutations(orgSlug);

  // null = closed, "new" = creating, otherwise the slug being edited.
  const [editing, setEditing] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);

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

  if (isSignedOut(jobs.error) || isSignedOut(me.error)) return <SessionExpired />;
  if (jobs.isError) {
    // A 404 here means "not a member of this organisation", which is
    // deliberately indistinguishable from "no such organisation". A 401
    // is handled above: it means signed out, not unwelcome.
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
    setSaveFailed(false);
    const done = () => setEditing(null);
    // Without an `onError` a 403 -- which is exactly what a non-employer used to
    // get here -- left the form sitting there having silently done nothing.
    const onError = () => setSaveFailed(true);
    if (editing === "new") create.mutate(payload, { onSuccess: done, onError });
    else if (current)
      update.mutate(
        { slug: current.slug, body: payload },
        { onSuccess: done, onError },
      );
  };

  if (editing) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold">
          {editing === "new" ? t("newJob") : t("editJob")}
        </h2>
        {saveFailed && (
          <p className="rounded-lg border border-danger-border bg-danger-surface px-3 py-2 text-sm text-danger-text">
            {t("saveFailed")}
          </p>
        )}
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("yourVacancies")}</h2>
          <p className="mt-1 text-sm text-muted">{t("yourVacanciesNote")}</p>
        </div>
        <Button onClick={() => setEditing("new")}>{t("newJob")}</Button>
      </div>

      {refused && (
        <p className="rounded-lg border border-warning-border bg-warning-surface px-3 py-2 text-sm text-warning-text">
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
                    <h3 className="text-base font-semibold">{job.title}</h3>
                    <p className="mt-0.5 text-sm text-muted">
                      {[job.location_district, job.location_state]
                        .filter(Boolean)
                        .join(", ")}
                      {job.nsqf_level_min != null &&
                        ` · ${t("nsqfLevel", { level: job.nsqf_level_min })}`}
                    </p>
                  </div>
                  {/* Three states, not two. A closed vacancy is published --
                      its page is still there -- so a published/draft badge
                      would call it open when it is not. */}
                  {job.status !== "published" ? (
                    <Badge tone="warn">{t("draft")}</Badge>
                  ) : job.is_open ? (
                    <Badge tone="good">{t("published")}</Badge>
                  ) : (
                    <Badge>{t(`closed_${job.close_reason ?? "filled"}`)}</Badge>
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
                    <button
                      type="button"
                      disabled={setOpen.isPending}
                      onClick={() => {
                        if (
                          job.is_open &&
                          !confirm(t("confirmClose", { title: job.title }))
                        )
                          return;
                        setOpen.mutate({ slug: job.slug, open: !job.is_open });
                      }}
                      className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    >
                      {job.is_open ? t("close") : t("reopen")}
                    </button>
                  )}
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
