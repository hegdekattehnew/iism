import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import {
  MESSAGE_MAX,
  applyFailureKey,
  canWithdraw,
  isLive,
  withdrawFailureKey,
} from "../core/applying";
import { isSignedOut, statusOf } from "../core/errors";
import {
  useAccount,
  useApplications,
  useApply,
  useSaved,
  useToggleSave,
  useWithdraw,
} from "../lib/me-queries";
import { space } from "../theme";
import { Badge } from "./list";
import { Button, Notice, Text, TextField } from "./primitives";
import { SessionExpired } from "./session";

/**
 * Apply, withdraw and save, on the vacancy page and on a match.
 *
 * **The confirm step is the consent moment**: it names the organisation, says exactly what applying
 * discloses (name, mobile number and email, for this vacancy only), and that withdrawing takes it
 * back. Nothing is pre-ticked and the button that discloses is the one labelled to disclose; the API
 * records the same act as `contact_shared_at`. The sentence is the web's own, from the same
 * catalogue, so the two cannot drift.
 *
 * An organisation-only account is offered nothing: it cannot apply, and an affordance that always
 * fails is worse than none. While the account is still loading nothing shows either.
 */
/**
 * Whether the panel has anything to show (Sprint 69, UI-08). The vacancy screen puts it in a bar
 * under the content, and an empty bar (an organisation-only account, or an account that is still
 * loading) would be a bordered strip with nothing in it. One rule, read by the panel and by the
 * screen, so the two cannot disagree about whether there is a panel.
 */
export function useApplyVisible(jobSlug: string, isOpen: boolean): boolean {
  const { signedIn, isJobSeeker } = useAccount();
  const applications = useApplications();
  const mine = applications.data?.find((a) => a.job.slug === jobSlug);
  const live = mine !== undefined && isLive(mine);
  if (!isOpen && !live) return true;
  if (!signedIn) return true;
  return isJobSeeker === true;
}

export function ApplyPanel({
  jobSlug,
  organisation,
  isOpen,
  compact = false,
}: {
  jobSlug: string;
  organisation: string;
  isOpen: boolean;
  /** Apply and Save side by side, for the bar under a vacancy: the bar must not take the screen. */
  compact?: boolean;
}) {
  const t = useTranslations("applications");
  const router = useRouter();
  const { signedIn, isJobSeeker } = useAccount();
  const applications = useApplications();
  const saved = useSaved();
  const apply = useApply();
  const withdraw = useWithdraw();
  const toggleSave = useToggleSave();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");

  const mine = applications.data?.find((a) => a.job.slug === jobSlug);
  const live = mine !== undefined && isLive(mine);
  const isSaved = saved.data?.some((s) => s.job.slug === jobSlug) ?? false;

  // **Before the sign-in prompt.** A closed vacancy takes nobody's application, so asking a signed-out
  // person to sign in first would walk them through an account to reach a refusal.
  if (!isOpen && !live) return <Notice tone="warning">{t("vacancyClosed")}</Notice>;
  if (!signedIn) {
    return <Button label={t("signInToApply")} onPress={() => router.push("/sign-in")} />;
  }
  if (isJobSeeker !== true) return null;

  // Side by side only while there are two buttons: asking for confirmation hides Apply.
  const row = compact && !confirming;
  const failure = apply.error ?? withdraw.error ?? toggleSave.error;
  const signedOut = failure !== null && isSignedOut(failure);

  return (
    <View style={{ gap: space.md }}>
      <View style={row ? { flexDirection: "row", gap: space.md, alignItems: "stretch" } : { gap: space.md }}>
        <View style={row ? { flex: 1 } : undefined}>
          {live && mine ? (
            <View style={{ gap: space.sm }}>
              <Badge
                tone={mine.status === "rejected" ? "warning" : "success"}
                // "Applied" for a live application, and the employer's own word once they have decided:
                // a rejected candidate told "Applied" is misled.
                label={mine.status === "applied" || mine.status === "shortlisted" ? t("appliedLabel") : t(`status.${mine.status}`)}
              />
              {canWithdraw(mine.status) ? (
                <Button
                  variant="secondary"
                  label={withdraw.isPending ? t("withdrawing") : t("withdraw")}
                  busy={withdraw.isPending}
                  onPress={() => withdraw.mutate(mine.id)}
                />
              ) : null}
            </View>
          ) : confirming ? null : (
            <Button label={t("apply")} onPress={() => setConfirming(true)} />
          )}
        </View>
        <View style={row ? { flex: 1 } : undefined}>
          <Button
            variant="secondary"
            label={isSaved ? t("savedLabel") : t("save")}
            busy={toggleSave.isPending}
            onPress={() => toggleSave.mutate({ slug: jobSlug, saved: isSaved })}
          />
        </View>
      </View>

      {confirming && !live ? (
        <View style={{ gap: space.md }}>
          <Text variant="lead">{t("confirmHeading")}</Text>
          {/* The disclosure, named in full, before the act that makes it. */}
          <Text>{t("confirmShare", { organisation })}</Text>
          <Text tone="muted">{t("confirmWithdrawNote")}</Text>
          <TextField
            label={t("messageLabel")}
            placeholder={t("messagePlaceholder")}
            value={message}
            onChangeText={setMessage}
            maxLength={MESSAGE_MAX}
            multiline
            numberOfLines={3}
          />
          <Button
            label={apply.isPending ? t("applying") : t("confirmCta")}
            busy={apply.isPending}
            onPress={() =>
              apply.mutate(
                { jobSlug, message },
                {
                  onSuccess: () => {
                    setConfirming(false);
                    setMessage("");
                  },
                },
              )
            }
          />
          <Button
            variant="secondary"
            label={t("cancel")}
            onPress={() => {
              setConfirming(false);
              apply.reset();
            }}
          />
        </View>
      ) : null}

      {signedOut ? (
        <SessionExpired />
      ) : apply.isError ? (
        <Notice tone="danger">{t(applyFailureKey(statusOf(apply.error)))}</Notice>
      ) : withdraw.isError ? (
        <Notice tone="danger">{t(withdrawFailureKey(statusOf(withdraw.error)))}</Notice>
      ) : toggleSave.isError ? (
        <Notice tone="danger">{t("errorGeneric")}</Notice>
      ) : null}
    </View>
  );
}
