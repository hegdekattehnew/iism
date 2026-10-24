"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { BatchOverviewPanel } from "@/components/employer/BatchOverviewPanel";
import { CentreForm } from "@/components/employer/CentreForm";
import { CENTRE_STATE_LOOK } from "@/components/cards/centre-look";
import { SessionExpired } from "@/components/SessionExpired";
import { Button, Card, CardBody, Skeleton } from "@/components/ui";
import { BuildingIcon, CheckCircleIcon, ClockIcon, MapPinIcon, UserIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { useCentreColleagues, useMyCentre, useUpdateMyCentre } from "@/lib/centres";
import { isSignedOut } from "@/lib/http";

/**
 * A centre, as the person who runs it sees it (Sprint 96, ADR-102): what it is, whose it is, whether
 * its address has been checked, and a way to keep it true. Nothing of the organisation is here
 * beyond its name; closing the centre and who else runs it are the organisation's. **It leads with
 * work** (Sprint 99): the figures for the centre's batches and the next to start, then the centre.
 * Its batches are on `/batches`; the learners of a batch arrive with registration (Sprint 100).
 */
export function CentreWorkspace({ slug }: { slug: string }) {
  const t = useTranslations("centreWorkspace");
  const tc = useTranslations("centres");
  const centre = useMyCentre(slug);
  const colleagues = useCentreColleagues(slug);
  const update = useUpdateMyCentre(slug);
  const [editing, setEditing] = useState(false);

  if (centre.isPending) return <Skeleton className="h-64 w-full rounded-xl" />;
  if (isSignedOut(centre.error)) return <SessionExpired />;
  if (centre.isError) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{t("noAccess")}</p>
        </CardBody>
      </Card>
    );
  }

  const c = centre.data;
  const look = CENTRE_STATE_LOOK[c.status];
  const closed = c.status === "closed";
  const place = [c.location_district, c.location_state].filter(Boolean).join(", ");

  return (
    <div className="space-y-6">
      <BatchOverviewPanel org={slug} showNext />
      <Card>
        <CardBody>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h2 className="min-w-0 grow basis-48 text-xl font-semibold">{c.name}</h2>
            <div className="flex flex-wrap gap-2">
              <StatusChip tone={look.tone} icon={look.icon}>
                {tc(`status.${c.status}`)}
              </StatusChip>
              <StatusChip
                tone={c.is_verified ? "good" : "neutral"}
                icon={c.is_verified ? CheckCircleIcon : ClockIcon}
              >
                {c.is_verified ? tc("checked") : tc("notChecked")}
              </StatusChip>
            </div>
          </div>
          <p className="mt-2 flex items-start gap-1.5 text-sm text-muted">
            <BuildingIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("centreOf", { organisation: c.organisation })}</span>
          </p>
          <p className="mt-1 flex items-start gap-1.5 text-sm text-muted">
            <MapPinIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{[c.address, place].filter(Boolean).join(" · ") || tc("noPlace")}</span>
          </p>
          {!c.place_resolved && <p className="mt-2 text-sm text-muted">{tc("placeNotFound")}</p>}
          {closed && <p className="mt-2 text-sm text-muted">{t("closedNote")}</p>}

          {editing ? (
            <div className="mt-4">
              <CentreForm
                centre={c}
                pending={update.isPending}
                error={update.error}
                onCancel={() => {
                  update.reset();
                  setEditing(false);
                }}
                onSubmit={(body) => update.mutate(body, { onSuccess: () => setEditing(false) })}
              />
            </div>
          ) : (
            !closed && (
              <div className="mt-4">
                <Button variant="secondary" onClick={() => setEditing(true)}>
                  {t("edit")}
                </Button>
              </div>
            )
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <h2 className="text-base font-semibold">{t("whoRunsIt")}</h2>
          {colleagues.isPending ? (
            <Skeleton className="mt-3 h-12 w-full" />
          ) : colleagues.isError ? (
            <p className="mt-2 text-sm text-muted">{t("colleaguesFailed")}</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {colleagues.data.map((m) => (
                <li key={m.user_id} className="flex items-start gap-2 text-sm">
                  <UserIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                  <span className="min-w-0">
                    <span className="block font-medium">
                      {m.full_name ?? m.email}
                      {m.is_you && <span className="font-normal text-muted"> · {t("you")}</span>}
                    </span>
                    {m.full_name && <span className="block break-all text-muted">{m.email}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-muted">{t("whoRunsItNote")}</p>
        </CardBody>
      </Card>
    </div>
  );
}
