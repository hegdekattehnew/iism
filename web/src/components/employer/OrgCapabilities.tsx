"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import {
  TrainingCapabilities,
  doesSomething,
  type Capabilities,
} from "@/components/TrainingCapabilities";
import { Button, Card, CardBody } from "@/components/ui";
import { api } from "@/lib/api";
import { apiErrorFrom, detailOf } from "@/lib/http";

/**
 * What this organisation does, changed by its owner (Sprint 94, ADR-102).
 *
 * The same control as sign-up, with its own Save, because turning a capability off is a standing change
 * the server may refuse: an organisation with published courses cannot stop selling them, and one must
 * always do something. The refusal is shown **in the server's words** (409 carries the reason); a
 * generic line would send an owner looking for what to fix. A change reaches the header's switcher
 * (`["me"]`) and the settings form's own query (`["org", slug]`).
 */
export function OrgCapabilities({
  orgSlug,
  sells,
  delivers,
}: {
  orgSlug: string;
  sells: boolean;
  delivers: boolean;
}) {
  const t = useTranslations("capabilities");
  const qc = useQueryClient();
  const [value, setValue] = useState<Capabilities>({ sells, delivers });
  // What the server last said, so "changed" means changed from that and a saved change is not a
  // pending one (the parent used to re-key this to reset it, which also threw "Saved." away).
  const [base, setBase] = useState<Capabilities>({ sells, delivers });
  const [saved, setSaved] = useState(false);

  const save = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await api.PUT("/org/{org_slug}/capabilities", {
        params: { path: { org_slug: orgSlug } },
        body: { sells_courses: value.sells, delivers_training: value.delivers },
      });
      if (error || !data) throw apiErrorFrom(response.status, error);
      return data;
    },
    onSuccess: async (data) => {
      qc.setQueryData(["org", orgSlug], data);
      setBase({ sells: data.publishes_courses ?? false, delivers: data.delivers_training ?? false });
      await qc.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
    },
  });

  const changed = value.sells !== base.sells || value.delivers !== base.delivers;

  return (
    <Card className="mt-6">
      <CardBody>
        <h2 className="text-base font-semibold">{t("settingsTitle")}</h2>
        <p className="mt-1 text-sm text-muted">{t("settingsSubtitle")}</p>
        <form
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault();
            setSaved(false);
            save.mutate();
          }}
        >
          <TrainingCapabilities
            value={value}
            onChange={(next) => {
              setSaved(false);
              setValue(next);
            }}
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={save.isPending || !changed || !doesSomething(value)}>
              {save.isPending ? t("saving") : t("save")}
            </Button>
            {saved && !changed && (
              <span role="status" className="text-sm text-brand">
                {t("saved")}
              </span>
            )}
          </div>
          {save.isError && (
            <p role="alert" className="mt-3 text-sm text-danger-text">
              {detailOf(save.error) ?? t("saveError")}
            </p>
          )}
        </form>
      </CardBody>
    </Card>
  );
}
