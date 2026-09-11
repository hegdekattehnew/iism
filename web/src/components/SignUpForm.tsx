"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Text } from "@/components/profile/fields";
import { WELCOME_BACK } from "@/components/ReturningNotice";
import { Button, ButtonLink } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens, useIsSignedIn } from "@/lib/auth";
import { SEEKER, landingFor, lastContext } from "@/lib/context";
import { useMemberships } from "@/lib/org";

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
  // Two different forms, not one form with branches: they ask for different
  // things and call different endpoints, and hooks must not change order.
  return useIsSignedIn() ? (
    <AlreadySignedIn type={type} />
  ) : (
    <ColdSignUp type={type} />
  );
}

/**
 * Someone already signed in, arriving at a signup page.
 *
 * The homepage role chooser links every visitor to `/signup/employer`, and the
 * cold form behind it posted `/auth/org/register` with a fresh email -- which
 * minted a second `User`, forking the account (ADR-038). The API now refuses
 * to do that, and this is the interface not asking in the first place: an
 * organisation is added to the account you are already in, with no email and
 * no code, exactly as the header's "Create an organisation" does.
 */
function AlreadySignedIn({ type }: { type: SignUpType }) {
  const t = useTranslations("signup");
  const tc = useTranslations("context");
  const router = useRouter();
  const qc = useQueryClient();
  const { data, isPending, memberships } = useMemberships();
  const [organisation, setOrganisation] = useState("");

  const create = useMutation({
    mutationFn: async (tenant_type: "employer" | "course_provider") => {
      const { data: tenant, error } = await api.POST("/me/organisations", {
        body: { organisation_name: organisation, tenant_type },
      });
      if (error || !tenant) throw new Error("create failed");
      return tenant;
    },
    onSuccess: async (tenant) => {
      // The switcher labels contexts from `/auth/me`; the new one must reach it.
      await qc.invalidateQueries({ queryKey: ["me"] });
      router.push(`/employer/${tenant.slug}`);
    },
  });

  if (type === "seeker") {
    // Nothing to create. A job seeker already has the job-seeker side, and an
    // organisation-only account cannot acquire one through any route -- so
    // this offers the way on rather than a form that would fork the account.
    return (
      <div className="mx-auto w-full max-w-sm text-center">
        <p className="text-sm text-muted">{t("alreadySignedIn")}</p>
        {!isPending && data && (
          <ButtonLink
            href={landingFor(memberships, { last: lastContext() })}
            className="mt-4"
          >
            {t("continue")}
          </ButtonLink>
        )}
      </div>
    );
  }

  return (
    <form
      className="mx-auto w-full max-w-sm"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(TENANT_TYPE[type]);
      }}
    >
      <p className="mb-4 text-sm text-muted">{tc("createOrgHint")}</p>
      <Field label={t("orgNameLabel")}>
        <Text
          required
          minLength={2}
          value={organisation}
          onChange={(e) => setOrganisation(e.target.value)}
          placeholder={t(`${type}Placeholder`)}
        />
      </Field>
      <Button
        type="submit"
        size="lg"
        className="mt-6 w-full"
        disabled={create.isPending}
      >
        {create.isPending ? tc("creating") : tc("create")}
      </Button>
      {create.isError && (
        <p className="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
          {tc("createError")}
        </p>
      )}
    </form>
  );
}

function ColdSignUp({ type }: { type: SignUpType }) {
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
      // Only a signed-in caller gets an organisation back from this call, and
      // this form is for signed-out ones -- but a token that appeared since the
      // page rendered should land them in it, not strand them at a code prompt.
      if ("organisation_slug" in data && data.organisation_slug) {
        router.push(`/employer/${data.organisation_slug}`);
        return;
      }
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
      // A brand-new job seeker goes to the profile wizard. Anyone else who
      // "signed up" with a number or address that was already registered was
      // signed in -- deliberately, so the request stays no enumeration oracle
      // -- and is now told so, and landed on their workspace rather than
      // walked back through onboarding.
      if (isSeeker && data.created) {
        router.push("/profile");
        return;
      }
      const me = await api.GET("/auth/me");
      const target = landingFor(me.data?.memberships ?? [], {
        // The organisation this sign-in was for, named by the API. This used
        // to be `.find()` over an unordered list while the comment above it
        // claimed "the newest".
        organisationSlug: data.organisation_slug ?? null,
        // They came through the job-seeker door, so the job-seeker side is
        // what they meant, whatever they used last.
        last: isSeeker ? SEEKER : lastContext(),
      });
      router.push(data.created ? target : `${target}?${WELCOME_BACK}`);
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
          {/* Said up front, because the request cannot say it: a response
              that differed for a registered number would tell anyone which
              numbers are registered. */}
          <p className="mt-4 text-xs text-muted">
            {t(isSeeker ? "existingHintPhone" : "existingHintEmail")}
          </p>
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
