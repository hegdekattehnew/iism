"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Text } from "@/components/profile/fields";
import { Alert, Button, Card, CardBody, Skeleton } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { setTokens, useIsSignedIn } from "@/lib/auth";
import { PRIVACY_NOTICE_VERSION } from "@/lib/legal";

/**
 * The one screen somebody sees before they have an account.
 *
 * Two ways through it, and the split is the whole of Sprint 25's risk:
 *
 * - **Signed in** — `POST /invitations/{token}/accept`. One identity, one more
 *   membership, never a second account (ADR-038).
 * - **Not signed in** — `claim` sends a code to the address the invitation was
 *   *written to* (never one typed here), and verifying it creates the account.
 *   That is the only path in the product where an email code creates an
 *   account, and `verify_email_and_sign_in` still answers 401 to an address
 *   with no invitation and no account.
 *
 * Consent is sent with the verification because this is a signup: an account
 * created without a recorded `consent_version` 428s on every request it makes
 * afterwards (Sprint 20).
 */


export function InvitePanel({ token }: { token: string }) {
  const t = useTranslations("invite");
  const signedIn = useIsSignedIn();
  const router = useRouter();
  const qc = useQueryClient();

  const [hint, setHint] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const invitation = useQuery({
    queryKey: ["invitation", token],
    retry: false,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/invitations/{token}", {
        params: { path: { token } },
      });
      if (error || !data) throw new Error(String(response.status));
      return data;
    },
  });

  const landOn = async (slug: string) => {
    // Everything the previous identity had cached is wrong now, and on a
    // shared phone it belongs to somebody else (Sprint 13's `qc.clear()`).
    await qc.invalidateQueries();
    router.push(`/employer/${slug}`);
  };

  const accept = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/invitations/{token}/accept", {
        params: { path: { token } },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => landOn(data.organisation_slug),
    onError: () => setError(t("errorGeneric")),
  });

  const claim = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err, response } = await api.POST("/invitations/{token}/claim", {
        params: { path: { token } },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: (data) => setHint(data.email_hint),
    onError: () => setError(t("errorGeneric")),
  });

  const verify = useMutation({
    mutationFn: async () => {
      setError(null);
      // **No address in this request.** It is read off the invitation server
      // side, which is why this endpoint exists instead of the client calling
      // `/auth/email/otp/verify`: a form that asked for an address would let a
      // forwarded link mint an account at an address of the holder's choosing.
      const { data, error: err, response } = await api.POST("/invitations/{token}/verify", {
        params: { path: { token } },
        body: { code, consent_version: PRIVACY_NOTICE_VERSION },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async (data) => {
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
      await landOn(data.organisation_slug ?? "");
    },
    onError: () => setError(t("errorGeneric")),
  });

  if (invitation.isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (invitation.isError) {
    const gone = invitation.error.message === "410";
    return (
      <Card>
        <CardBody>
          <h2 className="text-lg font-semibold">{t(gone ? "goneTitle" : "notFoundTitle")}</h2>
          <p className="mt-2 text-sm text-muted">{t(gone ? "goneBody" : "notFoundBody")}</p>
        </CardBody>
      </Card>
    );
  }

  const roleWord = t(invitation.data.role === "admin" ? "roleAdmin" : "roleMember");

  return (
    <Card>
      <CardBody>
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <p className="mt-2">
          {t("body", { organisation: invitation.data.organisation, role: roleWord })}
        </p>

        {signedIn ? (
          <>
            <p className="mt-4 text-sm text-muted">{t("signedInAs")}</p>
            <div className="mt-4">
              <Button size="lg" disabled={accept.isPending} onClick={() => accept.mutate()}>
                {accept.isPending ? t("accepting") : t("accept")}
              </Button>
            </div>
          </>
        ) : hint === null ? (
          <>
            <p className="mt-4 text-sm text-muted">{t("needAccount")}</p>
            <div className="mt-4">
              <Button size="lg" disabled={claim.isPending} onClick={() => claim.mutate()}>
                {claim.isPending ? t("sending") : t("sendCode")}
              </Button>
            </div>
          </>
        ) : (
          <form
            className="mt-4"
            onSubmit={(e) => {
              e.preventDefault();
              verify.mutate();
            }}
          >
            <p className="text-sm text-muted">{t("codeSent", { hint })}</p>
            <label className="mt-3 block text-sm">
              <span className="font-medium">{t("codeLabel")}</span>
              <Text
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            <p className="mt-2 text-xs text-muted">{t("consent")}</p>
            <div className="mt-4">
              <Button type="submit" size="lg" disabled={verify.isPending}>
                {verify.isPending ? t("verifying") : t("verify")}
              </Button>
            </div>
          </form>
        )}

        {error && (
          <Alert className="mt-3">
            {error}
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}
