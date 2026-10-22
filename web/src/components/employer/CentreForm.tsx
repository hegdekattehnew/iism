"use client";

import { useTranslations } from "next-intl";

import { Area, Field, FormErrors, Text } from "@/components/profile/fields";
import { Alert, Button } from "@/components/ui";
import type { Centre } from "@/lib/centres";
import { detailOf, fieldsOf } from "@/lib/http";

/** One form for adding and for changing: the same four fields, the same limits as `CentreIn`. */
export function CentreForm({
  centre,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  centre?: Centre;
  pending: boolean;
  error: unknown;
  onSubmit: (body: {
    name: string;
    address: string | null;
    state: string;
    district: string;
  }) => void;
  onCancel?: () => void;
}) {
  const t = useTranslations("centres");
  return (
    <FormErrors fields={fieldsOf(error)}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const s = (k: string) => String(f.get(k) ?? "").trim();
          onSubmit({
            name: s("name"),
            address: s("address") || null,
            state: s("state"),
            district: s("district"),
          });
        }}
      >
        <Field label={t("name")} hint={t("nameHint")} className="sm:col-span-2">
          <Text name="name" minLength={2} maxLength={120} required defaultValue={centre?.name ?? ""} />
        </Field>
        <Field label={t("address")} hint={t("addressHint")} className="sm:col-span-2">
          <Area name="address" rows={2} maxLength={500} defaultValue={centre?.address ?? ""} />
        </Field>
        <Field label={t("state")}>
          <Text
            name="state"
            minLength={2}
            maxLength={120}
            required
            defaultValue={centre?.location_state ?? ""}
          />
        </Field>
        <Field label={t("district")}>
          <Text
            name="district"
            minLength={2}
            maxLength={120}
            required
            defaultValue={centre?.location_district ?? ""}
          />
        </Field>
        {centre?.is_verified && (
          <Alert tone="warning" role={undefined} className="sm:col-span-2">
            {t("checkedWarning")}
          </Alert>
        )}
        {error != null && Object.keys(fieldsOf(error) ?? {}).length === 0 && (
          <Alert role="alert" className="sm:col-span-2">
            {detailOf(error) ?? t("failed")}
          </Alert>
        )}
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="submit" disabled={pending}>
            {centre ? t("saveChanges") : t("create")}
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              {t("cancel")}
            </Button>
          )}
        </div>
      </form>
    </FormErrors>
  );
}
