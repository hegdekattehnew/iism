"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { clearTokens, useIsSignedIn } from "@/lib/auth";
import { forgetContext } from "@/lib/context";
import { useMemberships } from "@/lib/org";

/**
 * The DPDP Act 2023 rights, self-served: see what was agreed, download
 * everything held, and delete the account.
 *
 * Deleting is two steps, and the second shows what goes with it *before* the
 * button that does it -- fetched from the API, not guessed here, because only
 * the API knows which organisations have no other member. An organisation
 * someone else still belongs to blocks deletion outright rather than being
 * left with nobody able to run it.
 */
export function AccountPanel() {
  const t = useTranslations("account");
  // Two components, not one with an early return: hooks must not change order.
  return useIsSignedIn() ? (
    <SignedIn />
  ) : (
    <p className="mt-8 text-sm text-muted">
      {t("signedOut")}{" "}
      <Link href="/signin" className="text-brand underline-offset-4 hover:underline">
        {t("signIn")}
      </Link>
    </p>
  );
}

const ALERT =
  "mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 " +
  "dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300";

function SignedIn() {
  const t = useTranslations("account");
  const format = useFormatter();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMemberships();
  const [confirming, setConfirming] = useState(false);

  const preview = useQuery({
    queryKey: ["me", "deletion"],
    enabled: confirming,
    queryFn: async () => {
      const { data, error } = await api.GET("/me/account/deletion");
      if (error || !data) throw new Error("preview failed");
      return data;
    },
  });

  const download = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.GET("/me/account/export");
      if (error || !data) throw new Error("export failed");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `iism-my-data-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/me/account");
      if (error || !response.ok) throw new Error(String(response.status));
    },
    onSuccess: () => {
      // The server has already revoked every refresh token. What remains is
      // this browser: tokens, the remembered context, and every cached query --
      // the same three things signing out clears, for the same reason.
      clearTokens();
      forgetContext();
      qc.clear();
      router.push("/");
    },
  });

  const going = preview.data?.organisations_deleted ?? [];
  const blocked = preview.data?.blocked_by ?? [];

  return (
    <div className="mt-8 space-y-6">
      <section
        aria-labelledby="consent-heading"
        className="rounded-xl border border-border-token bg-surface p-5"
      >
        <h2 id="consent-heading" className="text-base font-semibold">
          {t("consentTitle")}
        </h2>
        <p className="mt-1 text-sm text-muted">
          {me?.consent_version && me.consented_at
            ? t("consentGiven", {
                version: me.consent_version,
                date: format.dateTime(new Date(me.consented_at), {
                  dateStyle: "medium",
                }),
              })
            : t("consentMissing")}
        </p>
        <p className="mt-2 text-sm">
          <Link href="/privacy" className="text-brand underline-offset-4 hover:underline">
            {t("readNotice")}
          </Link>
        </p>
      </section>

      <section
        aria-labelledby="export-heading"
        className="rounded-xl border border-border-token bg-surface p-5"
      >
        <h2 id="export-heading" className="text-base font-semibold">
          {t("exportTitle")}
        </h2>
        <p className="mt-1 text-sm text-muted">{t("exportBody")}</p>
        <Button
          variant="secondary"
          className="mt-4"
          disabled={download.isPending}
          onClick={() => download.mutate()}
        >
          {download.isPending ? t("exporting") : t("exportButton")}
        </Button>
        {download.isError && (
          <p role="alert" className={ALERT}>
            {t("exportError")}
          </p>
        )}
      </section>

      <section
        aria-labelledby="delete-heading"
        className="rounded-xl border border-border-token bg-surface p-5"
      >
        <h2 id="delete-heading" className="text-base font-semibold">
          {t("deleteTitle")}
        </h2>
        <p className="mt-1 text-sm text-muted">{t("deleteBody")}</p>

        {!confirming ? (
          <Button variant="danger" className="mt-4" onClick={() => setConfirming(true)}>
            {t("deleteButton")}
          </Button>
        ) : (
          <div className="mt-4 rounded-lg border border-border-token p-4">
            <h3 className="text-sm font-semibold">{t("confirmTitle")}</h3>
            {preview.isPending ? (
              <p className="mt-2 text-sm text-muted">{t("loadingPreview")}</p>
            ) : preview.isError ? (
              <p role="alert" className={ALERT}>
                {t("deleteError")}
              </p>
            ) : (
              <>
                {blocked.length > 0 ? (
                  <>
                    <p className="mt-2 text-sm">{t("blocked")}</p>
                    <ul className="mt-2 list-disc pl-5 text-sm">
                      {blocked.map((o) => (
                        <li key={o.slug}>{o.name}</li>
                      ))}
                    </ul>
                  </>
                ) : going.length > 0 ? (
                  <>
                    <p className="mt-2 text-sm">{t("orgsGoing")}</p>
                    <ul className="mt-2 list-disc pl-5 text-sm">
                      {going.map((o) => (
                        <li key={o.slug}>
                          {t("orgLine", { name: o.name, listings: o.listings })}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="mt-2 text-sm text-muted">{t("nothingElse")}</p>
                )}
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button
                    variant="danger"
                    disabled={blocked.length > 0 || remove.isPending}
                    onClick={() => remove.mutate()}
                  >
                    {remove.isPending ? t("deleting") : t("confirmButton")}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setConfirming(false);
                      remove.reset();
                    }}
                  >
                    {t("cancel")}
                  </Button>
                </div>
                {remove.isError && (
                  <p role="alert" className={ALERT}>
                    {t("deleteError")}
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
