import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { ApplyPanel } from "@/components/ApplyPanel";
import { ReportListing } from "@/components/ReportListing";
import { ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { daysToClose, experienceText, payText, type Translate } from "@/lib/job-text";
import { payLine, yearlyLine } from "@/lib/pay";
import { presentRequirements } from "@/lib/requirements";

export const dynamic = "force-dynamic";

export default async function JobDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = await getTranslations("jobsPage");
  const say = t as unknown as Translate;

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

  // How workers rated whoever posted this. A second, optional call: a failure
  // here is "no rating to show", never a reason the vacancy fails to load.
  const rated = await api
    .GET("/jobs/{job_slug}/poster-rating", { params: { path: { job_slug: slug } } })
    .then((r) => r.data?.rating ?? null)
    .catch(() => null);
  const tr = await getTranslations("reviews");

  const title = data.title;
  const description = data.description;

  // Duplicates collapsed, shouted names sentence-cased and the generic entries every qualification
  // carries moved aside (Sprint 69, UI-09); mandatory first, since those are what gate a hire.
  const { main, also } = presentRequirements(
    (data.skills ?? []).map((s) => ({
      slug: s.skill.slug,
      name: s.skill.name,
      mandatory: s.is_mandatory,
      importance: s.importance,
    })),
  );

  const experience = experienceText(data, say);

  // What people say it is (a month), then what was posted (a year) beneath it (UI-05).
  const pay = payLine(data.salary_min_inr, data.salary_max_inr, data.employment_type);
  const salary = payText(pay, say, locale);
  const salaryYearly =
    pay.unit === "month"
      ? payText(yearlyLine(data.salary_min_inr, data.salary_max_inr), say, locale)
      : null;
  const days = daysToClose(data.closes_at);

  return (
    // A column so the apply bar can come second in the document and last on a phone (`order-last`
    // below), where it sticks to the bottom of the screen.
    <div className="mx-auto flex w-full max-w-3xl flex-col px-5 py-12 sm:py-16">
      <ButtonLink href="/jobs" variant="ghost" size="sm" className="-ml-3 self-start">
        ← {t("backToJobs")}
      </ButtonLink>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-brand">
          {t(`employmentType.${data.employment_type}`)}
        </span>
        {data.nsqf_level_min != null && (
          <span className="rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
            {t("minLevel", { level: data.nsqf_level_min })}
          </span>
        )}
        {days !== null && (
          <span className="rounded-md bg-warning-surface px-2.5 py-1 text-xs font-medium text-warning-text">
            {t("closesIn", { days })}
          </span>
        )}
      </div>

      <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      <p className="mt-1 text-lg text-muted">
        {data.tenant.name}
        {data.location_district ? ` · ${data.location_district}` : ""}
        {data.location_state ? `, ${data.location_state}` : ""}
      </p>
      {rated && (
        <p className="mt-1 text-sm text-muted">
          {tr("ofPoster")}:{" "}
          {tr("summary", {
            average: new Intl.NumberFormat(locale === "hi" ? "hi-IN" : "en-IN", {
              maximumFractionDigits: 1,
            }).format(rated.average),
            count: rated.count,
          })}
        </p>
      )}

      <dl className="mt-6 grid grid-cols-1 gap-4 rounded-xl border border-border-token bg-surface p-5 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted">{t("salaryLabel")}</dt>
          <dd className="mt-0.5 text-base font-semibold">{salary}</dd>
          {salaryYearly && <dd className="text-xs text-muted">{salaryYearly}</dd>}
        </div>
        <div>
          <dt className="text-xs text-muted">{t("experienceLabel")}</dt>
          <dd className="mt-0.5 font-medium">{experience}</dd>
        </div>
      </dl>

      {/* Who is behind it and what they may not ask for. The page says "not yet verified"; a card in
          a list never does (it would read as an accusation of every employer without a mark). */}
      <div className="mt-4 rounded-xl border border-border-token bg-surface p-4 text-sm">
        <p className={data.tenant.is_verified ? "font-medium text-success-text" : "text-muted"}>
          {data.tenant.is_verified ? t("verifiedEmployer") : t("notVerifiedYet")}
        </p>
        <p className="mt-1 text-muted">
          {t("neverPay")}{" "}
          <a href="#report" className="text-brand underline underline-offset-2">
            {t("reportThis")}
          </a>
        </p>
      </div>

      {/* Client-side: whether someone is signed in, and whether they are a job seeker, is only
          knowable in the browser. Second in the document, so a screen reader meets it with the
          facts; last on a phone, where it sticks to the bottom of the screen and is under the
          thumb at any scroll position (UI-08). A static block beside the content from `lg`. */}
      <div
        data-testid="apply-bar"
        className="sticky bottom-0 z-20 -mx-5 mt-6 max-h-[85vh] overflow-y-auto border-t border-border-token bg-surface px-5 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] empty:hidden max-lg:order-last lg:static lg:mx-0 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0"
      >
        <ApplyPanel
          jobSlug={data.slug}
          organisation={data.tenant.name}
          isOpen={data.is_open}
        />
      </div>

      {description && <p className="mt-8 text-base leading-relaxed">{description}</p>}

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {t("requiredSkills")}
        </h2>
        <ul className="mt-3 space-y-2">
          {main.map((s) => (
            <li key={s.slug}>
              <Link
                href={`/skills/${s.slug}`}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-border-token bg-surface px-3 py-3 text-sm transition-colors hover:border-brand"
              >
                <span className="font-medium">{s.name}</span>
                {s.mandatory && (
                  <span className="ml-auto rounded bg-brand px-1.5 py-0.5 text-xs font-bold text-brand-contrast">
                    {t("mandatory")}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
        {also.length > 0 && (
          <details className="mt-4 text-sm">
            <summary className="cursor-pointer py-2 text-muted">
              {t("alsoCovered", { count: also.length })}
            </summary>
            <ul className="mt-2 space-y-2">
              {also.map((s) => (
                <li key={s.slug}>
                  <Link
                    href={`/skills/${s.slug}`}
                    className="block rounded-lg border border-border-token bg-surface px-3 py-3 text-muted transition-colors hover:border-brand"
                  >
                    {s.name}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <div id="report" className="mt-10 scroll-mt-24">
        <ReportListing kind="job" slug={data.slug} />
      </div>
    </div>
  );
}
