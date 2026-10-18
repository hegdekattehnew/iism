import { getFormatter, getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { InterestPanel } from "@/components/InterestPanel";
import { ReportListing } from "@/components/ReportListing";
import { ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { creditsText, type Translate } from "@/lib/job-text";

export const dynamic = "force-dynamic";

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export default async function CourseDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = await getTranslations("coursesPage");
  const format = await getFormatter();

  const { data, error, response } = await api.GET(
    "/courses/{slug}",
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
  const fee =
    data.fee_inr == null || data.fee_inr === 0
      ? t("feeFree")
      : t("fee", { amount: inr(data.fee_inr) });

  const place =
    data.mode === "online"
      ? null
      : [data.location_district, data.location_state].filter(Boolean).join(", ") ||
        t("placeNotStated");
  const intake = data.starts_on
    ? t(data.started ? "startedOn" : "startsOn", {
        date: format.dateTime(new Date(`${data.starts_on}T00:00:00Z`), {
          dateStyle: "long",
          timeZone: "UTC",
        }),
      })
    : t("startNotStated");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ButtonLink href="/courses" variant="ghost" size="sm" className="-ml-3">
        ← {t("backToCourses")}
      </ButtonLink>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-brand">
          {t(`mode.${data.mode}`)}
        </span>
        <span className="rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
          {t(`language.${data.language}`)}
        </span>
        {data.nsqf_level != null && (
          <span className="rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
            {t("level", { level: data.nsqf_level })}
          </span>
        )}
      </div>

      <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      <p className="mt-1 text-lg text-muted">{data.tenant.name}</p>

      {/* The one thing a learner can do here. Until Sprint 24 this page
          was a dead end: the gap named, the course named, nothing to press. */}
      <div className="mt-6">
        <InterestPanel courseSlug={data.slug} organisation={data.tenant.name} />
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-4 rounded-xl border border-border-token bg-surface p-5 text-sm">
        <div>
          <dt className="text-xs text-muted">{t("feeLabel")}</dt>
          <dd className="mt-0.5 text-lg font-semibold">{fee}</dd>
        </div>
        {data.duration_hours != null && (
          <div>
            <dt className="text-xs text-muted">{t("durationLabel")}</dt>
            <dd className="mt-0.5 text-lg font-semibold">{t("duration", { hours: data.duration_hours })}</dd>
          </div>
        )}
        {place && (
          <div>
            <dt className="text-xs text-muted">{t("placeLabel")}</dt>
            <dd className="mt-0.5 text-lg font-semibold">{place}</dd>
          </div>
        )}
        <div>
          <dt className="text-xs text-muted">{t("intakeLabel")}</dt>
          <dd className="mt-0.5 text-lg font-semibold">{intake}</dd>
        </div>
        {data.qualification_name && (
          <div className="col-span-2">
            <dt className="text-xs text-muted">{t("qualificationLabel")}</dt>
            <dd className="mt-0.5 text-lg font-semibold">
              {data.qualification_name}
              {creditsText(data.qualification_credits, t as unknown as Translate) && (
                <span className="font-normal text-muted">
                  {` · ${creditsText(data.qualification_credits, t as unknown as Translate)}`}
                </span>
              )}
              <span className="mt-0.5 block text-xs font-normal text-muted">
                {t("qualificationNote")}
              </span>
            </dd>
          </div>
        )}
        {data.seats_left != null && (
          <div>
            <dt className="text-xs text-muted">{t("seatsLabel")}</dt>
            <dd className="mt-0.5 text-lg font-semibold">
              {data.seats_left === 0 ? t("full") : t("seatsLeft", { count: data.seats_left })}
            </dd>
          </div>
        )}
      </dl>

      {/* Who is behind it and what registering costs (UI-10; the vacancy page has the same strip). The
          page says "not yet verified"; a card in a list never does, because it would read as an
          accusation of every provider without a mark. */}
      <div className="mt-4 rounded-xl border border-border-token bg-surface p-4 text-sm">
        <p className={data.tenant.is_verified ? "font-medium text-success-text" : "text-muted"}>
          {data.tenant.is_verified ? t("verifiedProvider") : t("notVerifiedYet")}
        </p>
        <p className="mt-1 text-muted">{t("interestFree")}</p>
        {/* Its own line at the product's 44 px: an inline link in the sentence was a small target. */}
        <a
          href="#report"
          className="inline-flex min-h-11 items-center text-brand underline underline-offset-2"
        >
          {t("reportThis")}
        </a>
      </div>

      {description && <p className="mt-8 text-base leading-relaxed">{description}</p>}

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {t("skillsTaught")}
        </h2>
        <ul className="mt-3 flex flex-wrap gap-2">
          {(data.skills ?? []).map((s) => (
            <li key={s.skill.slug}>
              <Link
                href={`/skills/${s.skill.slug}`}
                className="inline-flex items-center gap-2 rounded-lg border border-border-token bg-surface px-3 py-1.5 text-sm transition-colors hover:border-brand"
              >
                <span>{s.skill.name}</span>
                {s.level_taught != null && (
                  <span className="text-xs text-muted">
                    {t("teachesToLevel", { level: s.level_taught })}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <div id="report" className="mt-10 scroll-mt-24">
        <ReportListing kind="course" slug={data.slug} />
      </div>
    </div>
  );
}
