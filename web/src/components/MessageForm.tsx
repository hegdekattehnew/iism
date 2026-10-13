"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, Text } from "@/components/profile/fields";
import { Alert, Button, ButtonLink } from "@/components/ui";
import { useIsSignedIn } from "@/lib/auth";
import {
  BODY_MAX,
  BODY_MIN,
  REPLY_TO_MAX,
  type GrievanceKind,
  type Submitted,
  useSendGrievance,
} from "@/lib/grievances";
import { detailOf, statusOf } from "@/lib/http";
import { useCountdown } from "@/lib/use-countdown";

/**
 * One form behind two pages (Sprint 57, BL-14.3, ADR-067): `/contact` and `/grievance`.
 *
 * **We never write to an address a stranger typed.** A signed-out sender is asked for somewhere to
 * reply, and an operator answers out of band; a signed-in sender is answered through their account
 * and needs to give nothing. So the screen says plainly, on success, what will and will not happen.
 *
 * **A request about your own data needs the account**, because the account is the proof of who is
 * asking. A signed-out person who picks it is told to sign in rather than shown a form that cannot
 * succeed.
 *
 * `website` is a honeypot: a field no person sees or reaches, which a bot fills. It is answered
 * with a success and stores nothing.
 */
export function MessageForm({ kinds }: { kinds: GrievanceKind[] }) {
  const t = useTranslations("messageForm");
  const signedIn = useIsSignedIn();
  const send = useSendGrievance();
  const wait = useCountdown();

  const [kind, setKind] = useState<GrievanceKind>(kinds[0]);
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [done, setDone] = useState<Submitted | null>(null);

  if (done) {
    return (
      <Alert tone="success" role="status" className="space-y-2">
        <p className="font-semibold">{t("sentTitle")}</p>
        <p>
          {t("reference")}{" "}
          <span
            className="font-mono font-semibold"
            data-testid="grievance-reference"
          >
            {done.reference}
          </span>
        </p>
        {done.kind === "contact" ? (
          <p>{t("sentContact")}</p>
        ) : (
          <p>
            {t("sentPromise", {
              hours: done.acknowledge_within_hours,
              days: done.resolve_within_days,
            })}
          </p>
        )}
        <p>{signedIn ? t("sentSignedIn") : t("sentSignedOut")}</p>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setDone(null);
            setBody("");
            setReplyTo("");
            send.reset();
          }}
        >
          {t("another")}
        </Button>
      </Alert>
    );
  }

  const needsAccount = kind === "data_request" && !signedIn;
  const needsReplyTo = !signedIn;
  const ready =
    body.trim().length >= BODY_MIN &&
    (!needsReplyTo || replyTo.trim().length > 0) &&
    !needsAccount;

  const failure = send.error;
  const status = statusOf(failure);
  const message =
    status === 429
      ? t("errorWait", {
          seconds: Math.max(wait.remaining, 1),
        })
      : status === 401
        ? t("errorSignIn")
        : (detailOf(failure) ?? t("errorGeneric"));

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!ready || send.isPending || wait.remaining > 0) return;
        send.mutate(
          {
            kind,
            body: body.trim(),
            reply_to: needsReplyTo ? replyTo.trim() : undefined,
            website: honeypot,
          },
          {
            onSuccess: (data) => setDone(data),
            onError: (error) => {
              const seconds = (error as { retryAfter?: number }).retryAfter;
              if (seconds) wait.start(seconds);
            },
          },
        );
      }}
    >
      {kinds.length > 1 && (
        <fieldset>
          <legend className="text-sm font-medium">{t("kindLegend")}</legend>
          <div className="mt-2 space-y-2">
            {kinds.map((option) => (
              <label key={option} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="kind"
                  value={option}
                  checked={kind === option}
                  onChange={() => setKind(option)}
                  className="mt-0.5 h-4 w-4 accent-brand"
                />
                <span>
                  <span className="font-medium">{t(`kind.${option}`)}</span>
                  <span className="block text-xs text-muted">
                    {t(`kindHint.${option}`)}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {needsAccount ? (
        <Alert tone="info" role={undefined} className="space-y-3">
          <p>{t("dataRequestSignIn")}</p>
          <ButtonLink href="/signin" size="sm">
            {t("signIn")}
          </ButtonLink>
        </Alert>
      ) : (
        <>
          <Field
            label={t("bodyLabel")}
            hint={t("bodyHint", { min: BODY_MIN, max: BODY_MAX })}
          >
            <Area
              name="body"
              rows={6}
              required
              minLength={BODY_MIN}
              maxLength={BODY_MAX}
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
            <span className="mt-1 block text-xs text-muted tabular-nums">
              {t("counter", { used: body.length, max: BODY_MAX })}
            </span>
          </Field>

          {needsReplyTo && (
            <Field label={t("replyToLabel")} hint={t("replyToHint")}>
              <Text
                name="reply_to"
                required
                maxLength={REPLY_TO_MAX}
                autoComplete="email"
                value={replyTo}
                onChange={(event) => setReplyTo(event.target.value)}
              />
            </Field>
          )}

          {/* The honeypot: out of sight, out of the tab order, out of the accessibility tree. */}
          <div
            aria-hidden="true"
            className="absolute left-[-10000px] h-px w-px overflow-hidden"
          >
            <label>
              {t("honeypotLabel")}
              <input
                type="text"
                name="website"
                tabIndex={-1}
                autoComplete="off"
                value={honeypot}
                onChange={(event) => setHoneypot(event.target.value)}
              />
            </label>
          </div>

          {send.isError && <Alert role="alert">{message}</Alert>}

          <Button
            type="submit"
            disabled={!ready || send.isPending || wait.remaining > 0}
          >
            {send.isPending ? t("sending") : t("send")}
          </Button>
        </>
      )}
    </form>
  );
}
