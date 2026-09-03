"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens } from "@/lib/auth";

type Step = "phone" | "code";

export function SignInForm() {
  const t = useTranslations("auth");
  const router = useRouter();

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const errorFor = (status: number | undefined, fallback: string) =>
    status === 429 ? t("errorRateLimited") : status === 422 ? t("errorInvalidPhone") : fallback;

  const request = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/auth/otp/request", {
        body: { phone },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => {
      setDevCode(data.debug_code ?? null);
      setStep("code");
    },
    onError: (e: Error) => setError(errorFor(Number(e.message), t("errorGeneric"))),
  });

  const verify = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/auth/otp/verify", {
        body: { phone, code },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => {
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
      router.push("/profile");
    },
    onError: (e: Error) => setError(errorFor(Number(e.message), t("errorBadCode"))),
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
          <div>
            <label htmlFor="phone" className="text-sm font-medium">
              {t("phoneLabel")}
            </label>
            <input
              id="phone"
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder={t("phonePlaceholder")}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-surface px-4 py-3 text-base tracking-wide placeholder:text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={request.isPending}>
            {request.isPending ? t("sending") : t("sendCode")}
          </Button>
        </form>
      ) : (
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            verify.mutate();
          }}
        >
          <div>
            <label htmlFor="code" className="text-sm font-medium">
              {t("codeLabel")}
            </label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="mt-1.5 w-full rounded-lg border border-border-token bg-surface px-4 py-3 text-center text-2xl font-semibold tracking-[0.4em] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            />
          </div>

          {/* Development only: the API returns the code when no SMS provider is
              configured, so the flow is exercisable without one. */}
          {devCode && (
            <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
              {t("devCodeNotice", { code: devCode })}
            </p>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={verify.isPending}>
            {verify.isPending ? t("verifying") : t("verify")}
          </Button>

          <div className="flex justify-between text-sm">
            <button
              type="button"
              onClick={() => {
                setStep("phone");
                setCode("");
                setDevCode(null);
                setError(null);
              }}
              className="text-muted hover:text-foreground hover:underline"
            >
              {t("changeNumber")}
            </button>
            <button
              type="button"
              onClick={() => request.mutate()}
              disabled={request.isPending}
              className="text-brand hover:underline disabled:opacity-50"
            >
              {t("resend")}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
        >
          {error}
        </p>
      )}
    </div>
  );
}
