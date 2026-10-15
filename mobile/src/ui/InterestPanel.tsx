import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { MESSAGE_MAX, applyFailureKey } from "../core/applying";
import { isSignedOut, statusOf } from "../core/errors";
import { useAccount, useInterests, useRegisterInterest, useWithdrawInterest } from "../lib/me-queries";
import { space } from "../theme";
import { Badge } from "./list";
import { Button, Notice, Text, TextField } from "./primitives";
import { SessionExpired } from "./session";

/**
 * "I'm interested in this course", and taking it back. **The confirm step is the consent moment**
 * and names the provider and what they will see (name, phone, email, district), the web's own
 * sentence. Registering interest is not enrolling: whether somebody enrolled is a fact the provider
 * owns. An organisation-only account is offered nothing.
 */
export function InterestPanel({ courseSlug, organisation }: { courseSlug: string; organisation: string }) {
  const t = useTranslations("courseInterest");
  const router = useRouter();
  const { signedIn, isJobSeeker } = useAccount();
  const interests = useInterests();
  const register = useRegisterInterest();
  const withdraw = useWithdrawInterest();
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");

  const mine = interests.data?.find((i) => i.course.slug === courseSlug);
  const live = mine !== undefined && mine.status !== "withdrawn";

  if (!signedIn) {
    return <Button label={t("signInToRegister")} onPress={() => router.push("/sign-in")} />;
  }
  if (isJobSeeker !== true) return null;

  const failure = register.error ?? withdraw.error;

  return (
    <View style={{ gap: space.md }}>
      {live && mine ? (
        <View style={{ gap: space.sm }}>
          <Badge tone="success" label={t("registeredLabel")} />
          <Button
            variant="secondary"
            label={withdraw.isPending ? t("withdrawing") : t("withdraw")}
            busy={withdraw.isPending}
            onPress={() => withdraw.mutate(mine.id)}
          />
        </View>
      ) : confirming ? null : (
        <Button label={t("register")} onPress={() => setConfirming(true)} />
      )}

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
            label={register.isPending ? t("registering") : t("confirmCta")}
            busy={register.isPending}
            onPress={() =>
              register.mutate(
                { courseSlug, message },
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
      ) : null}

      {failure && isSignedOut(failure) ? (
        <SessionExpired />
      ) : register.isError ? (
        <Notice tone="danger">{t(applyFailureKey(statusOf(register.error)))}</Notice>
      ) : withdraw.isError ? (
        <Notice tone="danger">{t("errorGeneric")}</Notice>
      ) : null}
    </View>
  );
}
