"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Area } from "@/components/profile/fields";
import { Alert, Button, ButtonLink } from "@/components/ui";
import { StatusChip } from "@/components/ui/status-chip";
import { BATCH_INTEREST_LOOK } from "@/components/cards/batch-interest-look";
import { useBatchInterestMutations, type PublicBatch } from "@/lib/batches";
import { useIsSignedIn } from "@/lib/auth";
import { detailOf } from "@/lib/http";
import { REPLY_WITHIN_DAYS, replyBy } from "@/lib/interest-reply";
import { useMemberships } from "@/lib/org";

/**
 * Register interest in a batch (Sprint 100, ADR-103, BL-20.3), and take it back.
 *
 * **The confirm step is the consent moment**: it names the centre that will receive the learner's
 * name, phone, email, place and message **and the organisation it belongs to**, says nobody else
 * sees them (not the organisation that sells the course, unless it is the same one) and that
 * withdrawing takes them off the centre's screen. Registering again after withdrawing reuses the
 * row. When it is unanswered the learner is given the date a reply is expected by, as an ask and
 * never a promise (`lib/interest-reply`, the one number the centre's "Waiting n days" also reads).
 *
 * An organisation-only account is offered nothing: it cannot register, and a control that always
 * fails is worse than none. A full batch offers nothing to press and says so.
 */
export function RegisterBatch({ batch }: { batch: PublicBatch }) {
  const t = useTranslations("publicBatches");
  const format = useFormatter();
  const signedIn = useIsSignedIn();
  const { isJobSeeker, isPending: membershipsPending } = useMemberships();
  const { register, withdraw } = useBatchInterestMutations();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");
  const mine = batch.my_interest;

  if (!signedIn) {
    return (
      <div className="mt-4">
        <ButtonLink href="/signin" variant="secondary">
          {t("signInToRegister")}
        </ButtonLink>
      </div>
    );
  }
  // Nothing while we do not know which this is, and nothing for an organisation: a button that
  // appears and then vanishes is worse than one that arrives a moment late.
  if (membershipsPending || !isJobSeeker) return null;

  const failure = register.error ?? withdraw.error;
  const reason = (error: unknown) => {
    const status = (error as { status?: number } | null)?.status;
    return status === 409 || status === 404 || status === 429
      ? (detailOf(error) ?? t("failed"))
      : status === 403
        ? t("errorSeeker")
        : (detailOf(error) ?? t("failed"));
  };

  return (
    <div className="mt-4">
      {mine ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip
              tone={BATCH_INTEREST_LOOK[mine.status].tone}
              icon={BATCH_INTEREST_LOOK[mine.status].icon}
            >
              {t(`interestStatus.${mine.status}`)}
            </StatusChip>
            <Button
              size="sm"
              variant="ghost"
              disabled={withdraw.isPending}
              aria-label={t("withdrawNamed", { name: batch.course.title })}
              onClick={() => withdraw.mutate(mine.id)}
            >
              {withdraw.isPending ? t("withdrawing") : t("withdraw")}
            </Button>
          </div>
        </div>
      ) : batch.phase === "full" ? (
        <p className="text-sm text-muted">{t("fullNote")}</p>
      ) : !confirming ? (
        <Button
          aria-label={t("registerNamed", { name: batch.course.title })}
          onClick={() => setConfirming(true)}
        >
          {t("register")}
        </Button>
      ) : (
        <div className="rounded-xl border border-border-token bg-surface p-4">
          <h4 className="text-base font-semibold">{t("confirmHeading")}</h4>
          {/* The disclosure, named in full, before the act that makes it. */}
          <p className="mt-2 text-sm">
            {t("confirmShare", { centre: batch.centre.name, organisation: batch.organisation.name })}
          </p>
          <p className="mt-1 text-sm text-muted">{t("confirmWho")}</p>
          <p className="mt-1 text-sm text-muted">{t("confirmWithdrawNote")}</p>
          <label className="mt-4 block text-sm">
            <span className="font-medium">{t("messageLabel")}</span>
            <Area
              name="message"
              value={message}
              maxLength={1000}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t("messagePlaceholder")}
            />
          </label>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              disabled={register.isPending}
              onClick={() =>
                register.mutate(
                  { batchId: batch.id, message: message.trim() || null },
                  {
                    onSuccess: () => {
                      setConfirming(false);
                      setMessage("");
                    },
                  },
                )
              }
            >
              {register.isPending ? t("registering") : t("confirmCta")}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setConfirming(false);
                register.reset();
              }}
            >
              {t("cancel")}
            </Button>
          </div>
        </div>
      )}

      {/* Right under the proof that it worked: when to expect an answer (a date asked for, never
          promised). The list is public and carries no registration time, so this is shown from what
          the registration itself answered; the learner's own list shows it from the interest. */}
      {mine?.status === "registered" && register.data && (
        <p className="mt-3 text-sm" role="status">
          <span className="font-medium">
            {t("replyBy", {
              date: format.dateTime(replyBy(register.data.registered_at), { dateStyle: "medium" }),
            })}
          </span>
          <span className="block text-muted">{t("replyHelp", { days: REPLY_WITHIN_DAYS })}</span>
        </p>
      )}

      {failure != null && (
        <Alert role="alert" className="mt-3">
          {reason(failure)}
        </Alert>
      )}
    </div>
  );
}
