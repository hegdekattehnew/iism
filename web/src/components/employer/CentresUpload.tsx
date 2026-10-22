"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { MAX_FILE_BYTES, ROW_LOOK } from "@/components/employer/BulkUpload";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, ButtonLink, Card, CardBody } from "@/components/ui";
import { StatusChip } from "@/components/ui/status-chip";
import { api } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { centresKey } from "@/lib/centres";
import { saveCsv } from "@/lib/download";
import { ApiError, apiErrorFrom, detailOf, isSignedOut } from "@/lib/http";

type Report = components["schemas"]["CentreBulkReportOut"];

/** The file is the request body, so the typed client is told not to JSON-encode it. */
const csv = {
  bodySerializer: (body: string) => body,
  headers: { "content-type": "text/csv" },
};

/**
 * Add many centres from a spreadsheet (Sprint 95): **check** first (nothing is written), then **add**.
 * A centre has no draft state to stop at, so there is no third step; the server re-validates on add,
 * so the review is a courtesy and never the thing that makes a row safe.
 */
export function CentresUpload({ org }: { org: string }) {
  const t = useTranslations("centresUpload");
  const qc = useQueryClient();
  const [text, setText] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [tooBig, setTooBig] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [applied, setApplied] = useState<Report | null>(null);
  const [accepted, setAccepted] = useState(false);

  const template = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.GET("/org/{org_slug}/centres/bulk/template", {
        params: { path: { org_slug: org } },
        parseAs: "text",
      });
      if (error || typeof data !== "string") throw new ApiError(response.status, null);
      saveCsv("centres-template.csv", data);
    },
  });

  const send = async (step: "check" | "apply", body: string) => {
    const params = { path: { org_slug: org } };
    const { data, error, response } =
      step === "check"
        ? await api.POST("/org/{org_slug}/centres/bulk/check", { params, body, ...csv })
        : await api.POST("/org/{org_slug}/centres/bulk/apply", { params, body, ...csv });
    if (error || !data) throw apiErrorFrom(response.status, error);
    return data;
  };

  const check = useMutation({ mutationFn: (body: string) => send("check", body), onSuccess: setReport });
  const apply = useMutation({
    mutationFn: (body: string) => send("apply", body),
    onSuccess: (result) => {
      setApplied(result);
      void qc.invalidateQueries({ queryKey: centresKey(org) });
    },
  });

  const failure = template.error ?? check.error ?? apply.error;
  if (isSignedOut(failure)) return <SessionExpired />;

  const reset = () => {
    setText(null);
    setFileName("");
    setTooBig(false);
    setReport(null);
    setApplied(null);
    setAccepted(false);
    check.reset();
    apply.reset();
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

  return (
    <div className="mt-8 space-y-6">
      <div>
        <ButtonLink href={`/employer/${org}/centres`} variant="ghost" size="sm" className="-ml-3">
          ← {t("back")}
        </ButtonLink>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mt-2 text-sm text-muted">{t("intro")}</p>
      </div>

      {failure && <Alert role="alert">{detailOf(failure) ?? t("failed")}</Alert>}

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold">{t("step1")}</h2>
          <p className="text-sm text-muted">{t("templateHelp")}</p>
          <Button variant="secondary" disabled={template.isPending} onClick={() => template.mutate()}>
            {t("downloadTemplate")}
          </Button>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-3">
          <h2 className="text-base font-semibold">{t("step2")}</h2>
          <label className="block text-sm" htmlFor="centres-file">
            {t("chooseFile")}
          </label>
          <input
            id="centres-file"
            type="file"
            accept=".csv,text/csv"
            className="block min-h-11 w-full text-sm"
            disabled={check.isPending || apply.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              // A browser fires no `change` when the same file is chosen twice, and choosing the
              // file you just fixed is the whole fix-and-upload-again loop.
              e.target.value = "";
              void choose(file);
            }}
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
            <h2 className="text-base font-semibold">{applied ? t("step3Done") : t("step3")}</h2>
            <p className="text-sm text-muted">{fileName}</p>
            <p className="text-sm" role="status" aria-live="polite">
              {t("summary", {
                ok: shown.ok,
                warnings: shown.warnings,
                errors: shown.errors,
                skipped: shown.skipped,
              })}
            </p>
            {(shown.notes ?? []).length > 0 && (
              <Alert tone="info" role={undefined}>
                <ul className="list-disc pl-5">
                  {(shown.notes ?? []).map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </Alert>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">{t("tableCaption")}</caption>
                <thead>
                  <tr className="border-b border-border-token text-xs text-muted">
                    <th scope="col" className="py-2 pr-3 font-medium">
                      {t("colRow")}
                    </th>
                    <th scope="col" className="py-2 pr-3 font-medium">
                      {t("colName")}
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
                  {shown.rows.map((r) => (
                    <tr key={r.row} className="border-t border-border-token align-top first:border-t-0">
                      <td className="py-2 pr-3 tabular-nums">{r.row}</td>
                      <td className="py-2 pr-3">{r.name ?? "—"}</td>
                      <td className="py-2 pr-3">
                        <StatusChip tone={ROW_LOOK[r.status].tone} icon={ROW_LOOK[r.status].icon}>
                          {t(`status.${r.status}`)}
                        </StatusChip>
                      </td>
                      <td className="py-2">
                        {(r.messages ?? []).map((m, i) => (
                          <p key={`${i}:${m}`}>{m}</p>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {!applied && report && (
              <div className="space-y-3">
                <p className="text-sm text-muted">{t("room", { remaining: report.remaining })}</p>
                {report.errors > 0 && (
                  <label className="flex min-h-11 items-start gap-2 py-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 h-5 w-5 shrink-0"
                      checked={accepted}
                      onChange={(e) => setAccepted(e.target.checked)}
                    />
                    <span>{t("acknowledge", { count: report.errors })}</span>
                  </label>
                )}
                {report.errors_csv && (
                  <Button
                    variant="secondary"
                    onClick={() => saveCsv("centres-to-fix.csv", report.errors_csv ?? "")}
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
                    {apply.isPending ? t("applying") : t("apply", { count: ready })}
                  </Button>
                </div>
              </div>
            )}

            {applied && (
              <div className="space-y-3">
                <p className="text-sm font-medium">{t("created", { count: applied.created })}</p>
                {applied.errors_csv && (
                  <Button
                    variant="secondary"
                    onClick={() => saveCsv("centres-to-fix.csv", applied.errors_csv ?? "")}
                  >
                    {t("downloadErrors")}
                  </Button>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {(applied || report) && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={reset}>
            {t("another")}
          </Button>
          {applied && (
            <ButtonLink href={`/employer/${org}/centres`} variant="ghost">
              {t("viewList")}
            </ButtonLink>
          )}
        </div>
      )}
    </div>
  );
}
