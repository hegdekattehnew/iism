"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { Field, Input } from "@/components/ui/field";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens } from "@/lib/auth";
import { landingFor, lastContext } from "@/lib/context";
import { failedWith, type WaitError } from "@/lib/http";
import { useCountdown } from "@/lib/use-countdown";

type Step = "phone" | "code";

/**
 * One door, either key.
 *
 * ADR-032 decided the *credential* follows the actor type, and it still does at
 * registration. But since Sprint 13 one identity can hold a candidate profile
 * and organisations and can link both credentials, so at sign-in the credential
 * no longer says who you are. Two doors would ask a question the account can
 * already answer, and would punish exactly the people who linked both.
 *
 * An `@` is the whole detection. It is unambiguous here because a phone
 * normalises to digits and an address cannot avoid the character.
 */
const looksLikeEmail = (value: string) => value.includes("@");

export function SignInForm() {
  const t = useTranslations("auth");
  const router = useRouter();

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The number verified but has no account. Sign-in never creates one: that
  // needs consent to the privacy notice, which only signup asks for.
  const [unregistered, setUnregistered] = useState(false);
  // How long until another code may be asked for. The server enforces it; this keeps the
  // button honest so nobody has to press it to find out.
  const wait = useCountdown();

  const errorFor = (status: number | undefined, fallback: string) =>
    status === 429
      ? t("errorRateLimited")
      : status === 422
        ? t("errorInvalidId")
        : fallback;

  const request = useMutation({
    mutationFn: async () => {
      setError(null);
      const {
        data,
        error: err,
        response,
      } = looksLikeEmail(phone)
        ? await api.POST("/auth/email/otp/request", { body: { email: phone } })
        : await api.POST("/auth/otp/request", { body: { phone } });
      if (err || !data) throw failedWith(response);
      return data;
    },
    onSuccess: (data) => {
      setDevCode(data.debug_code ?? null);
      wait.start(data.resend_after_seconds);
      setStep("code");
    },
    onError: (e: WaitError) => {
      // Asking again too soon is not a failure to explain: count down, and say how long.
      if (Number(e.message) === 429 && e.retryAfter) {
        wait.start(e.retryAfter);
        setError(t("errorWait", { seconds: e.retryAfter }));
        return;
      }
      setError(errorFor(Number(e.message), t("errorGeneric")));
    },
  });

  const verify = useMutation({
    mutationFn: async () => {
      setError(null);
      setUnregistered(false);
      const {
        data,
        error: err,
        response,
      } = looksLikeEmail(phone)
        ? await api.POST("/auth/email/otp/verify", {
            body: { email: phone, code },
          })
        : await api.POST("/auth/otp/verify", { body: { phone, code } });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async (data) => {
      setTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      // Route on what the account holds, not on which key opened the door --
      // and not by preferring one role. This sent anyone with a personal
      // membership to `/matches`, so a candidate who also hires could never
      // be delivered to their organisation, and took `.find()` over an
      // unordered list for everyone else. `landingFor` honours where they
      // last were.
      const me = await api.GET("/auth/me");
      router.push(
        landingFor(me.data?.memberships ?? [], {
          organisationSlug: data.organisation_slug ?? null,
          last: lastContext(),
        }),
      );
    },
    onError: (e: Error) => {
      if (Number(e.message) === 428) {
        setUnregistered(true);
        return;
      }
      setError(errorFor(Number(e.message), t("errorBadCode")));
    },
  });

  return (
    <div className="mx-auto w-full max-w-sm">
      <h1 className="text-2xl font-bold tracking-tight">
        {step === "phone" ? t("signInTitle") : t("codeTitle")}
      </h1>
      <p className="mt-2 text-sm text-muted">
        {step === "phone" ? t("signInSubtitle") : t("codeSubtitle", { phone })}
      </p>

      {step === "phone" ? (
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate();
          }}
        >
          <Field label={t("identifierLabel")}>
            <Input
              name="identifier"
              type="text"
              autoComplete="username"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder={t("identifierPlaceholder")}
              className="px-4 py-3 text-base tracking-wide placeholder:text-muted"
            />
          </Field>
          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={request.isPending}
          >
            {request.isPending ? t("sending") : t("sendCode")}
          </Button>
          <p className="text-center text-sm text-muted">
            {t("noAccount")}{" "}
            {/* Sign-in is one door taking either credential, so the way out
                of it must not assume the person is a job seeker. */}
            <Link
              href="/signup"
              className="text-brand underline underline-offset-4 hover:text-brand-strong"
            >
              {t("signUpInstead")}
            </Link>
          </p>
        </form>
      ) : (
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            verify.mutate();
          }}
        >
          <Field label={t("codeLabel")}>
            <Input
              name="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="px-4 py-3 text-center text-2xl font-semibold tracking-[0.4em]"
            />
          </Field>

          {/* Development only: the API returns the code when no SMS provider is
              configured, so the flow is exercisable without one. */}
          {devCode && (
            <p className="rounded-lg border border-warning-border bg-warning-surface px-3 py-2 text-xs text-warning-text">
              {t("devCodeNotice", { code: devCode })}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={verify.isPending}
          >
            {verify.isPending ? t("verifying") : t("verify")}
          </Button>

          <div className="-mx-2 flex justify-between text-sm">
            <button
              type="button"
              onClick={() => {
                setStep("phone");
                setCode("");
                setDevCode(null);
                setError(null);
                setUnregistered(false);
              }}
              className="inline-flex min-h-11 items-center rounded-lg px-2 text-muted hover:text-foreground hover:underline"
            >
              {t("changeNumber")}
            </button>
            <button
              type="button"
              onClick={() => request.mutate()}
              disabled={request.isPending || wait.remaining > 0}
              className="inline-flex min-h-11 items-center rounded-lg px-2 text-brand hover:underline disabled:opacity-50 disabled:no-underline"
            >
              {wait.remaining > 0
                ? t("resendIn", { seconds: wait.remaining })
                : t("resend")}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-danger-border bg-danger-surface px-3 py-2 text-sm text-danger-text"
        >
          {error}
        </p>
      )}

      {unregistered && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-warning-border bg-warning-surface px-3 py-3 text-sm text-warning-text"
        >
          <p>{t("unregistered")}</p>
          <Link
            href="/signup/seeker"
            className="mt-1 inline-flex min-h-11 items-center font-medium underline underline-offset-4"
          >
            {t("unregisteredAction")}
          </Link>
        </div>
      )}
    </div>
  );
}
