"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { EmployerDashboard } from "@/components/employer/EmployerDashboard";
import { JobEditor } from "@/components/employer/JobEditor";
import { RowActions } from "@/components/RowActions";
import { SessionExpired } from "@/components/SessionExpired";
import { detailOf, isSignedOut } from "@/lib/http";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardBody,
  Skeleton,
} from "@/components/ui";
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
  const format = useFormatter();
  const me = useMemberships();
  const jobs = useOrgJobs(orgSlug);
  const { create, update, setPublished, setOpen } = useOrgJobMutations(orgSlug);

  // null = closed, "new" = creating, otherwise the slug being edited.
  const [editing, setEditing] = useState<string | null>(null);
  // What the server said when publishing, closing or reopening was refused.
  // This used to be a slug, rendered as one fixed sentence about required
  // standards -- so an employer whose token had expired was told their vacancy
  // needed a standard it already had. A wrong reason is worse than none.
  const [actionFailed, setActionFailed] = useState<string | true | null>(null);
  // A 401 from one of those mutations. The query-level check below cannot see
  // it: the session expires while the page is already open.
  const [signedOut, setSignedOut] = useState(false);
  // The server's own words when it has any. `saveFailed` alone produced
  // "Could not save. Check the details and try again." for a two-character
  // title, which names neither the field nor the rule.
  const [saveFailed, setSaveFailed] = useState<string | true | null>(null);

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

  if (signedOut || isSignedOut(jobs.error) || isSignedOut(me.error))
    return <SessionExpired />;
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

  // Publish, unpublish, close and reopen all fail the same way and all used
  // to fail silently or misleadingly. 401 goes to the panel built for it;
  // anything else shows the server's own sentence where there is one.
  const onActionError = (e: unknown) => {
    if (isSignedOut(e)) {
      setSignedOut(true);
      return;
    }
    setActionFailed(detailOf(e) ?? true);
  };

  const save = (payload: JobPayload) => {
    setSaveFailed(null);
    const done = () => setEditing(null);
    // Without an `onError` a 403 -- which is exactly what a non-employer used to
    // get here -- left the form sitting there having silently done nothing.
    const onError = (e: unknown) => setSaveFailed(detailOf(e) ?? true);
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
          <Alert role="alert">
            {/* What the server actually said, when it said anything. The
                generic line is the fallback for a failure that carried no
                explanation -- a network drop, a 500 -- not the default. */}
            {typeof saveFailed === "string" ? saveFailed : t("saveFailed")}
          </Alert>
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
      <EmployerDashboard orgSlug={orgSlug} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("yourVacancies")}</h2>
          <p className="mt-1 text-sm text-muted">{t("yourVacanciesNote")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href={`/employer/${orgSlug}/jobs/upload`} variant="secondary">
            {t("uploadJobs")}
          </ButtonLink>
          <Button onClick={() => setEditing("new")}>{t("newJob")}</Button>
        </div>
      </div>

      {actionFailed && (
        <Alert role="alert">
          {/* The server's own words -- "Add at least one required standard
              before publishing" -- when it sent any. The generic line is the
              fallback for a failure that carried no explanation. */}
          {typeof actionFailed === "string" ? actionFailed : t("actionFailed")}
        </Alert>
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
                  {job.taken_down_at ? (
                    <Badge tone="bad">{t("removed")}</Badge>
                  ) : job.status !== "published" ? (
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

                {job.taken_down_at && (
                  <Alert tone="warning" role={undefined} className="mt-3 space-y-1">
                    <p className="font-medium">
                      {t("removedOn", {
                        date: format.dateTime(new Date(job.taken_down_at), {
                          dateStyle: "medium",
                        }),
                      })}
                    </p>
                    <p>{job.takedown_reason}</p>
                    <p className="text-xs">{t("removedExplain")}</p>
                  </Alert>
                )}

                <RowActions
                  moreLabel={t("more")}
                  // One thing a person came to this row for: the candidates for a live vacancy, or
                  // putting a draft live. Nothing for a vacancy an operator took down.
                  primary={
                    job.taken_down_at ? null : job.status === "published" ? (
                      <ButtonLink
                        size="sm"
                        href={`/employer/${orgSlug}/candidates/${job.slug}`}
                      >
                        {t("seeCandidates")}
                      </ButtonLink>
                    ) : (
                      <Button
                        size="sm"
                        disabled={setPublished.isPending}
                        onClick={() => {
                          setActionFailed(null);
                          setPublished.mutate(
                            { slug: job.slug, published: true },
                            { onError: onActionError },
                          );
                        }}
                      >
                        {t("publish")}
                      </Button>
                    )
                  }
                  secondary={
                    <Button size="sm" variant="secondary" onClick={() => setEditing(job.slug)}>
                      {t("edit")}
                    </Button>
                  }
                  more={[
                    job.status === "published" && !job.taken_down_at && (
                      <Button
                        key="unpublish"
                        size="sm"
                        variant="ghost"
                        disabled={setPublished.isPending}
                        onClick={() => {
                          setActionFailed(null);
                          setPublished.mutate(
                            { slug: job.slug, published: false },
                            { onError: onActionError },
                          );
                        }}
                      >
                        {t("unpublish")}
                      </Button>
                    ),
                    job.status === "published" && !job.taken_down_at && (
                      <Button
                        key="open"
                        size="sm"
                        variant="ghost"
                        disabled={setOpen.isPending}
                        onClick={() => {
                          if (job.is_open && !confirm(t("confirmClose", { title: job.title })))
                            return;
                          setActionFailed(null);
                          setOpen.mutate(
                            { slug: job.slug, open: !job.is_open },
                            { onError: onActionError },
                          );
                        }}
                      >
                        {job.is_open ? t("close") : t("reopen")}
                      </Button>
                    ),
                    job.status === "published" && (
                      <ButtonLink key="public" size="sm" variant="ghost" href={`/jobs/${job.slug}`}>
                        {t("viewPublic")}
                      </ButtonLink>
                    ),
                  ]}
                />
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
