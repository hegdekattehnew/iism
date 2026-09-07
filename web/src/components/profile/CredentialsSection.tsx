"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Text } from "@/components/profile/fields";
import { Badge, Button } from "@/components/ui";
import { api } from "@/lib/api";

/**
 * The two ways into this account, and adding the one that is missing.
 *
 * The linking half of ADR-038 had no interface at all: `POST
 * /me/credentials/{email,phone}` existed, was tested, and was called from
 * nowhere. That mattered more than it sounds — a phone-only candidate could not
 * attach the email address that lets the organisation sign-in path recognise
 * them, so the two halves of one person could never meet.
 *
 * Nothing is written until the code comes back. An unverified identifier sitting
 * on an account looks exactly like a verified one at a glance, which is how
 * account-takeover-by-typo happens.
 */
export function CredentialsSection() {
  const t = useTranslations("credentials");
  const qc = useQueryClient();
  const [adding, setAdding] = useState<"email" | "phone" | null>(null);
  const [value, setValue] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const { data, error: err } = await api.GET("/auth/me");
      if (err || !data) throw new Error("not signed in");
      return data;
    },
    retry: false,
  });

  const request = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err } =
        adding === "email"
          ? await api.POST("/me/credentials/email", { body: { email: value } })
          : await api.POST("/me/credentials/phone", { body: { phone: value } });
      if (err || !data) throw new Error("request failed");
      return data;
    },
    onSuccess: (d) => setDevCode(d.debug_code ?? null),
    onError: () => setError(t("requestError")),
  });

  const verify = useMutation({
    mutationFn: async () => {
      setError(null);
      const {
        data,
        error: err,
        response,
      } = adding === "email"
        ? await api.POST("/me/credentials/email/verify", {
            body: { email: value, code },
          })
        : await api.POST("/me/credentials/phone/verify", {
            body: { phone: value, code },
          });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me"] });
      setAdding(null);
      setValue("");
      setCode("");
      setDevCode(null);
    },
    // 409 is the one worth naming: the identifier belongs to another account,
    // and merging two accounts is not something a form should do silently.
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("takenError") : t("codeError")),
  });

  const d = me.data;

  const row = (
    kind: "phone" | "email",
    present: string | null,
    verified: boolean,
  ) => (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-token bg-background px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium">{t(kind)}</p>
        <p className="text-sm text-muted">{present ?? t("notSet")}</p>
      </div>
      {present ? (
        verified ? (
          <Badge tone="good">{t("verified")}</Badge>
        ) : (
          <Badge tone="warn">{t("unverified")}</Badge>
        )
      ) : (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setAdding(kind);
            setValue("");
            setCode("");
            setDevCode(null);
            setError(null);
          }}
        >
          {t("add")}
        </Button>
      )}
    </div>
  );

  return (
    <section className="rounded-xl border border-border-token bg-surface p-6">
      <h2 className="text-base font-semibold">{t("title")}</h2>
      <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>

      <div className="mt-4 space-y-2">
        {row("phone", d?.phone ?? null, d?.phone_verified_at != null)}
        {row("email", d?.email ?? null, d?.email_verified_at != null)}
      </div>

      {adding && (
        <form
          className="mt-4 rounded-lg border border-border-token p-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (devCode === null && !request.isSuccess) request.mutate();
            else verify.mutate();
          }}
        >
          <Field label={adding === "email" ? t("emailLabel") : t("phoneLabel")}>
            <Text
              type={adding === "email" ? "email" : "tel"}
              required
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={request.isSuccess}
            />
          </Field>

          {request.isSuccess && (
            <>
              <Field label={t("codeLabel")} className="mt-3">
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
            </>
          )}

          {error && (
            <p className="mt-3 text-sm text-rose-700 dark:text-rose-400">
              {error}
            </p>
          )}

          <div className="mt-4 flex gap-3">
            <Button
              type="submit"
              size="sm"
              disabled={request.isPending || verify.isPending}
            >
              {request.isSuccess ? t("verify") : t("sendCode")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => {
                setAdding(null);
                request.reset();
              }}
            >
              {t("cancel")}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
