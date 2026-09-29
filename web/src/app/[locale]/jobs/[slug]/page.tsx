import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { ApplyPanel } from "@/components/ApplyPanel";
import { ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = await getTranslations("jobsPage");

  const { data, error, response } = await api.GET(
    "/jobs/{slug}",
    // Server-side: the browser middleware that normally carries this
    // header does not run here, and without it the API answers in the
    // default language on a page that is not in it (ADR-041).
    { params: { path: { slug } }, headers: { "accept-language": locale } },
  );
  // Only a 404 is "not found". Every failure used to land here, so an API
  // outage told visitors the listing did not exist; `error.tsx` now says the
  // page is unavailable instead.
  if (response.status === 404) notFound();
  if (error || !data) throw new Error(`API responded ${response.status}`);

  const title = data.title;
  const description =
    data.description;

  // Mandatory first — those are what actually gate a hire.
  const skills = [...(data.skills ?? [])].sort(
    (a, b) =>
      Number(b.is_mandatory) - Number(a.is_mandatory) || b.importance - a.importance,
  );

  const experience =
    data.experience_min_years === 0 && !data.experience_max_years
      ? t("experienceNone")
      : data.experience_max_years
        ? t("experienceRange", {
            min: data.experience_min_years,
            max: data.experience_max_years,
          })
        : t("experience", { min: data.experience_min_years });

  const salary =
    data.salary_min_inr && data.salary_max_inr
      ? t("salary", { min: inr(data.salary_min_inr), max: inr(data.salary_max_inr) })
      : data.salary_min_inr
        ? t("salaryFrom", { min: inr(data.salary_min_inr) })
        : t("salaryUndisclosed");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ButtonLink href="/jobs" variant="ghost" size="sm" className="-ml-3">
        ← {t("backToJobs")}
      </ButtonLink>
      {/* Client-side: whether someone is signed in, and whether they are a job
          seeker, is only knowable in the browser. */}
      <div className="mt-6">
        <ApplyPanel
          jobSlug={data.slug}
          organisation={data.tenant.name}
          isOpen={data.is_open}
        />
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-brand">
          {t(`employmentType.${data.employment_type}`)}
        </span>
        {data.nsqf_level_min != null && (
          <span className="rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
            {t("minLevel", { level: data.nsqf_level_min })}
          </span>
        )}
      </div>

      <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      <p className="mt-1 text-lg text-muted">
        {data.tenant.name}
        {data.location_district ? ` · ${data.location_district}` : ""}
        {data.location_state ? `, ${data.location_state}` : ""}
      </p>

      <dl className="mt-6 grid grid-cols-1 gap-4 rounded-xl border border-border-token bg-surface p-5 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted">{t("experienceLabel")}</dt>
          <dd className="mt-0.5 font-medium">{experience}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("salaryLabel")}</dt>
          <dd className="mt-0.5 font-medium">{salary}</dd>
        </div>
      </dl>

      {description && (
        <p className="mt-8 text-base leading-relaxed">{description}</p>
      )}

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {t("requiredSkills")}
        </h2>
        <ul className="mt-3 space-y-2">
          {skills.map((s) => (
            <li key={s.skill.slug}>
              <Link
                href={`/skills/${s.skill.slug}`}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-border-token bg-surface px-3 py-2 text-sm transition-colors hover:border-brand"
              >
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                    s.is_mandatory
                      ? "bg-brand text-brand-contrast"
                      : "bg-surface-muted text-muted"
                  }`}
                >
                  {s.is_mandatory ? t("mandatory") : t("optional")}
                </span>
                <span className="font-medium">
                  {s.skill.name}
                </span>
                <span className="ml-auto text-xs text-muted">
                  {t("importance", { n: s.importance })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <p className="mt-10 border-t border-border-token pt-5 font-mono text-xs text-muted">
        {data.slug}
      </p>
    </div>
  );
}
