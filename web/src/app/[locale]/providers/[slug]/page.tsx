import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { CourseCard } from "@/components/cards/CourseCard";
import { ButtonLink } from "@/components/ui";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Fact, FactValue, Facts } from "@/components/ui/fact";
import {
  AwardIcon,
  BookOpenIcon,
  BuildingIcon,
  CalendarIcon,
  GlobeIcon,
  MapPinIcon,
  ShieldCheckIcon,
  TargetIcon,
} from "@/components/ui/icons";
import { TrustStrip } from "@/components/ui/trust-strip";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

/** A link an organisation typed is only a link if it is a web address: `javascript:` is not. */
const webAddress = (url: string | null | undefined) =>
  url && /^https?:\/\//i.test(url.trim()) ? url.trim() : null;

/**
 * A training organisation's own page (Sprint 94, ADR-102).
 *
 * One page for an organisation that sells courses, one that delivers training and one that does both:
 * what it **does** is two badges, what it **says about itself** (affiliations, year established,
 * languages) is labelled as its own claim and never sorted or filtered on (ADR-085), what it **trains
 * in** is read from its published courses by the server and never stored, and its **courses** are the
 * published ones on the same card as the list. Its **centres** (Sprint 95) are listed by place, each with its
 * own "Address checked" mark when an operator has checked it: never the organisation's mark, and a
 * card never says an address is unchecked. The courses it delivers for others arrive with the sprint
 * that builds them. The contact address is not here: the server never sends it.
 */
export default async function ProviderPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = await getTranslations("providerPage");

  const { data, error, response } = await api.GET("/providers/{slug}", {
    params: { path: { slug } },
    // Server-side: the browser middleware that carries this header does not run here (ADR-041).
    headers: { "accept-language": locale },
  });
  // Only a 404 is "not found"; an outage must not tell a visitor an organisation does not exist.
  if (response.status === 404) notFound();
  if (error || !data) throw new Error(`API responded ${response.status}`);

  // What it is authorised to deliver for others (Sprint 97). A second request, and a failure of it
  // costs the page one section, never the page: it is extra, not the organisation.
  const delivered = await api
    .GET("/providers/{slug}/delivery", { params: { path: { slug } } })
    .then((r) => (r.data?.items ?? []))
    .catch(() => []);

  // Lists that default to empty are optional in the generated types.
  const sectors = data.sectors ?? [];
  const courses = data.courses ?? [];
  const coursesTotal = data.courses_total ?? 0;
  const centres = data.centres ?? [];
  const website = webAddress(data.website);
  const claims = data.year_established != null || data.teaching_languages || data.affiliations;

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ButtonLink href="/courses" variant="ghost" size="sm" className="-ml-3">
        ← {t("back")}
      </ButtonLink>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {data.publishes_courses && (
          <Badge tone="brand" size="md">
            <BookOpenIcon className="h-4 w-4" />
            {t("sells")}
          </Badge>
        )}
        {data.delivers_training && (
          <Badge tone="brand" size="md">
            <BuildingIcon className="h-4 w-4" />
            {t("delivers")}
          </Badge>
        )}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Avatar name={data.name} />
        <h1 className="min-w-0 flex-1 text-3xl font-bold tracking-tight sm:text-4xl">{data.name}</h1>
      </div>

      <div className="mt-6">
        <TrustStrip
          verified={data.is_verified}
          statement={data.is_verified ? t("verified") : t("notVerifiedYet")}
        >
          {data.is_verified && <p className="mt-1 text-muted">{t("verifiedBy")}</p>}
        </TrustStrip>
      </div>

      {data.description && <p className="mt-8 text-base leading-relaxed">{data.description}</p>}

      {(data.city || website || claims) && (
        <Facts className="mt-8 grid-cols-2">
          {data.city && (
            <Fact icon={<MapPinIcon />} label={t("cityLabel")}>
              <FactValue large>{data.city}</FactValue>
            </Fact>
          )}
          {data.year_established != null && (
            <Fact icon={<CalendarIcon />} label={t("establishedLabel")}>
              <FactValue large>{data.year_established}</FactValue>
            </Fact>
          )}
          {data.teaching_languages && (
            <Fact icon={<GlobeIcon />} label={t("languagesLabel")}>
              <FactValue large>{data.teaching_languages}</FactValue>
            </Fact>
          )}
          {website && (
            <Fact icon={<GlobeIcon />} label={t("websiteLabel")}>
              <FactValue>
                <a
                  href={website}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="inline-flex min-h-11 items-center break-all text-brand underline underline-offset-2"
                >
                  {website.replace(/^https?:\/\//i, "")}
                </a>
              </FactValue>
            </Fact>
          )}
          {data.affiliations && (
            <Fact icon={<AwardIcon />} label={t("affiliationsLabel")} wide>
              <FactValue>
                {data.affiliations}
                <span className="mt-0.5 block text-xs font-normal text-muted">{t("statedByNote")}</span>
              </FactValue>
            </Fact>
          )}
        </Facts>
      )}

      {sectors.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">{t("trainsIn")}</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {sectors.map((s) => (
              <li key={s.name}>
                <Badge size="md" className="font-medium">
                  <TargetIcon className="h-4 w-4" />
                  {s.name}
                  <span className="text-xs text-muted">{t("sectorCourses", { count: s.courses })}</span>
                </Badge>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">{t("sectorsNote")}</p>
        </section>
      )}

      {data.delivers_training && (
        <section className="mt-10">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("centresTitle", { count: centres.length })}
          </h2>
          {centres.length === 0 ? (
            <p className="mt-3 text-sm text-muted">{t("noCentres")}</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {centres.map((c) => {
                const place = [c.location_district, c.location_state].filter(Boolean).join(", ");
                return (
                  <li key={c.slug} className="rounded-xl border border-border-token bg-surface p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <h3 className="min-w-0 grow basis-48 text-base font-semibold">{c.name}</h3>
                      {c.is_verified && (
                        <Badge tone="good" size="md">
                          <ShieldCheckIcon className="h-4 w-4" />
                          {t("addressChecked")}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-2 flex items-start gap-1.5 text-sm text-muted">
                      <MapPinIcon className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>{[c.address, place].filter(Boolean).join(" · ")}</span>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      {delivered.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("authorisedTitle")}
          </h2>
          <p className="mt-2 text-xs text-muted">{t("authorisedNote")}</p>
          <ul className="mt-3 space-y-2">
            {delivered.map((d) => (
              <li key={`${d.provider.slug}:${d.course?.slug ?? "all"}`}>
                <Link
                  href={`/providers/${d.provider.slug}`}
                  className="flex min-h-11 items-center gap-2 rounded-xl border border-border-token bg-surface px-4 py-3 text-sm hover:bg-surface-muted"
                >
                  <BuildingIcon className="h-4 w-4 shrink-0" />
                  <span className="min-w-0">
                    {d.course
                      ? t("courseBy", { course: d.course.title, organisation: d.provider.name })
                      : t("everyCourseOf", { organisation: d.provider.name })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          {t("coursesTitle", { count: coursesTotal })}
        </h2>
        {courses.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            {data.publishes_courses ? t("noCourses") : t("noCoursesDeliverer")}
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {courses.map((course) => (
              <li key={course.slug}>
                <CourseCard course={course} />
              </li>
            ))}
          </ul>
        )}
        {coursesTotal > courses.length && (
          <p className="mt-3 text-sm text-muted">
            {t("moreCourses", { shown: courses.length, total: coursesTotal })}
          </p>
        )}
      </section>
    </div>
  );
}
