"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import { Badge, Button, Card, CardBody, Skeleton } from "@/components/ui";
import { ApiError, detailOf, isSignedOut, readDetail } from "@/lib/http";
import { api } from "@/lib/api";

/**
 * What a candidate sees about this employer, edited by the employer.
 *
 * Owner only — `ORG_UPDATE` sits in the owner's permission set alone, and the
 * API is the authority on that; an admin simply gets a 403 here.
 *
 * The verification badge is read-only and says so. It is set by an operator,
 * because a self-asserted badge is worse than none: a candidate reads it as
 * ours.
 */
export function OrgSettings({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("orgSettings");
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);

  const org = useQuery({
    queryKey: ["org", orgSlug],
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}", {
        params: { path: { org_slug: orgSlug } },
      });
      if (error || !data) throw new Error("could not load the organisation");
      return data;
    },
    retry: false,
  });

  const save = useMutation({
    mutationFn: async (body: {
      name: string;
      city: string | null;
      description: string | null;
      website: string | null;
      logo_url: string | null;
      contact_email: string | null;
    }) => {
      const { data, error, response } = await api.PUT("/org/{org_slug}", {
        params: { path: { org_slug: orgSlug } },
        body,
      });
      if (error || !data) throw new ApiError(response.status, readDetail(error));
      return data;
    },
    onSuccess: async (data) => {
      qc.setQueryData(["org", orgSlug], data);
      // The switcher labels contexts by name, so a rename must reach it.
      await qc.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
    },
  });

  if (org.isPending) return <Skeleton className="h-96 w-full rounded-xl" />;
  // 401 is not "no access" -- it is "your session ran out", and saying the
  // former sends an owner looking for a permission they never lost.
  if (isSignedOut(org.error)) return <SessionExpired />;
  if (org.isError) return <p className="text-sm text-muted">{t("noAccess")}</p>;

  const d = org.data;

  return (
    <Card>
      <CardBody>
        <form
          key={d?.slug}
          onSubmit={(e) => {
            e.preventDefault();
            setSaved(false);
            const f = new FormData(e.currentTarget);
            const s = (k: string) =>
              (String(f.get(k) ?? "").trim() || null) as string | null;
            save.mutate({
              name: String(f.get("name") ?? "").trim(),
              city: s("city"),
              description: s("description"),
              website: s("website"),
              logo_url: s("logo_url"),
              contact_email: s("contact_email"),
            });
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-base font-semibold">{t("title")}</h2>
            {d?.is_verified ? (
              <Badge tone="good">{t("verified")}</Badge>
            ) : (
              <Badge>{t("unverified")}</Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <Field label={t("name")} className="sm:col-span-2">
              <Text
                name="name"
                maxLength={120}
                required
                minLength={2}
                defaultValue={d?.name ?? ""}
              />
            </Field>
            <Field
              label={t("description")}
              className="sm:col-span-2"
              hint={t("descriptionHint")}
            >
              <Area
                name="description"
                rows={4}
                defaultValue={d?.description ?? ""}
              />
            </Field>
            <Field label={t("city")}>
              <Text name="city" defaultValue={d?.city ?? ""} />
            </Field>
            <Field label={t("website")}>
              <Text name="website"
                maxLength={500} type="url" defaultValue={d?.website ?? ""} />
            </Field>
            <Field label={t("logoUrl")}>
              <Text
                name="logo_url"
                type="url"
                defaultValue={d?.logo_url ?? ""}
              />
            </Field>
            <Field label={t("contactEmail")} hint={t("contactEmailHint")}>
              <Text
                name="contact_email"
                type="email"
                defaultValue={d?.contact_email ?? ""}
              />
            </Field>
          </div>

          <p className="mt-6 rounded-lg border border-border-token bg-surface-muted px-3 py-2 text-xs text-muted">
            {t("slugNote", { slug: d?.slug ?? "" })}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? t("saving") : t("save")}
            </Button>
            {saved && <span className="text-sm text-brand">{t("saved")}</span>}
            {save.isError && (
              <span className="text-sm text-danger-text">
                {/* What the server said -- "Website: URL should have a scheme"
                    beats "Only an owner can edit the organisation" when the
                    caller *is* the owner and the URL is simply malformed. */}
                {detailOf(save.error) ?? t("saveError")}
              </span>
            )}
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
