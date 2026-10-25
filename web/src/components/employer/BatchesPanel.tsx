"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { BatchCard } from "@/components/cards/BatchCard";
import { BatchForm } from "@/components/employer/BatchForm";
import { BatchOverviewPanel } from "@/components/employer/BatchOverviewPanel";
import { RowActions } from "@/components/RowActions";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { ChipRow, ChipSelect } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { CalendarIcon } from "@/components/ui/icons";
import {
  BATCH_PHASES,
  useBatches,
  useBatchMutations,
  useDeliverableCourses,
  type Batch,
  type BatchPhase,
} from "@/lib/batches";
import { useCentres } from "@/lib/centres";
import { detailOf, isSignedOut } from "@/lib/http";
import { useOrgType } from "@/lib/org";

/**
 * Who registered is **not in the route's first load**: it is fetched the first time the fold is
 * opened (`next/dynamic` at module level; a source test fails on a static import), with a
 * placeholder of its own so nothing moves when it arrives.
 */
const BatchLearners = dynamic(
  () => import("@/components/employer/BatchLearners").then((m) => m.BatchLearners),
  { loading: () => <Skeleton className="h-24 w-full rounded-lg" /> },
);

/** "Learners": a closed fold that mounts its content the first time it is opened. */
function LearnersFold({ org, batch }: { org: string; batch: Batch }) {
  const t = useTranslations("batchLearners");
  const [opened, setOpened] = useState(false);
  return (
    <details
      className="mt-4 border-t border-border-token pt-2"
      // The first toggle can only be an opening, and once opened it stays mounted.
      onToggle={() => setOpened(true)}
    >
      <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">
        {t("summary", { count: batch.interested })}
      </summary>
      {opened && (
        <div className="pb-2 pt-2">
          <BatchLearners org={org} batch={batch} />
        </div>
      )}
    </details>
  );
}

/**
 * One batch with what its phase allows next. **What may be done is read off the phase, never a flag**:
 * a draft is published, changed or cancelled; a published batch that has not started is changed or
 * cancelled; a running one is neither (a class in progress is never stopped from under its learners),
 * and a finished or cancelled one is history. The server refuses the rest.
 */
