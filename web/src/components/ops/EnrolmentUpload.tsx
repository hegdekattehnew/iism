"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  Skeleton,
} from "@/components/ui";
import { saveCsv } from "@/lib/download";
import {
  type EnrolmentReport,
  type EnrolmentRow,
  MAX_FILE_BYTES,
  PROGRAMME_MAX,
  PROGRAMME_MIN,
  useEnrolmentApply,
  useEnrolmentBatches,
  useEnrolmentCheck,
  useEnrolmentTemplate,
} from "@/lib/enrolment";
import { detailOf, isSignedOut } from "@/lib/http";
import { useMemberships } from "@/lib/org";
import { useKnownProgrammes } from "@/lib/ops";

const TONE = {
  new: "good",
  tag: "brand",
  already: "neutral",
  error: "bad",
} as const;
// What an operator needs to see first, and how many rows are worth listing at all.
const ORDER = { error: 0, already: 1, tag: 2, new: 3 } as const;
const SHOWN = 100;

/**
 * An operator enrols an agency's file of people (Sprint 61, BL-14.10, ADR-071).
 *
 * **Admin tier only, and absent for anyone else** (not a disabled panel): the server answers 403
 * to a support operator either way. Three acts, the person controls each: **check** (nothing is
 * written), the **attestation** that the privacy notice was read out to everyone in the file, and
 * **enrol**. The server re-reads the file on enrol, so the review on screen is a courtesy, never
 * what makes a row safe. A phone is only ever shown masked; this screen holds the file in memory
 * and nowhere else.
 */
