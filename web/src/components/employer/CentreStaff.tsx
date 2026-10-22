"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Field, Text } from "@/components/profile/fields";
import { Alert, Button, Skeleton } from "@/components/ui";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  UserIcon,
  XCircleIcon,
} from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import { useCentreStaff, useCentreStaffMutations, type StaffInvitation } from "@/lib/centre-staff";
import { detailOf } from "@/lib/http";

/**
 * An invitation's state, a word with a shape and a tone (Sprint 96). Typed over the server's own
 * union, so a new state is a compile error and not a chip with no shape; four states, four shapes.
 */
export const INVITE_LOOK: Record<
  StaffInvitation["state"],
  { tone: "info" | "good" | "neutral" | "warn"; icon: typeof ClockIcon }
> = {
  pending: { tone: "info", icon: ClockIcon },
  accepted: { tone: "good", icon: CheckCircleIcon },
  revoked: { tone: "neutral", icon: XCircleIcon },
  expired: { tone: "warn", icon: AlertTriangleIcon },
};

/**
 * Who runs one centre, from the organisation's side (Sprint 96, ADR-102): the managers, the
 * invitations, and a way to ask someone. Only an admin or an owner of the organisation sees this;
 * the centre's own manager sees the read-only list on their own page.
 */
export function CentreStaff({
  org,
  centre,
  closed,
}: {
  org: string;
  centre: string;
  closed: boolean;
}) {
  const t = useTranslations("centreStaff");
  const format = useFormatter();
  const staff = useCentreStaff(org, centre);
  const { invite, revoke, remove } = useCentreStaffMutations(org, centre);
  const [email, setEmail] = useState("");

  if (staff.isPending) return <Skeleton className="h-24 w-full rounded-xl" />;
  if (staff.isError) return <p className="text-sm text-muted">{t("loadFailed")}</p>;

  const failure = invite.error ?? revoke.error ?? remove.error;
  return (
    <div className="space-y-4">
      {failure != null && <Alert role="alert">{detailOf(failure) ?? t("failed")}</Alert>}

      {staff.data.managers.length === 0 ? (
        <p className="text-sm text-muted">{t("none")}</p>
      ) : (
        <ul className="space-y-2">
          {staff.data.managers.map((m) => (
            <li key={m.user_id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex min-w-0 grow basis-48 items-start gap-2 text-sm">
                <UserIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
                <span className="min-w-0">
                  <span className="block font-medium">{m.full_name ?? m.email}</span>
                  {m.full_name && <span className="block text-muted">{m.email}</span>}
                </span>
              </span>
              <Button
                size="sm"
                variant="ghost"
                disabled={remove.isPending}
                aria-label={t("removeNamed", { name: m.full_name ?? m.email ?? "" })}
                onClick={() => remove.mutate(m.user_id)}
              >
                {t("remove")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      {closed ? (
        <p className="text-sm text-muted">{t("closed")}</p>
      ) : (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            invite.mutate(email, { onSuccess: () => setEmail("") });
          }}
        >
          <Field label={t("emailLabel")} hint={t("emailHint")} className="grow basis-56">
            <Text
              name="email"
              type="email"
              required
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Button type="submit" disabled={invite.isPending || email.trim() === ""}>
            {t("invite")}
          </Button>
        </form>
      )}

      {staff.data.invitations.length > 0 && (
        <ul className="space-y-2 border-t border-border-token pt-3">
          {staff.data.invitations.map((i) => {
            const look = INVITE_LOOK[i.state];
            return (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="min-w-0 grow basis-48">
                  <span className="block break-all">{i.email}</span>
                  <span className="block text-muted">
                    {format.dateTime(new Date(i.created_at), { dateStyle: "medium" })}
                  </span>
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <StatusChip tone={look.tone} icon={look.icon}>
                    {t(`state.${i.state}`)}
                  </StatusChip>
                  {i.state === "pending" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={revoke.isPending}
                      aria-label={t("withdrawNamed", { email: i.email })}
                      onClick={() => revoke.mutate(i.id)}
                    >
                      {t("withdraw")}
                    </Button>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
