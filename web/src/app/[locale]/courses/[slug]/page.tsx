import { NextBatches } from "@/components/NextBatches";
import { getFormatter, getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { InterestPanel } from "@/components/InterestPanel";
import { ReportListing } from "@/components/ReportListing";
import { ButtonLink } from "@/components/ui";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Fact, FactValue, Facts } from "@/components/ui/fact";
import {
  AwardIcon,
  BuildingIcon,
  CalendarIcon,
  ClockIcon,
  GlobeIcon,
  MapPinIcon,
  RupeeIcon,
  TargetIcon,
  UsersIcon,
} from "@/components/ui/icons";
import { TrustStrip } from "@/components/ui/trust-strip";
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
  // A date that has passed is not an "intake" and "40 seats left" beside it is not an offer: the page
  // said "Next intake: Started September 29, 2026 . 40 seats left" for a course three weeks in
  // (Sprint 91, the designer's review). A started group says so, and sends the learner to ask.
  const started = data.starts_on != null && data.started;
  const when = data.starts_on
    ? format.dateTime(new Date(`${data.starts_on}T00:00:00Z`), { dateStyle: "long", timeZone: "UTC" })
    : null;
  const intake = when === null ? t("startNotStated") : started ? when : t("startsOn", { date: when });

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ButtonLink href="/courses" variant="ghost" size="sm" className="-ml-3">
        ← {t("backToCourses")}
      </ButtonLink>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Badge tone="brand" size="md">
          {data.mode === "online" ? <GlobeIcon className="h-4 w-4" /> : <BuildingIcon className="h-4 w-4" />}
          {t(`mode.${data.mode}`)}
        </Badge>
        <Badge size="md" className="font-medium">
          {t(`language.${data.language}`)}
        </Badge>
        {data.nsqf_level != null && (
          <Badge size="md" className="font-medium">
            <TargetIcon className="h-4 w-4" />
            {t("level", { level: data.nsqf_level })}
          </Badge>
        )}
      </div>

      <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      {/* The provider's mark beside its name, as on the card in the list (Sprint 85). The name is a
          link to the organisation's own page (Sprint 94, ADR-102). */}
      <div className="mt-3 flex items-center gap-3">
        <Avatar name={data.tenant.name} />
        <Link
          href={`/providers/${data.tenant.slug}`}
          className="inline-flex min-h-11 min-w-0 flex-1 items-center text-lg text-muted underline-offset-4 hover:text-foreground hover:underline"
        >
          {data.tenant.name}
        </Link>
      </div>

      {/* The one thing a learner can do here. Until Sprint 24 this page
          was a dead end: the gap named, the course named, nothing to press. */}
      <div className="mt-6">
        <InterestPanel courseSlug={data.slug} organisation={data.tenant.name} />
      </div>

      <Facts className="mt-6 grid-cols-2">
        <Fact icon={<RupeeIcon />} label={t("feeLabel")}>
          <FactValue large>{fee}</FactValue>
        </Fact>
        {data.duration_hours != null && (
          <Fact icon={<ClockIcon />} label={t("durationLabel")}>
            <FactValue large>{t("duration", { hours: data.duration_hours })}</FactValue>
          </Fact>
        )}
        {place && (
          <Fact icon={<MapPinIcon />} label={t("placeLabel")}>
            <FactValue large>{place}</FactValue>
          </Fact>
        )}
        <Fact icon={<CalendarIcon />} label={started ? t("startedLabel") : t("intakeLabel")}>
          <FactValue large>
            {intake}
            {started && <span className="mt-0.5 block text-xs font-normal text-muted">{t("startedAsk")}</span>}
          </FactValue>
        </Fact>
        {data.qualification_name && (
          <Fact icon={<AwardIcon />} label={t("qualificationLabel")} wide>
            <FactValue large>
              {data.qualification_name}
              {creditsText(data.qualification_credits, t as unknown as Translate) && (
                <span className="font-normal text-muted">
                  {` · ${creditsText(data.qualification_credits, t as unknown as Translate)}`}
                </span>
              )}
              <span className="mt-0.5 block text-xs font-normal text-muted">
                {t("qualificationNote")}
              </span>
            </FactValue>
          </Fact>
        )}
        {data.seats_left != null && !(started && data.seats_left > 0) && (
          <Fact icon={<UsersIcon />} label={t("seatsLabel")}>
            <FactValue large>
              {data.seats_left === 0 ? t("full") : t("seatsLeft", { count: data.seats_left })}
            </FactValue>
          </Fact>
        )}
      </Facts>

      {/* The batches planned for it, nearest first (Sprint 100): shows nothing for a course with none. */}
      <NextBatches course={data.slug} />

      {/* Who is behind it and what registering costs (UI-10; the vacancy page has the same strip). The
          page says "not yet verified"; a card in a list never does, because it would read as an
          accusation of every provider without a mark. */}
      <div className="mt-4">
        <TrustStrip
          verified={data.tenant.is_verified}
          statement={data.tenant.is_verified ? t("verifiedProvider") : t("notVerifiedYet")}
        >
          {data.tenant.is_verified && <p className="mt-1 text-muted">{t("verifiedBy")}</p>}
          <p className="mt-1 text-muted">{t("interestFree")}</p>
          {/* Its own line at the product's 44 px: an inline link in the sentence was a small target. */}
          <a
            href="#report"
            className="inline-flex min-h-11 items-center text-brand underline underline-offset-2"
          >
            {t("reportThis")}
          </a>
        </TrustStrip>
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
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border-token bg-surface px-3 py-1.5 text-sm transition-colors hover:border-brand"
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
