"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { experienceLabel, salaryLabel } from "@/components/JobBrowser";
import { lookalikeNames, StandardOrigin } from "@/components/SkillBrowser";
import { Badge, ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import type { paths } from "@/lib/api-schema";

/**
 * What the homepage search answers: jobs first, then roles, then standards.
 *
 * The hero promises "Tell us the job you want", and its search used to land on
 * the standards browser -- someone who typed "General Duty Assistant" got 24
 * technical units, two of them identically named, and no vacancy. The order
 * here is the order a job seeker cares about: work that is open now, the job
 * roles behind it, and the standards for anyone who came for the taxonomy.
 * Each band is a preview; its full page is one link away and keeps the query.
 */

const PREVIEW = 5;

export function SearchResults({ query }: { query: string }) {
  const t = useTranslations("searchPage");
  const tSkills = useTranslations("skillsPage");
  const q = query.trim();

  const jobs = useQuery({
    queryKey: ["search", "jobs", q],
    enabled: q.length > 0,
    queryFn: async () =>
      (await api.GET("/jobs", { params: { query: { q, limit: PREVIEW } } })).data ?? null,
  });
  const roles = useQuery({
    queryKey: ["search", "roles", q],
    enabled: q.length > 0,
    queryFn: async () =>
      (await api.GET("/roles/search", { params: { query: { q, limit: PREVIEW } } })).data ?? [],
  });
  const standards = useQuery({
    queryKey: ["search", "standards", q],
    enabled: q.length > 0,
    queryFn: async () =>
      (await api.GET("/skills/search", { params: { query: { q, limit: 50 } } })).data ?? [],
  });

  if (!q) return <p className="text-sm text-muted">{t("prompt")}</p>;

  const jobRows = jobs.data?.items ?? [];
  const standardRows = standards.data ?? [];
  const shownStandards = standardRows.slice(0, 6);
  const lookalikes = lookalikeNames(shownStandards);
  const encoded = encodeURIComponent(q);

  return (
    <div className="space-y-12">
      <Band
        title={t("jobsHeading")}
        count={jobs.data?.total}
        pending={jobs.isPending}
        empty={t("noJobs")}
        more={
          (jobs.data?.total ?? 0) > jobRows.length
            ? { href: `/jobs?q=${encoded}`, label: t("seeAllJobs", { count: jobs.data?.total ?? 0 }) }
            : null
        }
      >
        {jobRows.length > 0 && (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {jobRows.map((j) => (
              <li key={j.slug}>
                <JobRow job={j} />
              </li>
            ))}
          </ul>
        )}
      </Band>

      <Band
        title={t("rolesHeading")}
        note={t("rolesNote")}
        pending={roles.isPending}
        empty={t("noRoles")}
      >
        {(roles.data ?? []).length > 0 && (
          <ul className="space-y-2">
            {(roles.data ?? []).map((r) => (
              <li key={r.slug}>
                <RoleRow role={r} />
              </li>
            ))}
          </ul>
        )}
      </Band>

      <Band
        title={t("standardsHeading")}
        count={standardRows.length}
        pending={standards.isPending}
        empty={t("noStandards")}
        more={
          standardRows.length > shownStandards.length
            ? { href: `/skills?q=${encoded}`, label: t("seeAllStandards") }
            : null
        }
      >
        {shownStandards.length > 0 && (
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {shownStandards.map((s) => (
              <li key={s.slug}>
                <Link
                  href={`/skills/${s.slug}`}
                  className="block h-full rounded-xl border border-border-token bg-surface p-4 transition-colors hover:border-brand"
                >
                  <p className="text-sm font-semibold">{s.name}</p>
                  {/* The browse page shows level as a chip; here it is one of
                      the few things that differs between same-named twins. */}
                  {s.nsqf_level != null && (
                    <p className="mt-0.5 text-xs text-muted">
                      {tSkills("levelShort", { level: s.nsqf_level })}
                    </p>
                  )}
                  <StandardOrigin
                    row={s}
                    lookalike={lookalikes.has(s.name.trim().toLowerCase())}
                  />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Band>
    </div>
  );
}

function Band({
  title,
  note,
  count,
  pending,
  empty,
  more,
  children,
}: {
  title: string;
  note?: string;
  count?: number;
  pending: boolean;
  empty: string;
  more?: { href: string; label: string } | null;
  children: React.ReactNode;
}) {
  const t = useTranslations("searchPage");
  const hasContent = Boolean(children);
  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {title}
          {count != null && count > 0 && <span className="ml-2">({count})</span>}
        </h2>
        {more && (
          <Link href={more.href} className="text-sm text-brand hover:underline">
            {more.label} →
          </Link>
        )}
      </div>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
      <div className="mt-3">
        {pending ? (
          <p className="text-sm text-muted">{t("loading")}</p>
        ) : hasContent ? (
          children
        ) : (
          <p className="text-sm text-muted">{empty}</p>
        )}
      </div>
    </section>
  );
}

type JobItem =
  paths["/jobs"]["get"]["responses"][200]["content"]["application/json"]["items"][number];

function JobRow({ job }: { job: JobItem }) {
  const t = useTranslations("jobsPage");
  return (
    <Link
      href={`/jobs/${job.slug}`}
      className="block h-full rounded-xl border border-border-token bg-surface p-4 transition-colors hover:border-brand"
    >
      <p className="text-base font-semibold">{job.title}</p>
      <p className="mt-0.5 text-sm text-muted">
        {job.tenant.name}
        {(job.location_district || job.location_state) &&
          ` · ${[job.location_district, job.location_state].filter(Boolean).join(", ")}`}
      </p>
      <p className="mt-1.5 text-xs text-muted">
        {experienceLabel(job, t)} · {salaryLabel(job, t)}
      </p>
    </Link>
  );
}

type RoleItem =
  paths["/roles/search"]["get"]["responses"][200]["content"]["application/json"][number];

/**
 * A job role, and on request the standards it is made of -- which is the
 * product's whole pitch shown in one place: this is what the work involves.
 */
function RoleRow({ role }: { role: RoleItem }) {
  const t = useTranslations("searchPage");
  const [open, setOpen] = useState(false);
  const standards = useQuery({
    queryKey: ["role-standards", role.slug],
    enabled: open,
    queryFn: async () =>
      (
        await api.GET("/roles/{slug}/standards", { params: { path: { slug: role.slug } } })
      ).data ?? null,
  });

  return (
    <div className="rounded-xl border border-border-token bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">{role.job_role}</span>
        <Badge>{t("standardsCount", { count: role.standards_count })}</Badge>
      </div>
      <p className="mt-0.5 font-mono text-[11px] text-muted">
        {role.qp_code}
        {role.nsqf_level != null && ` · NSQF ${role.nsqf_level}`}
        {role.sector_name && ` · ${role.sector_name}`}
      </p>
      {role.match_kind === "alias" && (
        <p className="mt-0.5 text-xs text-brand">
          {t("matchedVia", { term: role.matched_on })}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="text-sm text-brand hover:underline"
        >
          {open ? t("hideStandards") : t("showStandards")}
        </button>
        <ButtonLink href="/profile" size="sm" variant="secondary">
          {t("buildProfile")}
        </ButtonLink>
      </div>
      {open && (
        <ul className="mt-3">
          {standards.isPending && <li className="text-sm text-muted">{t("loading")}</li>}
          {(standards.data?.standards ?? []).map((s) => (
            <li key={s.slug} className="border-t border-border-token py-1.5 text-sm first:border-t-0">
              <Link href={`/skills/${s.slug}`} className="hover:underline">
                {s.name}
              </Link>
              {s.nos_code && (
                <span className="ml-2 font-mono text-[11px] text-muted">{s.nos_code}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
