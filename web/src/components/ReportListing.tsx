"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, Select } from "@/components/profile/fields";
import { Alert, Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { detailOf, statusOf } from "@/lib/http";
import {
  DETAIL_MAX,
  REASONS,
  type ReportReason,
  type TargetType,
  useReportListing,
} from "@/lib/moderation";

/**
 * "Report this listing" on a vacancy or a course (Sprint 59, BL-14.4, ADR-069).
 *
 * A disclosure rather than a dialog: Radix's dialog is ~33 KB of a first-load budget this page
 * shares with every other. **A report is accountable, so it needs an account**: signed out, the
 * control says to sign in instead of offering a form that cannot succeed. The server's own
 * sentences are shown for the two refusals a person can act on ("you manage this listing" and
 * "you have already reported it"), and the person is told only that it was received: what an
 * operator decides, and who reported, are not for them or the organisation to be told.
 */
export function ReportListing({
  kind,
  slug,
}: {
  kind: TargetType;
  slug: string;
}) {
  const t = useTranslations("reportListing");
  const signedIn = useIsSignedIn();
  const report = useReportListing(kind, slug);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>("fake_or_misleading");
  const [detail, setDetail] = useState("");

  if (!signedIn) {
    return (
      <p className="text-sm text-muted">
        {t("signedOut")}{" "}
        <Link
          href="/signin"
          className="text-brand underline underline-offset-2"
        >
          {t("signIn")}
        </Link>
      </p>
    );
  }

  if (report.isSuccess) {
    return (
      <Alert tone="success" role="status">
        {t("received")}
      </Alert>
    );
  }

  const status = statusOf(report.error);
  const failure =
    status === 429
      ? t("tooMany")
      : status === 401
        ? t("signedOut")
        : (detailOf(report.error) ?? t("failed"));

  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-sm text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        {t(kind === "job" ? "openJob" : "openCourse")}
      </button>
      {open && (
        <form
          className="mt-3 space-y-3 rounded-xl border border-border-token bg-surface p-4"
          onSubmit={(event) => {
            event.preventDefault();
            report.mutate({ reason, detail: detail.trim() });
          }}
        >
          <p className="text-sm text-muted">{t("intro")}</p>
          <Field label={t("reasonLabel")}>
            <Select
              name="reason"
              value={reason}
              onChange={(event) =>
                setReason(event.target.value as ReportReason)
              }
            >
              {REASONS.map((value) => (
                <option key={value} value={value}>
                  {t(`reason.${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("detailLabel")} hint={t("detailHint")}>
            <Area
              name="detail"
              rows={3}
              maxLength={DETAIL_MAX}
              value={detail}
              onChange={(event) => setDetail(event.target.value)}
            />
          </Field>
          {report.isError && <Alert role="alert">{failure}</Alert>}
          <Button type="submit" disabled={report.isPending}>
            {report.isPending ? t("sending") : t("send")}
          </Button>
        </form>
      )}
    </div>
  );
}
