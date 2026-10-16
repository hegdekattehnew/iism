import { useState } from "react";
import { Linking, View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError, isSignedOut } from "../core/errors";
import { useConfirmConsent, useConsent, useWithdrawConsent } from "../lib/me-queries";
import { useInstantDate } from "../lib/months";
import { WEB_BASE_URL } from "../config";
import { useLocale } from "../runtime";
import { space } from "../theme";
import { Card } from "./list";
import { Button, Notice, Text } from "./primitives";
import { SessionExpired } from "./session";

/**
 * What the person agreed to, and the two things they can do about it without deleting anything
 * (the web's `ConsentSection`, Sprint 72, ADR-082): **withdraw consent**, with who holds their
 * details shown first, and **confirm the notice again** when it changed or after a withdrawal.
 *
 * Withdrawing is a pause, not an erasure, and the card says so; deleting sits beside it on the same
 * screen. The state comes from the server, never guessed here.
 */
export function ConsentCard() {
  const t = useTranslations("account");
  const tm = useTranslations("mobile.account");
  const locale = useLocale();
  const day = useInstantDate();
  const state = useConsent();
  const withdraw = useWithdrawConsent();
  const confirm = useConfirmConsent();
  const [confirming, setConfirming] = useState(false);

  const given = state.data;
  const pausedAt = given?.withdrawn ? given.consent_withdrawn_at : null;
  const agreedAt = given?.consented_at ?? null;
  const failure = (error: unknown, fallback: string) =>
    error instanceof ApiError && error.detail ? error.detail : fallback;

  return (
    <Card>
      <Text variant="lead">{t("consentTitle")}</Text>
      {state.isPending ? (
        <Text tone="muted">{t("loadingPreview")}</Text>
      ) : pausedAt ? (
        <Text tone="muted">{t("consentStatusPaused", { date: day(pausedAt) ?? "" })}</Text>
      ) : given?.consent_version && agreedAt ? (
        <Text tone="muted">{t("consentGiven", { version: given.consent_version, date: day(agreedAt) ?? "" })}</Text>
      ) : (
        <Text tone="muted">{t("consentMissing")}</Text>
      )}
      <Button
        variant="secondary"
        label={tm("readNotice")}
        onPress={() => void Linking.openURL(`${WEB_BASE_URL}/${locale}/privacy`)}
      />

      {given?.withdrawn ? (
        <View style={{ gap: space.md }}>
          <Text variant="lead">{t("restoreTitle")}</Text>
          <Text tone="muted">{t("restoreBody")}</Text>
          <Button
            label={confirm.isPending ? t("bannerConfirming") : t("restoreButton")}
            busy={confirm.isPending}
            onPress={() => confirm.mutate()}
          />
          {confirm.isError ? (
            isSignedOut(confirm.error) ? (
              <SessionExpired />
            ) : (
              <Notice tone="danger">{failure(confirm.error, t("bannerError"))}</Notice>
            )
          ) : null}
        </View>
      ) : given ? (
        <View style={{ gap: space.md }}>
          {given.current ? null : (
            <>
              <Text variant="lead">{t("bannerStaleTitle")}</Text>
              <Text tone="muted">{t("bannerStaleBody")}</Text>
              <Button
                label={confirm.isPending ? t("bannerConfirming") : t("bannerConfirm")}
                busy={confirm.isPending}
                onPress={() => confirm.mutate()}
              />
              {confirm.isError ? (
                isSignedOut(confirm.error) ? (
                  <SessionExpired />
                ) : (
                  <Notice tone="danger">{failure(confirm.error, t("bannerError"))}</Notice>
                )
              ) : null}
            </>
          )}
          <Text variant="lead">{t("withdrawTitle")}</Text>
          <Text tone="muted">{t("withdrawBody")}</Text>
          {!confirming ? (
            <Button variant="secondary" label={t("withdrawButton")} onPress={() => setConfirming(true)} />
          ) : (
            <View style={{ gap: space.md }}>
              <Text variant="lead">{t("withdrawPreviewTitle")}</Text>
              <Text>
                {given.live_applications + given.live_interests > 0
                  ? t("withdrawHolders", {
                      applications: given.live_applications,
                      interests: given.live_interests,
                    })
                  : t("withdrawNoHolders")}
              </Text>
              <Text>{`• ${t("withdrawEffectPool")}`}</Text>
              <Text>{`• ${t("withdrawEffectApply")}`}</Text>
              <Text>{`• ${t("withdrawEffectTrack")}`}</Text>
              <Text>{`• ${t("withdrawEffectStill")}`}</Text>
              {withdraw.isError ? (
                isSignedOut(withdraw.error) ? (
                  <SessionExpired />
                ) : (
                  <Notice tone="danger">{failure(withdraw.error, t("withdrawError"))}</Notice>
                )
              ) : null}
              <Button
                label={withdraw.isPending ? t("withdrawing") : t("withdrawConfirm")}
                busy={withdraw.isPending}
                onPress={() => withdraw.mutate()}
              />
              <Button
                variant="secondary"
                label={t("cancel")}
                onPress={() => {
                  setConfirming(false);
                  withdraw.reset();
                }}
              />
            </View>
          )}
        </View>
      ) : null}
    </Card>
  );
}
