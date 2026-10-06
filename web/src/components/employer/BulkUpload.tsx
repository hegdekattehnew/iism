"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { SessionExpired } from "@/components/SessionExpired";
import {
  Alert,
  Badge,
  Button,
  ButtonLink,
  Card,
  CardBody,
} from "@/components/ui";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import {
  employerDashboardKey,
  invalidatePublicCounts,
  providerDashboardKey,
} from "@/lib/counts";
import { ApiError, detailOf, isSignedOut, readDetail } from "@/lib/http";

type Kind = "jobs" | "courses";
type Report = components["schemas"]["BulkReportOut"];
type Row = components["schemas"]["BulkRowOut"];
type Published = components["schemas"]["BulkPublishOut"];

// The server's own limits (`max_bulk_body_bytes`, `BulkPublishIn.slugs`). A file the
// browser can see is too big is refused here rather than uploaded to be refused there.
export const MAX_FILE_BYTES = 2 * 1024 * 1024;
export const PUBLISH_BATCH = 200;

const TONE = {
  ok: "good",
  warning: "warn",
  error: "bad",
  skip: "neutral",
} as const;

/** Save text as a UTF-8 CSV Excel will open with Devanagari intact (hence the BOM). */
function saveCsv(name: string, text: string) {
  const blob = new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/** The file is the request body, so the typed client is told not to JSON-encode it. */
const csv = {
  bodySerializer: (body: string) => body,
  headers: { "content-type": "text/csv" },
};

async function send(
  kind: Kind,
  org: string,
  step: "check" | "apply",
  text: string,
) {
  const params = { path: { org_slug: org } };
  const { data, error, response } =
    kind === "jobs"
      ? await api.POST(`/org/{org_slug}/jobs/bulk/${step}`, {
          params,
          body: text,
          ...csv,
        })
      : await api.POST(`/org/{org_slug}/courses/bulk/${step}`, {
          params,
          body: text,
          ...csv,
        });
  // Keep what the server said: "daily limit reached" and "that file is not UTF-8" both
  // arrive here, and a fixed sentence would be wrong about why.
  if (error || !data) throw new ApiError(response.status, readDetail(error));
  return data;
}

async function publish(
  kind: Kind,
  org: string,
  slugs: string[],
): Promise<Published> {
  const params = { path: { org_slug: org } };
  const body = { slugs };
  const { data, error, response } =
    kind === "jobs"
      ? await api.POST("/org/{org_slug}/jobs/bulk/publish", { params, body })
      : await api.POST("/org/{org_slug}/courses/bulk/publish", {
          params,
          body,
        });
  if (error || !data) throw new ApiError(response.status, readDetail(error));
  return data;
}

/**
 * Create vacancies or courses from a spreadsheet, in three acts the person controls:
 * **check** (nothing is written), **apply** (drafts, invisible to everyone else) and
 * **publish** (the one step that makes them public). The server re-validates on apply, so a
 * review on screen is a courtesy, never the thing that makes a row safe.
 */
export function BulkUpload({ kind, org }: { kind: Kind; org: string }) {
  const t = useTranslations("bulkUpload");
  const qc = useQueryClient();

  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [tooBig, setTooBig] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [applied, setApplied] = useState<Report | null>(null);
  const [published, setPublished] = useState<Published | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const refresh = () => {
    if (kind === "jobs") {
      void qc.invalidateQueries({ queryKey: ["org-jobs", org] });
      void qc.invalidateQueries({ queryKey: employerDashboardKey(org) });
    } else {
      void qc.invalidateQueries({ queryKey: ["org-courses", org] });
      void qc.invalidateQueries({ queryKey: providerDashboardKey(org) });
    }
    invalidatePublicCounts(qc);
  };

  const template = useMutation({
    mutationFn: async () => {
      const params = { path: { org_slug: org } };
      const { data, error, response } =
        kind === "jobs"
          ? await api.GET("/org/{org_slug}/jobs/bulk/template", {
              params,
              parseAs: "text",
            })
          : await api.GET("/org/{org_slug}/courses/bulk/template", {
              params,
              parseAs: "text",
            });
      if (error || typeof data !== "string")
        throw new ApiError(response.status, null);
      saveCsv(`${kind}-template.csv`, data);
    },
  });

  const check = useMutation({
    mutationFn: (body: string) => send(kind, org, "check", body),
    onSuccess: setReport,
  });

  const apply = useMutation({
    mutationFn: (body: string) => send(kind, org, "apply", body),
    onSuccess: (result) => {
      setApplied(result);
      refresh();
    },
  });

  const publishAll = useMutation({
    mutationFn: (slugs: string[]) => publish(kind, org, slugs),
    onSuccess: (result) => {
      setPublished(result);
      setConfirming(false);
      refresh();
    },
    onError: () => setConfirming(false),
  });

  const failure =
    template.error ?? check.error ?? apply.error ?? publishAll.error;
  if (isSignedOut(failure)) return <SessionExpired />;

  const reset = () => {
    setText(null);
    setFileName("");
    setTooBig(false);
    setReport(null);
    setApplied(null);
    setPublished(null);
    setAccepted(false);
    setConfirming(false);
    check.reset();
    apply.reset();
    publishAll.reset();
  };

  const choose = async (file: File | undefined) => {
    reset();
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setTooBig(true);
      return;
    }
    const body = await file.text();
    setText(body);
    setFileName(file.name);
    check.mutate(body);
  };

  const shown = applied ?? report;
  const ready = report ? report.ok + report.warnings : 0;
  const drafts = (applied?.rows ?? [])
    .filter((r) => r.created && r.slug)
    .map((r) => r.slug as string);

  return (
    <div className="mt-8 space-y-6">
      <div>
        <ButtonLink
          href={`/employer/${org}`}
          variant="ghost"
          size="sm"
          className="-ml-3"
        >
          ← {t("back")}
        </ButtonLink>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">
          {t(`${kind}.title`)}
        </h1>
        <p className="mt-2 text-sm text-muted">{t(`${kind}.intro`)}</p>
      </div>

      {failure && (
        <Alert role="alert">{detailOf(failure) ?? t("failed")}</Alert>
      )}

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold">{t("step1")}</h2>
          <p className="text-sm text-muted">{t("templateHelp")}</p>
          <p className="text-sm text-muted">{t(`${kind}.standardsHelp`)}</p>
          <Button
            variant="secondary"
            disabled={template.isPending}
            onClick={() => template.mutate()}
          >
            {t("downloadTemplate")}
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold">{t("step2")}</h2>
          <label className="block text-sm" htmlFor="bulk-file">
            {t("chooseFile")}
          </label>
          <input
            id="bulk-file"
            type="file"
            accept=".csv,text/csv"
            className="block w-full text-sm"
            disabled={check.isPending || apply.isPending}
            onChange={(e) => void choose(e.target.files?.[0])}
          />
          {tooBig && <Alert role="alert">{t("tooBig")}</Alert>}
          {check.isPending && (
            <p className="text-sm text-muted" role="status">
              {t("checking")}
            </p>
          )}
        </CardBody>
      </Card>

      {shown && (
        <Card>
          <CardBody className="space-y-4">
            <h2 className="text-base font-semibold">
              {applied ? t("step3Done") : t("step3")}
            </h2>
            <p className="text-sm text-muted">{fileName}</p>
            <p className="text-sm" role="status" aria-live="polite">
              {t("summary", {
                ok: shown.ok,
                warnings: shown.warnings,
                errors: shown.errors,
                skipped: shown.skipped,
              })}
            </p>
            {!applied && (
              <p className="text-sm text-muted">
                {t("limitLine", {
                  remaining: shown.remaining_today,
                  limit: shown.daily_limit,
                })}
              </p>
            )}
            {(shown.notes ?? []).length > 0 && (
              <Alert tone="info" role={undefined}>
                <ul className="list-disc pl-5">
                  {(shown.notes ?? []).map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </Alert>
            )}

            <ReviewTable rows={shown.rows} />

            {!applied && report && (
              <div className="space-y-3">
                {report.errors > 0 && (
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={accepted}
                      onChange={(e) => setAccepted(e.target.checked)}
                    />
                    <span>{t("acknowledge", { count: report.errors })}</span>
                  </label>
                )}
                {report.errors_csv && (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      saveCsv(`${kind}-to-fix.csv`, report.errors_csv ?? "")
                    }
                  >
                    {t("downloadErrors")}
                  </Button>
                )}
                <div>
                  <Button
                    disabled={
                      text === null ||
                      ready === 0 ||
                      (report.errors > 0 && !accepted) ||
                      apply.isPending
                    }
                    onClick={() => text !== null && apply.mutate(text)}
                  >
                    {apply.isPending
                      ? t("applying")
                      : t("apply", { count: ready })}
                  </Button>
                  <p className="mt-2 text-xs text-muted">{t("draftsNote")}</p>
                </div>
              </div>
            )}

            {applied && (
              <div className="space-y-3">
                <p className="text-sm font-medium">
                  {t("created", { count: applied.created })}
                </p>
                {applied.errors_csv && (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      saveCsv(`${kind}-to-fix.csv`, applied.errors_csv ?? "")
                    }
                  >
                    {t("downloadErrors")}
                  </Button>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {applied && drafts.length > 0 && !published && (
        <Card>
          <CardBody className="space-y-3">
            <h2 className="text-base font-semibold">{t("step4")}</h2>
            <p className="text-sm text-muted">{t(`${kind}.publishNote`)}</p>
            {!confirming ? (
              <Button onClick={() => setConfirming(true)}>
                {t("publish", {
                  count: Math.min(drafts.length, PUBLISH_BATCH),
                })}
              </Button>
            ) : (
              <Alert tone="warning" role={undefined}>
                <p>
                  {t(`${kind}.publishConfirm`, {
                    count: Math.min(drafts.length, PUBLISH_BATCH),
                  })}
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    disabled={publishAll.isPending}
                    onClick={() =>
                      publishAll.mutate(drafts.slice(0, PUBLISH_BATCH))
                    }
                  >
                    {t("confirmPublish")}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirming(false)}>
                    {t("cancel")}
                  </Button>
                </div>
              </Alert>
            )}
          </CardBody>
        </Card>
      )}

      {published && (
        <Card>
          <CardBody className="space-y-3">
            <p className="text-sm font-medium" role="status">
              {t("publishedSummary", {
                published: published.published,
                refused: published.refused,
              })}
            </p>
            {published.results
              .filter((r) => !r.published)
              .map((r) => (
                <p key={r.slug} className="text-sm text-muted">
                  {r.slug}: {r.message}
                </p>
              ))}
          </CardBody>
        </Card>
      )}

      {(applied || report) && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={reset}>
            {t("another")}
          </Button>
          {applied && (
            <ButtonLink href={`/employer/${org}`} variant="ghost">
              {t(`${kind}.viewList`)}
            </ButtonLink>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewTable({ rows }: { rows: Row[] }) {
  const t = useTranslations("bulkUpload");
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t("tableCaption")}</caption>
        <thead>
          <tr className="border-b border-border-token text-xs text-muted">
            <th scope="col" className="py-2 pr-3 font-medium">
              {t("colRow")}
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              {t("colTitle")}
            </th>
            <th scope="col" className="py-2 pr-3 font-medium">
              {t("colResult")}
            </th>
            <th scope="col" className="py-2 font-medium">
              {t("colDetails")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.row}
              className="border-t border-border-token align-top first:border-t-0"
            >
              <td className="py-2 pr-3 tabular-nums">{r.row}</td>
              <td className="py-2 pr-3">{r.title ?? "—"}</td>
              <td className="py-2 pr-3">
                <Badge tone={TONE[r.status]}>{t(`status.${r.status}`)}</Badge>
              </td>
              <td className="py-2">
                {(r.messages ?? []).map((m) => (
                  <p key={m}>{m}</p>
                ))}
                {(r.standards ?? []).length > 0 && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-xs text-muted">
                      {t("standardsCount", {
                        count: (r.standards ?? []).length,
                      })}
                    </summary>
                    <ul className="mt-1 space-y-0.5 text-xs">
                      {(r.standards ?? []).map((s) => (
                        <li key={s.code}>
                          <span className="font-mono">{s.code}</span> {s.name}
                          {s.origin === "role" && (
                            <span className="text-muted">
                              {" "}
                              · {t("fromRole")}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
