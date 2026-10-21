"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, type ReactNode } from "react";

import { Field, Text } from "@/components/profile/fields";
import { Alert, Badge, Button, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { setTokens } from "@/lib/auth";
import { failedWith, type WaitError } from "@/lib/http";
import { useMemberships } from "@/lib/org";
import { useCountdown } from "@/lib/use-countdown";

type Channel = "phone" | "email";
type Mode = "idle" | "typing" | "code" | "removing";

/**
 * How this person gets in: add, change and remove (Sprint 56, BL-14.2, ADR-066).
 *
 * A one-time code is the only way into an account, so the phone number or email it goes to **is**
 * the account. People change numbers and lose them. The first version of this screen could only add
 * the credential that was missing; changing one meant nothing, and a number that was lost was an
 * account that was lost. Each act is a code to the **new** identifier, never the old one (the usual
 * reason to change it is that it is lost):
 *
 * * **add** one the account does not have;
 * * **change** the one it has. Every other session ends and this one is handed a fresh pair, so
 *   changing a number never signs the person out of the screen they changed it on (not storing that
 *   pair would do exactly that);
 * * **remove** one, only while another *verified* way in remains. The button is not offered
 *   otherwise, so the server's refusal is a backstop and not the explanation.
 *
 * Nothing is written until the code comes back: an unverified identifier on an account looks like a
 * verified one at a glance, which is how account-takeover-by-typo happens. A phone-only person is
 * asked to add an email, the one recovery that works before SMS is registered and the place a
 * notice of a change can be sent.
 */
export function CredentialsSection({ icon }: { icon?: ReactNode } = {}) {
  const t = useTranslations("credentials");
  const { data: me, isPending } = useMemberships();

  if (isPending) {
    return (
      <section className="rounded-xl border border-border-token bg-surface p-6">
        <div className="flex items-center gap-3">
          {icon}
          <h2 className="text-base font-semibold">{t("title")}</h2>
        </div>
        <Skeleton className="mt-4 h-28 w-full" />
      </section>
    );
  }
  if (!me) return null;

  const phoneVerified = Boolean(me.phone && me.phone_verified_at);
  const emailVerified = Boolean(me.email && me.email_verified_at);

  return (
    <section className="rounded-xl border border-border-token bg-surface p-6">
      {/* The account page passes a mark; the profile passes nothing, so the icon factory stays off
          the profile's first load (it has about 1 KB left). */}
      <div className="flex items-center gap-3">
        {icon}
        <h2 className="text-base font-semibold">{t("title")}</h2>
      </div>
      <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
      {me.phone && !me.email && (
        <Alert tone="info" role={undefined} className="mt-3">
          {t("addBackupEmail")}
        </Alert>
      )}
      <ul className="mt-4 space-y-2">
        <Row
          channel="phone"
          value={me.phone ?? null}
          verified={phoneVerified}
          canRemove={emailVerified}
        />
        <Row
          channel="email"
          value={me.email ?? null}
          verified={emailVerified}
          canRemove={phoneVerified}
        />
      </ul>
    </section>
  );
}

function Row({
  channel,
  value,
  verified,
  canRemove,
}: {
  channel: Channel;
  value: string | null;
  verified: boolean;
  canRemove: boolean;
}) {
  const t = useTranslations("credentials");
  const ta = useTranslations("auth");
  const qc = useQueryClient();

  const [mode, setMode] = useState<Mode>("idle");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wait = useCountdown();
  const held = value !== null;

  const finish = () => {
    setMode("idle");
    setIdentifier("");
    setCode("");
    setDevCode(null);
    setError(null);
    void qc.invalidateQueries({ queryKey: ["me"] });
  };

  // The answer in the person's own language, by what happened: the server's sentences are English.
  const say = (status: number, fallback: string) =>
    status === 409
      ? t("takenError")
      : status === 401
        ? t("codeError")
        : fallback;

  const ask = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, response } =
        channel === "phone"
          ? await api.POST("/me/credentials/phone", { body: { phone: identifier } })
          : await api.POST("/me/credentials/email", { body: { email: identifier } });
      if (!data) throw failedWith(response);
      return data;
    },
    onSuccess: (data) => {
      setDevCode(data.debug_code ?? null);
      wait.start(data.resend_after_seconds);
      setMode("code");
    },
    onError: (e: WaitError) => {
      if (Number(e.message) === 429 && e.retryAfter) {
        wait.start(e.retryAfter);
        setError(ta("errorWait", { seconds: e.retryAfter }));
        return;
      }
      setError(t("requestError"));
    },
  });

  const confirm = useMutation({
    mutationFn: async () => {
      setError(null);
      if (!held) {
        const { data, response } =
          channel === "phone"
            ? await api.POST("/me/credentials/phone/verify", {
                body: { phone: identifier, code },
              })
            : await api.POST("/me/credentials/email/verify", {
                body: { email: identifier, code },
              });
        if (!data) throw failedWith(response);
        return null;
      }
      const { data, response } =
        channel === "phone"
          ? await api.POST("/me/credentials/phone/replace", {
              body: { phone: identifier, code },
            })
          : await api.POST("/me/credentials/email/replace", {
              body: { email: identifier, code },
            });
      if (!data) throw failedWith(response);
      return data;
    },
    onSuccess: (changed) => {
      if (changed) setTokens(changed);
      finish();
    },
    onError: (e: Error) => setError(say(Number(e.message), t("failed"))),
  });

  const remove = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, response } =
        channel === "phone"
          ? await api.DELETE("/me/credentials/phone")
          : await api.DELETE("/me/credentials/email");
      if (!data) throw failedWith(response);
      return data;
    },
    onSuccess: (changed) => {
      setTokens(changed);
      finish();
    },
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("onlyWay") : t("failed")),
  });

  const what = channel === "phone" ? t("whatPhone") : t("whatEmail");

  return (
    <li className="rounded-lg border border-border-token bg-background px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{t(channel)}</p>
          <p className="text-sm text-muted">{value ?? t("notSet")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {held && (
            <Badge tone={verified ? "good" : "warn"}>
              {verified ? t("verified") : t("unverified")}
            </Badge>
          )}
          {mode === "idle" && (
            <>
              <Button size="sm" variant="secondary" onClick={() => setMode("typing")}>
                {held ? t("change") : t("add")}
              </Button>
              {held && canRemove && (
                <Button size="sm" variant="ghost" onClick={() => setMode("removing")}>
                  {t("remove")}
                </Button>
              )}
            </>
          )}
        </div>
      </div>
      {held && !canRemove && mode === "idle" && (
        <p className="mt-1 text-xs text-muted">{t("onlyWay")}</p>
      )}

      {mode === "typing" && (
        <form
          className="mt-3 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            ask.mutate();
          }}
        >
          <Field label={channel === "phone" ? t("phoneLabel") : t("emailLabel")}>
            <Text
              type={channel === "phone" ? "tel" : "email"}
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
          </Field>
          {held && <p className="text-xs text-muted">{t("changeNote")}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={ask.isPending || wait.remaining > 0}>
              {ask.isPending ? t("sending") : t("sendCode")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={finish}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      )}

      {mode === "code" && (
        <form
          className="mt-3 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            confirm.mutate();
          }}
        >
          <p className="text-sm text-muted">{t("codeSent", { to: identifier })}</p>
          <Field label={t("codeLabel")}>
            <Text
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              minLength={4}
              maxLength={8}
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </Field>
          {devCode && <p className="text-xs text-muted">{t("devCode", { code: devCode })}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" size="sm" disabled={confirm.isPending}>
              {confirm.isPending ? t("confirming") : held ? t("confirm") : t("verify")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => ask.mutate()}
              disabled={ask.isPending || wait.remaining > 0}
            >
              {wait.remaining > 0
                ? ta("resendIn", { seconds: wait.remaining })
                : ta("resend")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={finish}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      )}

      {mode === "removing" && (
        <Alert tone="warning" role={undefined} className="mt-3">
          <p>{t("removeConfirm", { what })}</p>
          <div className="mt-3 flex gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={() => remove.mutate()}
              disabled={remove.isPending}
            >
              {remove.isPending ? t("removing") : t("removeYes")}
            </Button>
            <Button variant="ghost" size="sm" onClick={finish}>
              {t("cancel")}
            </Button>
          </div>
        </Alert>
      )}

      {error && (
        <Alert className="mt-3" role="alert">
          {error}
        </Alert>
      )}
    </li>
  );
}