function Row({ org, batch }: { org: string; batch: Batch }) {
  const t = useTranslations("batches");
  const { update, publish, cancel } = useBatchMutations(org);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const name = batch.course.title;
  const changeable = batch.phase === "draft" || batch.phase === "open" || batch.phase === "full";

  const actions = editing ? null : (
    <RowActions
      moreLabel={t("more")}
      primary={
        batch.phase === "draft" ? (
          <Button
            size="sm"
            disabled={publish.isPending}
            aria-label={t("publishNamed", { name })}
            onClick={() => publish.mutate(batch.id)}
          >
            {t("publish")}
          </Button>
        ) : undefined
      }
      secondary={
        changeable ? (
          <Button
            size="sm"
            variant="secondary"
            aria-label={t("editNamed", { name })}
            onClick={() => setEditing(true)}
          >
            {t("edit")}
          </Button>
        ) : undefined
      }
      more={[
        changeable && !confirming ? (
          <Button
            key="cancel"
            size="sm"
            variant="ghost"
            aria-label={t("cancelNamed", { name })}
            onClick={() => setConfirming(true)}
          >
            {t("cancelBatch")}
          </Button>
        ) : null,
      ]}
    />
  );

  return (
    <BatchCard
      batch={batch}
      footer={
        <>
          {editing ? (
            <div className="mt-4">
              <BatchForm
                batch={batch}
                pending={update.isPending}
                error={update.error}
                onCancel={() => {
                  update.reset();
                  setEditing(false);
                }}
                onSubmit={(body) =>
                  update.mutate(
                    { id: batch.id, body },
                    { onSuccess: () => setEditing(false) },
                  )
                }
              />
            </div>
          ) : (
            actions
          )}
          {batch.status !== "draft" && !editing && <LearnersFold org={org} batch={batch} />}
          {confirming && (
            <div className="mt-3 rounded-lg border border-border-token p-3">
              <p className="text-sm">
                {batch.interested > 0
                  ? t("confirmCancelTold", { count: batch.interested })
                  : t("confirmCancel")}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={cancel.isPending}
                  onClick={() =>
                    cancel.mutate(batch.id, { onSuccess: () => setConfirming(false) })
                  }
                >
                  {t("confirmYes")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
                  {t("confirmNo")}
                </Button>
              </div>
            </div>
          )}
          {(publish.error ?? cancel.error) != null && (
            <Alert role="alert" className="mt-3">
              {detailOf(publish.error ?? cancel.error) ?? t("failed")}
            </Alert>
          )}
        </>
      }
    />
  );
}

/**
 * An organisation's batches (Sprint 98, ADR-103): plan one, publish it, change it, cancel it. A
 * centre's own manager does the same for their centre only (Sprint 99): the page is the same, there
 * is no centre to choose and no centres to read, and a file of batches is the organisation's.
 */
export function BatchesPanel({ org }: { org: string }) {
  const t = useTranslations("batches");
  const [phase, setPhase] = useState<BatchPhase | "">("");
  const [adding, setAdding] = useState(false);
  const list = useBatches(org, phase);
  const inCentre = useOrgType(org) === "training_centre";
  // A centre has no centres of its own to read (the request would be refused): only an
  // organisation lists them, to choose where a batch goes.
  const centres = useCentres(org, !inCentre);
  const courses = useDeliverableCourses(org);
  const { create } = useBatchMutations(org);

  if (list.isPending) return <Skeleton className="mt-8 h-64 w-full rounded-xl" />;
  if (isSignedOut(list.error)) return <SessionExpired />;
  if (list.isError) {
    return (
      <Card className="mt-8">
        <CardBody>
          <p className="text-sm text-muted">
            {list.error.message === "403" ? t("notDelivering") : t("noAccess")}
          </p>
          {list.error.message === "403" && (
            <ButtonLink href={`/employer/${org}/settings`} variant="secondary" className="mt-4">
              {t("toSettings")}
            </ButtonLink>
          )}
        </CardBody>
      </Card>
    );
  }

  const total = list.data.pages[0]?.total ?? 0;
  const rows = list.data.pages.flatMap((p) => p.items);
  const openCentres = (centres.data?.items ?? []).filter((c) => c.status === "active");
  const courseChoices = courses.data?.items ?? [];
  // Planning needs somewhere to teach and something to teach: say which is missing instead of
  // opening a form with an empty choice.
  const blocker =
    !inCentre && centres.isSuccess && openCentres.length === 0
      ? "noCentres"
      : courses.isSuccess && courseChoices.length === 0
        ? "noCourses"
        : null;

  return (
    <div className="mt-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted" role="status">
          {t("count", { total })}
        </p>
        <div className="flex flex-wrap gap-2">
          {!inCentre && (
            <ButtonLink href={`/employer/${org}/batches/upload`} variant="secondary">
              {t("uploadLink")}
            </ButtonLink>
          )}
          {!adding && blocker === null && (
            <Button onClick={() => setAdding(true)}>{t("plan")}</Button>
          )}
        </div>
      </div>

      <BatchOverviewPanel org={org} />

      <ChipRow label={t("filterLabel")}>
        <ChipSelect
          label={t("filterLabel")}
          active={phase !== ""}
          value={phase}
          onChange={(e) => setPhase(e.target.value as BatchPhase | "")}
        >
          <option value="">{t("phaseAll")}</option>
          {BATCH_PHASES.map((p) => (
            <option key={p} value={p}>
              {t(`phase.${p}`)}
            </option>
          ))}
        </ChipSelect>
      </ChipRow>

      {blocker !== null && (
        <Alert tone="info" role={undefined}>
          {t(blocker)}{" "}
          <ButtonLink
            href={`/employer/${org}${blocker === "noCentres" ? "/centres" : "/delivery"}`}
            variant="secondary"
            size="sm"
          >
            {t(blocker === "noCentres" ? "toCentres" : "toDelivery")}
          </ButtonLink>
        </Alert>
      )}

      {adding && (
        <Card>
          <CardBody>
            <h2 className="mb-4 text-base font-semibold">{t("plan")}</h2>
            <BatchForm
              courses={courseChoices}
              centres={openCentres}
              inCentre={inCentre}
              pending={create.isPending}
              error={create.error}
              onCancel={() => {
                create.reset();
                setAdding(false);
              }}
              onSubmit={(body) =>
                create.mutate(body as Parameters<typeof create.mutate>[0], {
                  onSuccess: () => setAdding(false),
                })
              }
            />
          </CardBody>
        </Card>
      )}

      {rows.length === 0 && !adding ? (
        <EmptyState icon={CalendarIcon} title={phase === "" ? t("empty") : t("emptyFiltered")}>
          {phase === "" ? t("emptyHint") : t("emptyFilteredHint")}
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {rows.map((b) => (
            <li key={b.id}>
              <Row org={org} batch={b} />
            </li>
          ))}
        </ul>
      )}

      {list.hasNextPage && (
        <Button variant="secondary" disabled={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>
          {t("showMore", { left: total - rows.length })}
        </Button>
      )}
    </div>
  );
}
