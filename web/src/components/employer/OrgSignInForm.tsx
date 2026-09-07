"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens } from "@/lib/auth";

/**
 * Organisation sign-in and registration, by email and one-time passcode.
 *
 * The same shape as the candidate's phone form on purpose: ADR-038 keeps one
 * token path, and there is no reason the two should feel like different
 * products. No password, so there is nothing to reset and nothing to store.
 *
 * Registering an address that already has an account is **not** an error here.
 * The API sends a sign-in code instead and creates no second organisation, so
 * the form simply proceeds to the code step — which is both the friendlier
 * behaviour and the one that gives a prober nothing to read.
 */

type Mode = "signin" | "register";

export function OrgSignInForm() {
  const t = useTranslations("orgAuth");
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("signin");
  const [step, setStep] = useState<"details" | "code">("details");
  const [email, setEmail] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: async () => {
      setError(null);
      const call =
        mode === "register"
          ? api.POST("/auth/org/register", {
              body: {
                email,
                organisation_name: organisation,
                tenant_type: "employer" as const,
              },
            })
          : api.POST("/auth/email/otp/request", { body: { email } });
      const { data, error: err, response } = await call;
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => {
      setDevCode(data.debug_code ?? null);
      setStep("code");
    },
    onError: (e: Error) =>
      setError(
        Number(e.message) === 429
          ? t("errorRateLimited")
          : Number(e.message) === 422
            ? t("errorInvalidEmail")
            : t("errorGeneric"),
      ),
  });

  const verify = useMutation({
    mutationFn: async () => {
      setError(null);
      const {
        data,
        error: err,
        response,
      } = await api.POST("/auth/email/otp/verify", {
        body: { email, code },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async (data) => {
      setTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      // Land in the workspace they own. A person can own several, so the first
      // non-personal membership is the sensible default and the switcher
      // handles the rest.
      const me = await api.GET("/auth/me");
      const org = (me.data?.memberships ?? []).find(
        (m) => m.tenant.tenant_type !== "personal",
      );
      router.push(org ? `/employer/${org.tenant.slug}` : "/profile");
    },
    onError: (e: Error) =>
      setError(
        Number(e.message) === 429 ? t("errorRateLimited") : t("errorBadCode"),
      ),
  });

  return (
    <div className="mx-auto w-full max-w-sm">
      <div className="mb-6 flex gap-2">
        {(["signin", "register"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              setStep("details");
              setError(null);
            }}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
              mode === m
                ? "border-brand bg-accent-soft font-medium text-brand"
                : "border-border-token text-muted hover:text-foreground"
            }`}
          >
            {t(m)}
          </button>
        ))}
      </div>

      {step === "details" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate();
          }}
        >
          <Field label={t("emailLabel")} hint={t("emailHint")}>
            <Text
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="hiring@clinic.example"
            />
          </Field>

          {mode === "register" && (
            <Field label={t("organisationLabel")} className="mt-4">
              <Text
                required
                minLength={2}
                value={organisation}
                onChange={(e) => setOrganisation(e.target.value)}
                placeholder={t("organisationPlaceholder")}
              />
            </Field>
          )}

          <Button
            type="submit"
            className="mt-6 w-full"
            disabled={request.isPending}
          >
            {request.isPending ? t("sending") : t("sendCode")}
          </Button>
        </form>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            verify.mutate();
          }}
        >
          <p className="mb-4 text-sm text-muted">{t("codeSent", { email })}</p>
          <Field label={t("codeLabel")}>
            <Text
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </Field>
          {devCode && (
            // Development only: the API exposes the code when
            // OTP_EXPOSE_IN_RESPONSE is on, which production forbids outright.
            <p className="mt-2 text-xs text-muted">
              {t("devCode", { code: devCode })}
            </p>
          )}
          <Button
            type="submit"
            className="mt-6 w-full"
            disabled={verify.isPending}
          >
            {verify.isPending ? t("verifying") : t("verify")}
          </Button>
          <button
            type="button"
            onClick={() => setStep("details")}
            className="mt-3 w-full rounded-sm text-sm text-muted underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {t("changeEmail")}
          </button>
        </form>
      )}

      {error && (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
