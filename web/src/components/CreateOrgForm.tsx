"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Select, Text } from "@/components/profile/fields";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";

/**
 * Adding an organisation to the account you are already signed in as.
 *
 * This posts `POST /me/organisations`, which is the whole point: it creates a
 * second **membership**, not a second account. The only visible path before
 * this was the "Create an organisation" tab on `/employers/signin`, which posts
 * `/auth/org/register` with an email — and for an address the server has not
 * seen, that creates a brand-new `User`. A phone-signed-in candidate following
 * the one affordance available to them therefore ended up with two separate
 * identities, which is the exact outcome ADR-038 exists to prevent.
 */
export function CreateOrgForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (slug: string) => void;
}) {
  const t = useTranslations("context");
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<"employer" | "course_provider">("employer");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      setError(null);
      const { data, error: err } = await api.POST("/me/organisations", {
        body: { organisation_name: name, tenant_type: type },
      });
      if (err || !data) throw new Error("create failed");
      return data;
    },
    onSuccess: async (tenant) => {
      // The switcher reads memberships from ["me"]; without this the new
      // organisation would not appear until something else refetched.
      await qc.invalidateQueries({ queryKey: ["me"] });
      onCreated(tenant.slug);
    },
    onError: () => setError(t("createError")),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-5"
      role="dialog"
      aria-modal="true"
      aria-label={t("createOrg")}
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-xl border border-border-token bg-surface p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold">{t("createOrg")}</h2>
        <p className="mt-1 text-sm text-muted">{t("createOrgHint")}</p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label={t("orgName")} className="mt-4">
            <Text
              required
              minLength={2}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("orgNamePlaceholder")}
            />
          </Field>
          <Field label={t("orgType")} className="mt-4">
            <Select
              value={type}
              onChange={(e) =>
                setType(e.target.value as "employer" | "course_provider")
              }
            >
              <option value="employer">{t("typeEmployer")}</option>
              <option value="course_provider">{t("typeProvider")}</option>
            </Select>
          </Field>

          {error && (
            <p className="mt-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
              {error}
            </p>
          )}

          <div className="mt-6 flex gap-3">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? t("creating") : t("create")}
            </Button>
            <Button type="button" variant="secondary" onClick={onClose}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
