import { useRouter } from "expo-router";
import { useState } from "react";
import { Linking, Pressable, Switch, View } from "react-native";
import { useTranslations } from "use-intl";

import { WEB_BASE_URL } from "../src/config";
import { ApiError } from "../src/core/errors";
import { PRIVACY_NOTICE_VERSION, needsConsent, requestCode, verifyCode } from "../src/core/sign-in";
import { api, tokens, useLocale } from "../src/runtime";
import { Button, Notice, Screen, Text, TextField } from "../src/ui";
import { useCountdown } from "../src/ui/use-countdown";

type Step = "phone" | "code";

/**
 * Sign in or sign up by phone: one door, as on the web (ADR-032). Ask for a code, then verify it.
 *
 * **The agreement to the privacy notice is on the code step, as a box to tick**, because a number
 * with no account answers 428 only *after* its code has been used (asking sooner would reveal which
 * numbers are registered, ADR-038). A returning person need not tick it; somebody new who did not is
 * told, and asks for a new code. The notice itself is the website's page, opened in the browser:
 * one text, not two that can drift.
 */
export default function SignIn() {
  const t = useTranslations("auth");
  const m = useTranslations("mobile.signIn");
  const router = useRouter();
  const locale = useLocale();
  const wait = useCountdown();

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);

  const messageFor = (failure: unknown, fallback: string): string => {
    if (failure instanceof ApiError) {
      if (failure.status === 429 && failure.retryAfter) {
        wait.start(failure.retryAfter);
        return t("errorWait", { seconds: failure.retryAfter });
      }
      if (failure.status === 429) return t("errorRateLimited");
      if (failure.status === 422) return t("errorInvalidId");
    }
    return fallback;
  };

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const sent = await requestCode(api, phone.trim());
      wait.start(sent.resendAfterSeconds);
      setDevCode(__DEV__ ? sent.debugCode : null);
      setCode("");
      setStep("code");
    } catch (failure) {
      setError(messageFor(failure, t("errorGeneric")));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setError(null);
    try {
      await verifyCode(api, tokens, phone.trim(), code.trim(), agreed ? PRIVACY_NOTICE_VERSION : undefined);
      router.replace("/");
    } catch (failure) {
      setError(needsConsent(failure) ? m("needConsent") : messageFor(failure, t("errorBadCode")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Text variant="title">{step === "phone" ? t("signInTitle") : t("codeTitle")}</Text>

      {step === "phone" ? (
        <>
          <Text tone="muted">{t("signInSubtitle")}</Text>
          <TextField
            label={m("phoneLabel")}
            placeholder={m("phonePlaceholder")}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            autoComplete="tel"
            textContentType="telephoneNumber"
            maxLength={16}
          />
          {error ? <Notice tone="danger">{error}</Notice> : null}
          <Button
            label={busy ? t("sending") : t("sendCode")}
            onPress={() => void send()}
            busy={busy}
            disabled={phone.trim().length < 10}
          />
        </>
      ) : (
        <>
          <Text tone="muted">{t("codeSubtitle", { phone })}</Text>
          {devCode ? <Notice tone="warning">{t("devCodeNotice", { code: devCode })}</Notice> : null}
          <TextField
            label={t("codeLabel")}
            value={code}
            onChangeText={setCode}
            keyboardType="number-pad"
            // Android reads the code from the SMS; iOS offers it above the keyboard.
            autoComplete="sms-otp"
            textContentType="oneTimeCode"
            maxLength={6}
          />

          <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
            <Switch value={agreed} onValueChange={setAgreed} accessibilityLabel={m("consentAgree")} />
            <View style={{ flex: 1 }}>
              <Text>{m("consentAgree")}</Text>
              <Pressable
                accessibilityRole="link"
                onPress={() => void Linking.openURL(`${WEB_BASE_URL}/${locale}/privacy`)}
              >
                <Text tone="muted">{m("consentLink")}</Text>
              </Pressable>
            </View>
          </View>

          {error ? <Notice tone="danger">{error}</Notice> : null}
          <Button
            label={busy ? t("verifying") : t("verify")}
            onPress={() => void verify()}
            busy={busy}
            disabled={code.trim().length < 6}
          />
          <Button
            variant="secondary"
            label={wait.seconds > 0 ? t("resendIn", { seconds: wait.seconds }) : t("resend")}
            onPress={() => void send()}
            disabled={wait.seconds > 0 || busy}
          />
          <Button variant="secondary" label={t("changeNumber")} onPress={() => setStep("phone")} />
        </>
      )}
    </Screen>
  );
}
