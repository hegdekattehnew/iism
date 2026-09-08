"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens } from "@/lib/auth";

/**
 * Signing up as one of the three things this marketplace is for.
 *
 * The type is chosen before a credential is asked for, because what to ask for
 * depends on it: a candidate gives a phone, an organisation gives an email and
 * a name. That follows ADR-032 — the credential is determined by actor type at
 * registration, in one place — and it is what makes a provider account possible
 * at all. Registration previously hardcoded `tenant_type: "employer"`, so a
 * training provider could not sign up through any surface in the product.
 *
 * Signing *in* is deliberately not like this: one door that takes either
 * identifier. After Sprint 13 one identity can hold both credentials and
 * several roles, so at sign-in the credential no longer says who you are.
 */

export type SignUpType = "seeker" | "employer" | "provider";

const TENANT_TYPE: Record<
  Exclude<SignUpType, "seeker">,
  "employer" | "course_provider"
> = {
  employer: "employer",
  provider: "course_provider",
};

export function SignUpForm({ type }: { type: SignUpType }) {
  const t = useTranslations("signup");
  const ta = useTranslations("auth");
  const router = useRouter();

  const isSeeker = type === "seeker";
  const [identifier, setIdentifier] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: async () => {
      setError(null);
      const {
        data,
        error: err,
        response,
      } = isSeeker
        ? await api.POST("/auth/otp/request", { body: { phone: identifier } })
        : await api.POST("/auth/org/register", {
            body: {
              email: identifier,
              organisation_name: organisation,
              tenant_type: TENANT_TYPE[type],
            },
          });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => {
      setDevCode(data.debug_code ?? null);
      setSent(true);
    },
    onError: (e: Error) =>
      setError(
        Number(e.message) === 429
          ? ta("errorRateLimited")
          : Number(e.message) === 422
            ? t("errorInvalid")
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
      } = isSeeker
        ? await api.POST("/auth/otp/verify", {
            body: { phone: identifier, code },
          })
        : await api.POST("/auth/email/otp/verify", {
            body: { email: identifier, code },
          });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async (data) => {
      setTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      });
      if (isSeeker) {
        router.push("/profile");
        return;
      }
      // Land in the organisation just created. A person may already hold
      // several, so the newest non-personal membership is the one they meant.
      const me = await api.GET("/auth/me");
      const org = (me.data?.memberships ?? []).find(
        (m) => m.tenant.tenant_type !== "personal",
      );
      router.push(org ? `/employer/${org.tenant.slug}` : "/profile");
    },
    onError: (e: Error) =>
      setError(
        Number(e.message) === 429 ? ta("errorRateLimited") : t("errorBadCode"),
      ),
  });

  return (
    <div className="mx-auto w-full max-w-sm">
      {!sent ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            request.mutate();
          }}
        >
          {isSeeker ? (
            <Field label={t("phoneLabel")} hint={t("phoneHint")}>
              <Text
                type="tel"
                inputMode="tel"
                required
                autoComplete="tel"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="98765 43210"
              />
            </Field>
          ) : (
            <>
              <Field label={t("orgNameLabel")}>
                <Text
                  required
                  minLength={2}
                  value={organisation}
                  onChange={(e) => setOrganisation(e.target.value)}
                  placeholder={t(`${type}Placeholder`)}
                />
              </Field>
              <Field
                label={t("emailLabel")}
                hint={t("emailHint")}
                className="mt-4"
              >
                <Text
                  type="email"
                  required
                  autoComplete="email"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                />
              </Field>
            </>
          )}

          <Button
            type="submit"
            size="lg"
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
          <p className="mb-4 text-sm text-muted">
            {t("codeSent", { to: identifier })}
          </p>
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
            <p className="mt-2 text-xs text-muted">
              {t("devCode", { code: devCode })}
            </p>
          )}
          <Button
            type="submit"
            size="lg"
            className="mt-6 w-full"
            disabled={verify.isPending}
          >
            {verify.isPending ? t("verifying") : t("verify")}
          </Button>
          <button
            type="button"
            onClick={() => {
              setSent(false);
              request.reset();
            }}
            className="mt-3 w-full rounded-sm text-sm text-muted underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {t("changeDetails")}
          </button>
        </form>
      )}

      {error && (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {error}
        </p>
      )}

      <p className="mt-6 text-center text-sm text-muted">
        {t("haveAccount")}{" "}
        <Link
          href="/signin"
          className="text-brand underline-offset-4 hover:underline"
        >
          {t("signInInstead")}
        </Link>
      </p>
    </div>
  );
}
