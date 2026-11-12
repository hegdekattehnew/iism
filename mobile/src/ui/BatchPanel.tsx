import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { MESSAGE_MAX } from "../core/applying";
import { batchFailureText, registerState, type PublicBatch } from "../core/batches";
import { isSignedOut } from "../core/errors";
import { useAccount, useRegisterBatchInterest, useWithdrawBatchInterest } from "../lib/me-queries";
import { space } from "../theme";
import { Badge } from "./list";
import { Button, Notice, Text, TextField } from "./primitives";
import { SessionExpired } from "./session";

/**
 * Register interest in a batch, and take it back (Sprint 102, BL-20.5). **The confirm step is the
 * consent moment**: it names the centre that will receive the learner's name, phone, email and
 * district **and the organisation it belongs to**, and says nobody else sees them (the web's own
 * sentences). An organisation-only account is offered nothing, a full batch says so, and one that is
 * cancelled, running or over says that instead of a button the server would refuse.
 */
export function BatchPanel({ batch }: { batch: PublicBatch }) {
  const t = useTranslations("publicBatches");
  const router = useRouter();
  const { signedIn, isJobSeeker } = useAccount();
  const register = useRegisterBatchInterest();
  const withdraw = useWithdrawBatchInterest();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");
  const state = registerState(batch);

  if (!signedIn) {
    return <Button label={t("signInToRegister")} onPress={() => router.push("/sign-in")} />;
  }
  if (isJobSeeker !== true) return null;

  const failure = register.error ?? withdraw.error;
  const say = (k: string) => t(k);

  return (
    <View style={{ gap: space.md }}>
      {state.kind === "mine" ? (
        <View style={{ gap: space.sm }}>
          <Badge tone="success" label={t(`interestStatus.${state.status}`)} />
          <Button
            variant="secondary"
            label={withdraw.isPending ? t("withdrawing") : t("withdraw")}
            accessibilityLabel={t("withdrawNamed", { name: batch.course.title })}
            busy={withdraw.isPending}
            onPress={() => withdraw.mutate(state.interestId)}
          />
        </View>
      ) : state.kind === "full" ? (
        <Text tone="muted">{t("fullNote")}</Text>
      ) : state.kind === "closed" ? (
        <Text tone="muted">{t(`closedNote.${state.phase}`)}</Text>
      ) : confirming ? (
        <View style={{ gap: space.md }}>
          <Text variant="lead">{t("confirmHeading")}</Text>
          {/* The disclosure, named in full, before the act that makes it. */}
          <Text>{t("confirmShare", { centre: batch.centre.name, organisation: batch.organisation.name })}</Text>
          <Text tone="muted">{t("confirmWho")}</Text>
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
            label={register.isPending ? t("registering") : t("confirmCta")}
            busy={register.isPending}
            onPress={() =>
              register.mutate(
                { batchId: batch.id, message },
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
              register.reset();
            }}
          />
        </View>
      ) : (
        <Button
          label={t("register")}
          accessibilityLabel={t("registerNamed", { name: batch.course.title })}
          onPress={() => setConfirming(true)}
        />
      )}

      {failure && isSignedOut(failure) ? (
        <SessionExpired />
      ) : failure ? (
        <Notice tone="danger">{batchFailureText(failure, say)}</Notice>
      ) : null}
    </View>
  );
}
