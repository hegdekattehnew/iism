"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Badge, Button, Card, CardBody, Skeleton } from "@/components/ui";
import { statusOf } from "@/lib/http";
import { detailOf } from "@/lib/http";
import { NOTE_MAX, NOTE_MIN, useSetVerification, useVerificationDetail } from "@/lib/ops";

/**
 * One organisation, its badge, and every decision behind it.
 *
 * **The note is required and it is not a formality.** It is the only record of
 * why a candidate should believe the badge, so the control stays disabled
 * until there is one -- `min_length=10` on the server, mirrored here so the
 * browser says so before a request is made.
 *
 * **Revoking clears the tenant's evidence**, which is why the history is on
 * this page rather than tucked behind a link: after a revocation the log is
 * the only place the reason survives.
 */
export function OrganisationReview({ slug }: { slug: string }) {
  const t = useTranslations("ops");
  const format = useFormatter();
  const detail = useVerificationDetail(slug);
  const decide = useSetVerification(slug);
  const [note, setNote] = useState("");

  if (detail.isPending) return <Skeleton className="mt-8 h-64 w-full" />;

  if (detail.isError) {
    // A 404 here means the slug is not an organisation we can review -- a
    // personal workspace, or nothing at all. It is not an error state.
    const missing = statusOf(detail.error) === 404;
    return (
      <p className="mt-8 text-muted">{t(missing ? "unknownOrg" : "detailFailed")}</p>
    );
  }

  const data = detail.data;
  const ready = note.trim().length >= NOTE_MIN;

  const submit = (decision: "granted" | "revoked") => {
    decide.mutate({ decision, note: note.trim() }, { onSuccess: () => setNote("") });
  };

  return (
    <>
      <div className="mt-2 flex flex-wrap items-baseline gap-3">
        <h1 className="text-3xl font-bold tracking-tight">{data.name}</h1>
        <Badge tone={data.is_verified ? "good" : "neutral"}>
          {t(data.is_verified ? "verified" : "notVerified")}
        </Badge>
      </div>

      {data.is_verified && data.verified_at ? (
        <Card className="mt-6 border-success-border">
          <CardBody>
            <p className="text-sm text-muted">
              {t("verifiedOn", {
                date: format.dateTime(new Date(data.verified_at), { dateStyle: "long" }),
              })}
            </p>
            <p className="mt-2 text-sm">{data.verification_note}</p>
          </CardBody>
        </Card>
      ) : null}

      <Card className="mt-6">
        <CardBody>
          <h2 className="text-base font-semibold">{t("decideHeading")}</h2>
          <p className="mt-1 text-sm text-muted">{t("noteHelp")}</p>

          <label className="mt-4 block text-sm font-medium" htmlFor="ops-note">
            {t("noteLabel")}
          </label>
          <textarea
            id="ops-note"
            name="note"
            minLength={NOTE_MIN}
            maxLength={NOTE_MAX}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-input-border bg-surface px-3 py-2 text-sm"
            placeholder={t("notePlaceholder")}
          />

          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              onClick={() => submit("granted")}
              disabled={!ready || decide.isPending}
            >
              {t("grant")}
            </Button>
            {data.is_verified ? (
              <Button
                variant="secondary"
                onClick={() => submit("revoked")}
                disabled={!ready || decide.isPending}
              >
                {t("revoke")}
              </Button>
            ) : null}
          </div>

          {decide.isError ? (
            // What the server said, never a fixed sentence: it names the field
            // and the reason, and the generic line is the fallback for a
            // failure that carried nothing.
            <p className="mt-3 text-sm text-danger-text">
              {detailOf(decide.error) ?? t("decideFailed")}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <h2 className="mt-10 text-base font-semibold">{t("historyHeading")}</h2>
      {data.history.length === 0 ? (
        <p className="mt-2 text-muted">{t("historyEmpty")}</p>
      ) : (
        <ul className="mt-3">
          {data.history.map((event) => (
            <li
              key={event.id}
              className="border-t border-border-token py-3 first:border-t-0"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <Badge tone={event.decision === "granted" ? "good" : "warn"}>
                  {t(event.decision === "granted" ? "granted" : "revoked")}
                </Badge>
                <span className="text-sm text-muted">
                  {format.dateTime(new Date(event.created_at), { dateStyle: "medium" })}
                  {" · "}
                  {/* Null once that operator has exercised their own erasure.
                      The record about the organisation survives them. */}
                  {event.actor_name ?? t("formerOperator")}
                </span>
              </div>
              <p className="mt-1 text-sm">{event.note}</p>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
