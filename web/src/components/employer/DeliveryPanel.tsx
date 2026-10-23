"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useDeferredValue, useState } from "react";

import { DELIVERY_LOOK } from "@/components/cards/delivery-look";
import { Field, Select, Text } from "@/components/profile/fields";
import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Button, Card, CardBody, Skeleton } from "@/components/ui";
import { BuildingIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";
import {
  useDelivery,
  useDeliveryMutations,
  useOrganisationSearch,
  useSellerCourses,
  type Arrangement,
  type OrgRef,
} from "@/lib/delivery";
import { detailOf, isSignedOut } from "@/lib/http";
import { Link } from "@/i18n/navigation";
import { useOrgDelivers, useOrgSells } from "@/lib/org";

/**
 * One arrangement, from the side of the organisation looking at it (Sprint 97, ADR-102). What the
 * viewer may do is read off the state and the side, never a flag: the seller approves or declines a
 * request, the partner withdraws its own, and either ends an approved one. The server refuses
 * anything else.
 */
function ArrangementCard({ org, row }: { org: string; row: Arrangement }) {
  const t = useTranslations("delivery");
  const format = useFormatter();
  const { act } = useDeliveryMutations(org);
  const look = DELIVERY_LOOK[row.state];
  const name = row.other.name;
  const when = row.ended_at ?? row.approved_at ?? row.requested_at;

  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="min-w-0 grow basis-48 text-base font-semibold">
            <Link href={`/providers/${row.other.slug}`} className="underline-offset-4 hover:underline">
              {name}
            </Link>
          </h3>
          <StatusChip tone={look.tone} icon={look.icon}>
            {t(`state.${row.state}`)}
          </StatusChip>
        </div>
        <p className="mt-1 text-sm">
          {row.course ? t("oneCourse", { title: row.course.title }) : t("everyCourse")}
        </p>
        <p className="mt-1 text-sm text-muted">
          {t(`story.${row.state}.${row.side}`, { organisation: name })}
          {" · "}
          {format.dateTime(new Date(when), { dateStyle: "medium" })}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {row.state === "requested" && row.side === "provider" && (
            <>
              <Button
                size="sm"
                disabled={act.isPending}
                aria-label={t("approveNamed", { name })}
                onClick={() => act.mutate({ id: row.id, verb: "approve" })}
              >
                {t("approve")}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={act.isPending}
                aria-label={t("declineNamed", { name })}
                onClick={() => act.mutate({ id: row.id, verb: "decline" })}
              >
                {t("decline")}
              </Button>
            </>
          )}
          {row.state === "requested" && row.side === "partner" && (
            <Button
              size="sm"
              variant="ghost"
              disabled={act.isPending}
              aria-label={t("withdrawNamed", { name })}
              onClick={() => act.mutate({ id: row.id, verb: "decline" })}
            >
              {t("withdraw")}
            </Button>
          )}
          {row.state === "approved" && (
            <Button
              size="sm"
              variant="secondary"
              disabled={act.isPending}
              aria-label={t("endNamed", { name })}
              onClick={() => act.mutate({ id: row.id, verb: "revoke" })}
            >
              {t("end")}
            </Button>
          )}
        </div>
        {act.error != null && (
          <Alert role="alert" className="mt-3">
            {detailOf(act.error) ?? t("failed")}
          </Alert>
        )}
      </CardBody>
    </Card>
  );
}

/**
 * Find the organisation, choose what it covers, send it. `ask` is a delivering organisation asking a
 * seller; `invite` is a seller authorising a deliverer (the courses on offer are then its own).
 */
