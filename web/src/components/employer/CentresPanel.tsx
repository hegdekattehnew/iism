"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Area, Field, FormErrors, Text } from "@/components/profile/fields";
import { RowActions } from "@/components/RowActions";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { EmptyState } from "@/components/ui/empty-state";
import { CheckCircleIcon, ClockIcon, MapPinIcon, XCircleIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { useCentreMutations, useCentres, type Centre } from "@/lib/centres";
import { detailOf, fieldsOf, isSignedOut } from "@/lib/http";

/**
 * A centre's state and its address mark, as shapes (Sprint 95, ADR-102). Two different claims, each a
 * word, a shape and a tone: **open or closed** is the organisation's own doing; **address checked** is
 * an operator's, and is never the organisation's mark (a verified organisation does not make a centre
 * checked). Typed over the server's union, so a new status is a compile error.
 */
export const CENTRE_STATE_LOOK: Record<
  Centre["status"],
  { tone: "good" | "neutral"; icon: typeof CheckCircleIcon }
> = {
  active: { tone: "good", icon: CheckCircleIcon },
  closed: { tone: "neutral", icon: XCircleIcon },
};

/** One form for adding and for changing: the same four fields, the same limits as `CentreIn`. */
function CentreForm({
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

function CentreCard({ org, centre }: { org: string; centre: Centre }) {
  const t = useTranslations("centres");
  const { update, close, reopen } = useCentreMutations(org);
  const [editing, setEditing] = useState(false);
  const look = CENTRE_STATE_LOOK[centre.status];
  const closed = centre.status === "closed";
  const place = [centre.location_district, centre.location_state].filter(Boolean).join(", ");

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="min-w-0 grow basis-48 text-base font-semibold">{centre.name}</h3>
          <div className="flex flex-wrap gap-2">
            <StatusChip tone={look.tone} icon={look.icon}>
              {t(`status.${centre.status}`)}
            </StatusChip>
            <StatusChip
              tone={centre.is_verified ? "good" : "neutral"}
              icon={centre.is_verified ? CheckCircleIcon : ClockIcon}
            >
              {centre.is_verified ? t("checked") : t("notChecked")}
            </StatusChip>
          </div>
        </div>
        <p className="mt-2 flex items-start gap-1.5 text-sm text-muted">
          <MapPinIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {[centre.address, place].filter(Boolean).join(" · ") || t("noPlace")}
          </span>
        </p>
        {!centre.place_resolved && (
          <p className="mt-2 text-sm text-muted">{t("placeNotFound")}</p>
        )}
        {closed && <p className="mt-2 text-sm text-muted">{t("closedNote")}</p>}

        {editing ? (
          <div className="mt-4">
            <CentreForm
              centre={centre}
              pending={update.isPending}
              error={update.error}
              onCancel={() => {
                update.reset();
                setEditing(false);
              }}
              onSubmit={(body) =>
                update.mutate({ slug: centre.slug, body }, { onSuccess: () => setEditing(false) })
              }
            />
          </div>
        ) : (
          <RowActions
            moreLabel={t("more")}
            primary={
              <Button
                size="sm"
                variant="secondary"
                aria-label={t("editNamed", { name: centre.name })}
                onClick={() => setEditing(true)}
              >
                {t("edit")}
              </Button>
            }
            secondary={
              closed ? (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={reopen.isPending}
                  aria-label={t("reopenNamed", { name: centre.name })}
                  onClick={() => reopen.mutate(centre.slug)}
                >
                  {t("reopen")}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={close.isPending}
                  aria-label={t("closeNamed", { name: centre.name })}
                  onClick={() => close.mutate(centre.slug)}
                >
                  {t("close")}
                </Button>
              )
            }
          />
        )}
        {(close.error ?? reopen.error) != null && (
          <Alert role="alert" className="mt-3">
            {detailOf(close.error ?? reopen.error) ?? t("failed")}
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}

/**
 * An organisation's training centres (Sprint 95, ADR-102): add one, change it, close or reopen it.
 * A centre has no members of its own; whoever manages the organisation manages its centres.
 */
export function CentresPanel({ org }: { org: string }) {
  const t = useTranslations("centres");
  const list = useCentres(org);
  const { create } = useCentreMutations(org);
  const [adding, setAdding] = useState(false);

  if (list.isPending) return <Skeleton className="mt-8 h-64 w-full rounded-xl" />;
  if (isSignedOut(list.error)) return <SessionExpired />;
  if (list.isError) {
    // 403: the organisation does not deliver training (or the role may not see centres).
    return (
      <Card className="mt-8">
        <CardBody>
          <p className="text-sm text-muted">
            {list.error.message === "403" ? t("notDelivering") : t("noAccess")}
          </p>
          {list.error.message === "403" && (
            <ButtonLink href={`/employer/${org}/settings`} variant="secondary" className="mt-4">
              {t("toSettings")}
            </ButtonLink>
          )}
        </CardBody>
      </Card>
    );
  }

  const data = list.data;
  return (
    <div className="mt-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted" role="status">
          {t("count", { active: data.active, total: data.total })}
        </p>
        <div className="flex flex-wrap gap-2">
          <ButtonLink href={`/employer/${org}/centres/upload`} variant="secondary">
            {t("uploadLink")}
          </ButtonLink>
          {!adding && <Button onClick={() => setAdding(true)}>{t("add")}</Button>}
        </div>
      </div>

      {adding && (
        <Card>
          <CardBody>
            <h2 className="mb-4 text-base font-semibold">{t("add")}</h2>
            <CentreForm
              pending={create.isPending}
              error={create.error}
              onCancel={() => {
                create.reset();
                setAdding(false);
              }}
              onSubmit={(body) => create.mutate(body, { onSuccess: () => setAdding(false) })}
            />
          </CardBody>
        </Card>
      )}

      {data.items.length === 0 && !adding ? (
        <EmptyState
          icon={MapPinIcon}
          title={t("empty")}
          action={<Button onClick={() => setAdding(true)}>{t("add")}</Button>}
        >
          {t("emptyHint")}
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {data.items.map((c) => (
            <li key={c.slug}>
              <CentreCard org={org} centre={c} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