export function EnrolmentUpload() {
  const t = useTranslations("enrolment");
  const me = useMemberships();
  const known = useKnownProgrammes();
  const template = useEnrolmentTemplate();
  const check = useEnrolmentCheck();
  const apply = useEnrolmentApply();

  const [programme, setProgramme] = useState("");
  const [file, setFile] = useState<{ text: string; name: string } | null>(null);
  const [tooBig, setTooBig] = useState(false);
  const [report, setReport] = useState<EnrolmentReport | null>(null);
  const [done, setDone] = useState<EnrolmentReport | null>(null);
  const [attested, setAttested] = useState(false);

  if (me.data?.staff_tier !== "admin") return null;

  const failure = template.error ?? check.error ?? apply.error;
  if (isSignedOut(failure)) return <SessionExpired />;

  const name = programme.trim();
  const named = name.length >= PROGRAMME_MIN && name.length <= PROGRAMME_MAX;

  // Anything that changes what the file would do invalidates a review already on screen: an old
  // review must never sit beside a button that now does something else.
  const forget = () => {
    setReport(null);
    setDone(null);
    setAttested(false);
    check.reset();
    apply.reset();
  };

  const choose = async (chosen: File | undefined) => {
    forget();
    setTooBig(false);
    setFile(null);
    if (!chosen) return;
    if (chosen.size > MAX_FILE_BYTES) {
      setTooBig(true);
      return;
    }
    setFile({ text: await chosen.text(), name: chosen.name });
  };

  const runCheck = () => {
    if (!file || !named) return;
    forget();
    check.mutate(
      { body: file.text, programme: name, fileName: file.name },
      { onSuccess: setReport },
    );
  };

  const runApply = () => {
    if (!file || !named || !attested) return;
    apply.mutate(
      { body: file.text, programme: name, fileName: file.name },
      {
        onSuccess: (result) => {
          setDone(result);
          setReport(null);
          // The file has been used; it is not kept around to be used twice by accident.
          setFile(null);
        },
      },
    );
  };

  const shown = done ?? report;
  const writable = report ? report.new + report.tag : 0;

  return (
    <section>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>

      {failure && (
        <Alert role="alert" className="mt-4">
          {detailOf(failure) ?? t("failed")}
        </Alert>
      )}

      <Card className="mt-4">
        <CardBody className="space-y-3">
          <Button
            variant="secondary"
            disabled={template.isPending}
            onClick={() =>
              template.mutate(undefined, {
                onSuccess: (csv) => saveCsv("enrolment-template.csv", csv),
              })
            }
          >
            {t("downloadTemplate")}
          </Button>

          <label
            className="block text-sm font-medium"
            htmlFor="enrol-programme"
          >
            {t("programme")}
          </label>
          <Text
            id="enrol-programme"
            list="enrol-programmes"
            value={programme}
            minLength={PROGRAMME_MIN}
            maxLength={PROGRAMME_MAX}
            placeholder={t("programmePlaceholder")}
            onChange={(e) => {
              setProgramme(e.target.value);
              forget();
            }}
          />
          <datalist id="enrol-programmes">
            {(known.data ?? []).map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
          <p className="text-xs text-muted">{t("programmeHelp")}</p>

          <label className="block text-sm font-medium" htmlFor="enrol-file">
            {t("chooseFile")}
          </label>
          <input
            id="enrol-file"
            type="file"
            accept=".csv,text/csv"
            className="block w-full text-sm"
            disabled={check.isPending || apply.isPending}
            onChange={(e) => {
              const chosen = e.target.files?.[0];
              // Cleared once read: a browser fires no `change` for the same file twice, and
              // choosing the file you just fixed is the whole fix-and-upload-again loop.
              e.target.value = "";
              void choose(chosen);
            }}
          />
          {file && <p className="text-sm text-muted">{file.name}</p>}
          {tooBig && <Alert role="alert">{t("tooBig")}</Alert>}

          <Button
            disabled={!file || !named || check.isPending}
            onClick={runCheck}
          >
            {check.isPending ? t("checking") : t("check")}
          </Button>
        </CardBody>
      </Card>

      {shown && (
        <Card className="mt-4">
          <CardBody className="space-y-4">
            <h3 className="text-base font-semibold">
              {done ? t("doneTitle") : t("reviewTitle")}
            </h3>
            <p className="text-sm" role="status" aria-live="polite">
              {t("summary", {
                programme: shown.programme,
                created: shown.new,
                tagged: shown.tag,
                already: shown.already,
                errors: shown.errors,
              })}
            </p>
            {shown.notes.length > 0 && (
              <Alert tone="info" role={undefined}>
                <ul className="list-disc pl-5">
                  {shown.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </Alert>
            )}
            <Rows rows={shown.rows} />
            {shown.errors_csv && (
              <Button
                variant="secondary"
                onClick={() =>
                  saveCsv("enrolment-to-fix.csv", shown.errors_csv ?? "")
                }
              >
                {t("downloadErrors")}
              </Button>
            )}

            {report && !done && (
              <div className="space-y-3">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={attested}
                    disabled={apply.isPending}
                    onChange={(e) => setAttested(e.target.checked)}
                  />
                  <span>
                    {t("attest")}
                    <span className="mt-0.5 block text-xs text-muted">
                      {t("attestHelp")}
                    </span>
                  </span>
                </label>
                <Button
                  disabled={writable === 0 || !attested || apply.isPending}
                  onClick={runApply}
                >
                  {apply.isPending
                    ? t("enrolling")
                    : t("enrol", { count: writable })}
                </Button>
                {writable === 0 && (
                  <p className="text-xs text-muted">{t("nothingToEnrol")}</p>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <Batches />
    </section>
  );
}

function Rows({ rows }: { rows: EnrolmentRow[] }) {
  const t = useTranslations("enrolment");
  // Problems first, and not a thousand rows of "fine".
  const sorted = [...rows].sort(
    (a, b) => ORDER[a.status] - ORDER[b.status] || a.row - b.row,
  );
  const listed = sorted.slice(0, SHOWN);
  return (
    <div>
      <ul className="space-y-1 text-sm">
        {listed.map((r) => (
          <li
            key={r.row}
            className="flex flex-wrap items-baseline gap-x-3 border-t border-border-token py-1.5 first:border-t-0"
          >
            <span className="w-14 text-muted">{t("row", { row: r.row })}</span>
            <Badge tone={TONE[r.status]}>{t(`status.${r.status}`)}</Badge>
            <span>{[r.first_name, r.phone].filter(Boolean).join(" · ")}</span>
            {[...(r.errors ?? []), ...(r.warnings ?? [])].map((m) => (
              <span key={m} className="basis-full pl-14 text-xs text-muted">
                {m}
              </span>
            ))}
          </li>
        ))}
      </ul>
      {sorted.length > listed.length && (
        <p className="mt-2 text-xs text-muted">
          {t("moreRows", { count: sorted.length - listed.length })}
        </p>
      )}
    </div>
  );
}

function Batches() {
  const t = useTranslations("enrolment");
  const format = useFormatter();
  const batches = useEnrolmentBatches();

  // Below everything else on the panel, and a placeholder while it arrives: nothing above it moves.
  if (batches.isPending) return <Skeleton className="mt-6 h-16 w-full" />;
  if (batches.isError)
    return (
      <Alert role="alert" className="mt-6">
        {detailOf(batches.error) ?? t("failed")}
      </Alert>
    );
  const rows = batches.data ?? [];
  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
        {t("recent")}
      </h3>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("noBatches")}</p>
      ) : (
        <ul className="mt-2 space-y-2 text-sm">
          {rows.map((b) => (
            <li
              key={b.id}
              className="rounded-md border border-border-token p-3"
            >
              <p className="font-medium">{b.programme}</p>
              <p className="text-xs text-muted">
                {t("batchLine", {
                  when: format.dateTime(new Date(b.created_at), {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }),
                  operator: b.operator ?? t("formerOperator"),
                  version: b.attested_notice_version,
                })}
              </p>
              <p className="text-xs text-muted">
                {t("batchCounts", {
                  created: b.created,
                  tagged: b.tagged,
                  already: b.already,
                  errors: b.errors,
                })}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