function ScopeForm({ org, mode }: { org: string; mode: "ask" | "invite" }) {
  const t = useTranslations("delivery");
  const { ask, invite } = useDeliveryMutations(org);
  const [q, setQ] = useState("");
  const deferred = useDeferredValue(q);
  const [picked, setPicked] = useState<OrgRef | null>(null);
  const [scope, setScope] = useState("");
  const [sent, setSent] = useState(false);
  const send = mode === "ask" ? ask : invite;
  // Named for each mutation, so a failure of either reaches the screen.
  const failure = mode === "ask" ? ask.error : invite.error;

  const search = useOrganisationSearch(
    deferred,
    mode === "ask" ? "sells" : "delivers",
    picked === null && deferred.trim().length >= 2,
  );
  const sellerSlug = mode === "ask" ? (picked?.slug ?? null) : org;
  const courses = useSellerCourses(picked === null ? null : sellerSlug);
  const results = (search.data?.items ?? []).filter((o) => o.slug !== org);

  const submit = () => {
    if (!picked) return;
    setSent(false);
    const course = scope === "" ? null : scope;
    const done = { onSuccess: () => {
      setSent(true);
      setPicked(null);
      setQ("");
      setScope("");
    } };
    if (mode === "ask") ask.mutate({ provider: picked.slug, course }, done);
    else invite.mutate({ partner: picked.slug, course }, done);
  };

  return (
    <div className="mt-4 space-y-3 rounded-xl border border-border-token p-4">
      <h3 className="text-sm font-semibold">{t(mode === "ask" ? "askTitle" : "inviteTitle")}</h3>
      {picked === null ? (
        <>
          <Field label={t(mode === "ask" ? "findSeller" : "findPartner")} hint={t("findHint")}>
            <Text
              name="organisation"
              type="search"
              value={q}
              onChange={(e) => {
                setSent(false);
                setQ(e.target.value);
              }}
            />
          </Field>
          {search.isFetching && <Skeleton className="h-10 w-full" />}
          {deferred.trim().length >= 2 && !search.isFetching && results.length === 0 && (
            <p className="text-sm text-muted">{t("noMatch")}</p>
          )}
          <ul className="space-y-1">
            {results.map((o) => (
              <li key={o.slug}>
                <Button
                  variant="ghost"
                  className="h-auto w-full justify-start py-2 text-left"
                  onClick={() => setPicked(o)}
                >
                  <BuildingIcon className="h-4 w-4 shrink-0" />
                  <span className="min-w-0">
                    <span className="block">{o.name}</span>
                    {o.city && <span className="block text-xs font-normal text-muted">{o.city}</span>}
                  </span>
                </Button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <BuildingIcon className="h-4 w-4 shrink-0" />
            <span className="font-medium">{picked.name}</span>
            <Button size="sm" variant="ghost" onClick={() => setPicked(null)}>
              {t("change")}
            </Button>
          </p>
          <Field label={t("scope")} hint={t(mode === "ask" ? "scopeAskHint" : "scopeInviteHint")}>
            <Select name="scope" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="">{t("allCourses")}</option>
              {(courses.data ?? []).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.title}
                </option>
              ))}
            </Select>
          </Field>
          <Button disabled={send.isPending} onClick={submit}>
            {t(mode === "ask" ? "sendRequest" : "sendInvite")}
          </Button>
        </>
      )}
      {failure != null && <Alert role="alert">{detailOf(failure) ?? t("failed")}</Alert>}
      {sent && (
        <Alert tone="success" role="status">
          {t(mode === "ask" ? "requestSent" : "inviteSent")}
        </Alert>
      )}
    </div>
  );
}

function Section({
  org,
  mode,
  rows,
}: {
  org: string;
  mode: "ask" | "invite";
  rows: Arrangement[];
}) {
  const t = useTranslations("delivery");
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{t(mode === "ask" ? "asPartnerTitle" : "asProviderTitle")}</h2>
      <p className="text-sm text-muted">{t(mode === "ask" ? "asPartnerIntro" : "asProviderIntro")}</p>
      <ScopeForm org={org} mode={mode} />
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{t(mode === "ask" ? "nonePartner" : "noneProvider")}</p>
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id}>
              <ArrangementCard org={org} row={row} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * Who delivers whose courses (Sprint 97, ADR-102): the seller's side and the partner's side of an
 * organisation, each shown only if the organisation does that thing (it may do both).
 */
export function DeliveryPanel({ org }: { org: string }) {
  const t = useTranslations("delivery");
  const sells = useOrgSells(org);
  const delivers = useOrgDelivers(org);
  const list = useDelivery(org);

  if (list.isPending) return <Skeleton className="mt-8 h-64 w-full rounded-xl" />;
  if (isSignedOut(list.error)) return <SessionExpired />;
  if (list.isError) {
    return (
      <Card className="mt-8">
        <CardBody>
          <p className="text-sm text-muted">{t("noAccess")}</p>
        </CardBody>
      </Card>
    );
  }
  return (
    <div className="mt-8 space-y-10">
      {delivers && <Section org={org} mode="ask" rows={list.data.as_partner ?? []} />}
      {sells && <Section org={org} mode="invite" rows={list.data.as_provider ?? []} />}
    </div>
  );
}
