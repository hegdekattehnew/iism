"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Select, Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Badge, Button, ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { isSignedOut } from "@/lib/http";
import { api } from "@/lib/api";
import { useRouter } from "@/i18n/navigation";

/**
 * Who works here, and who has been asked to.
 *
 * For twenty-four sprints an organisation could hold exactly one person: every
 * `Membership` was written `role="owner"` by one of three call sites, and no
 * endpoint touched the table at all. This screen is what makes `admin` and
 * `member` real, and it is what makes the account-deletion guard in `privacy/`
 * reachable -- until now a sole owner deleting their account destroyed the
 * organisation and every application to it, silently.
 *
 * **Controls follow the permission, not the screen.** Every member may read
 * the list (`MEMBER_READ`); inviting needs `MEMBER_INVITE`, and changing a
 * role or removing somebody needs `MEMBER_MANAGE`, which only an owner holds.
 * A `member` therefore sees colleagues and no buttons -- rather than buttons
 * that 403, which is the Sprint 14 defect.
 */


type Role = "owner" | "admin" | "member";

export function TeamPanel({ org }: { org: string }) {
  const t = useTranslations("team");
  const format = useFormatter();
  const qc = useQueryClient();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"admin" | "member">("member");
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const membersKey = ["org", org, "members"];
  const invitesKey = ["org", org, "invitations"];

  const members = useQuery({
    queryKey: membersKey,
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}/members", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error("members failed");
      return data;
    },
  });

  // The invitation list needs MEMBER_INVITE, which a plain member does not
  // hold. Asking for it anyway would put a 403 in the console on a screen that
  // is otherwise working, so it waits until the member list says who we are.
  const me = members.data?.find((m) => m.is_you);
  const canInvite = me?.role === "owner" || me?.role === "admin";
  const canManage = me?.role === "owner";

  const invitations = useQuery({
    queryKey: invitesKey,
    enabled: canInvite,
    queryFn: async () => {
      const { data, error } = await api.GET("/org/{org_slug}/invitations", {
        params: { path: { org_slug: org } },
      });
      if (error || !data) throw new Error("invitations failed");
      return data;
    },
  });

  const invite = useMutation({
    mutationFn: async () => {
      setError(null);
      setSentTo(null);
      const { data, error: err, response } = await api.POST("/org/{org_slug}/invitations", {
        params: { path: { org_slug: org } },
        body: { email: email.trim().toLowerCase(), role },
      });
      if (err || !data) throw new Error(String(response.status));
      return data;
    },
    onSuccess: async (created) => {
      setSentTo(created.email);
      setEmail("");
      await qc.invalidateQueries({ queryKey: invitesKey });
    },
    // Every mutation that can 403 needs an onError: a button that silently
    // does nothing is worse than an error (Sprint 14).
    onError: (e: Error) => {
      const status = Number(e.message);
      setError(
        status === 409
          ? t("errorDuplicate")
          : status === 429
            ? t("errorCap")
            : status === 403
              ? t("errorEscalate")
              : t("errorGeneric"),
      );
    },
  });

  const revoke = useMutation({
    mutationFn: async (id: string) => {
      setError(null);
      const { error: err, response } = await api.DELETE(
        "/org/{org_slug}/invitations/{invitation_id}",
        { params: { path: { org_slug: org, invitation_id: id } } },
      );
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: invitesKey });
    },
    onError: () => setError(t("errorGeneric")),
  });

  const changeRole = useMutation({
    mutationFn: async ({ userId, next }: { userId: string; next: Role }) => {
      setError(null);
      const { error: err, response } = await api.PATCH("/org/{org_slug}/members/{user_id}", {
        params: { path: { org_slug: org, user_id: userId } },
        body: { role: next },
      });
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: membersKey });
    },
    // 409 is the last-owner rule, and it is the one error here worth naming
    // exactly: "something went wrong" would leave somebody trying again.
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("errorLastOwner") : t("errorGeneric")),
  });

  const remove = useMutation({
    mutationFn: async (userId: string) => {
      setError(null);
      const { error: err, response } = await api.DELETE("/org/{org_slug}/members/{user_id}", {
        params: { path: { org_slug: org, user_id: userId } },
      });
      if (err) throw new Error(String(response.status));
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: membersKey });
    },
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("errorLastOwner") : t("errorGeneric")),
  });

  const leave = useMutation({
    mutationFn: async () => {
      setError(null);
      const { error: err, response } = await api.POST("/org/{org_slug}/leave", {
        params: { path: { org_slug: org } },
      });
      if (err) throw new Error(String(response.status));
    },
    // Straight out of the organisation they just left: staying on this page
    // would render a 404 where the member list was.
    onSuccess: () => router.push("/"),
    onError: (e: Error) =>
      setError(Number(e.message) === 409 ? t("errorLastOwner") : t("errorGeneric")),
  });

  if (members.isPending) return <Skeleton className="mt-8 h-40 w-full" />;
  if (isSignedOut(members.error)) return <SessionExpired variant="inline" />;
  if (members.isError) return <p className="mt-8 text-sm text-muted">{t("errorGeneric")}</p>;

  const roleLabel = (r: string) =>
    r === "owner" ? t("roleOwner") : r === "admin" ? t("roleAdmin") : t("roleMember");

  // Both `full_name` and `email` are nullable -- an account created by phone
  // has no address and may never have typed a name -- so the fallback is not
  // defensive, it is the ordinary case for a candidate who joined an
  // organisation. next-intl also refuses a null interpolation value.
  const nameOf = (m: { full_name?: string | null; email?: string | null }) =>
    m.full_name || m.email || t("roleMember");

  return (
    <div className="mt-8">
      <ButtonLink href={`/employer/${org}`} variant="ghost" size="sm" className="-ml-3">
        ← {t("backToConsole")}
      </ButtonLink>

      <h2 className="mt-6 text-lg font-semibold">{t("membersHeading")}</h2>
      <ul className="mt-3 space-y-3">
        {members.data.map((member) => (
          <li key={member.user_id}>
            <Card>
              <CardBody>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-base font-semibold">
                      {nameOf(member)}
                      {member.is_you && (
                        <span className="ml-2 text-sm font-normal text-muted">({t("you")})</span>
                      )}
                    </p>
                    {member.email && member.full_name && (
                      <p className="text-sm text-muted">{member.email}</p>
                    )}
                    <p className="mt-0.5 text-xs text-muted">
                      {t("joined", {
                        date: format.dateTime(new Date(member.since), { dateStyle: "medium" }),
                      })}
                    </p>
                  </div>
                  <Badge tone={member.role === "owner" ? "good" : undefined}>
                    {roleLabel(member.role)}
                  </Badge>
                </div>

                {canManage && !member.is_you && (
                  <div className="mt-4 flex flex-wrap items-end gap-3">
                    <label className="text-sm">
                      <span className="font-medium">{t("changeRole")}</span>
                      <Select
                        value={member.role}
                        disabled={changeRole.isPending}
                        onChange={(e) =>
                          changeRole.mutate({
                            userId: member.user_id,
                            next: e.target.value as Role,
                          })
                        }
                      >
                        <option value="owner">{t("roleOwner")}</option>
                        <option value="admin">{t("roleAdmin")}</option>
                        <option value="member">{t("roleMember")}</option>
                      </Select>
                    </label>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={remove.isPending}
                      onClick={() => {
                        if (confirm(t("confirmRemove", { name: nameOf(member) })))
                          remove.mutate(member.user_id);
                      }}
                    >
                      {remove.isPending ? t("removing") : t("remove")}
                    </Button>
                  </div>
                )}

                {member.is_you && (
                  <div className="mt-4">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={leave.isPending}
                      onClick={() => {
                        if (confirm(t("confirmLeave", { organisation: org })))
                          leave.mutate();
                      }}
                    >
                      {leave.isPending ? t("leaving") : t("leave")}
                    </Button>
                  </div>
                )}
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>

      {!canManage && <p className="mt-3 text-sm text-muted">{t("onlyOwnerNote")}</p>}

      {canInvite && (
        <>
          <h2 className="mt-10 text-lg font-semibold">{t("inviteHeading")}</h2>
          <p className="mt-1 text-sm text-muted">{t("inviteIntro")}</p>
          <form
            className="mt-4 flex flex-wrap items-end gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              invite.mutate();
            }}
          >
            <label className="min-w-0 flex-1 text-sm">
              <span className="font-medium">{t("emailLabel")}</span>
              <Text
                type="email"
                required
                value={email}
                placeholder={t("emailPlaceholder")}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="text-sm">
              <span className="font-medium">{t("roleLabel")}</span>
              <Select value={role} onChange={(e) => setRole(e.target.value as "admin" | "member")}>
                <option value="member">{t("roleMember")}</option>
                {/* An admin may invite a `member` only; the server enforces it,
                    and offering the option anyway would be a button that 403s. */}
                {canManage && <option value="admin">{t("roleAdmin")}</option>}
              </Select>
            </label>
            <Button type="submit" disabled={invite.isPending}>
              {invite.isPending ? t("sending") : t("sendInvite")}
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted">
            {role === "admin" ? t("roleHintAdmin") : t("roleHintMember")}
          </p>
          {sentTo && (
            <p className="mt-3 text-sm text-success-text">
              {t("sent", { email: sentTo })}
            </p>
          )}

          <h2 className="mt-10 text-lg font-semibold">{t("pendingHeading")}</h2>
          {invitations.isPending ? (
            <Skeleton className="mt-3 h-20 w-full" />
          ) : !invitations.data?.length ? (
            <p className="mt-3 text-sm text-muted">{t("pendingEmpty")}</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {invitations.data.map((invitation) => (
                <li key={invitation.id}>
                  <Card>
                    <CardBody>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold break-words">{invitation.email}</p>
                          <p className="text-xs text-muted">
                            {roleLabel(invitation.role)}
                            {invitation.invited_by &&
                              ` · ${t("invitedBy", { name: invitation.invited_by })}`}
                          </p>
                          {invitation.state === "pending" && (
                            <p className="mt-0.5 text-xs text-muted">
                              {t("expires", {
                                date: format.dateTime(new Date(invitation.expires_at), {
                                  dateStyle: "medium",
                                }),
                              })}
                            </p>
                          )}
                        </div>
                        <Badge tone={invitation.state === "pending" ? "good" : undefined}>
                          {t(
                            invitation.state === "pending"
                              ? "statePending"
                              : invitation.state === "accepted"
                                ? "stateAccepted"
                                : invitation.state === "revoked"
                                  ? "stateRevoked"
                                  : "stateExpired",
                          )}
                        </Badge>
                      </div>
                      {invitation.state === "pending" && (
                        <div className="mt-3">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={revoke.isPending}
                            onClick={() => revoke.mutate(invitation.id)}
                          >
                            {revoke.isPending ? t("revoking") : t("revoke")}
                          </Button>
                        </div>
                      )}
                    </CardBody>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {error && (
        <Alert className="mt-3">
          {error}
        </Alert>
      )}
    </div>
  );
}
