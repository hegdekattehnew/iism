import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

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

  const { data, error } = await api.GET("/courses/{slug}", {
    params: { path: { slug } },
  });
  if (error || !data) notFound();

  const isHi = locale === "hi";
  const title = isHi && data.title_hi ? data.title_hi : data.title_en;
  const description =
    isHi && data.description_hi ? data.description_hi : data.description_en;
  const fee =
    data.fee_inr == null || data.fee_inr === 0
      ? t("feeFree")
      : t("fee", { amount: inr(data.fee_inr) });

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
      </dl>

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
                <span>{isHi && s.skill.name_hi ? s.skill.name_hi : s.skill.name_en}</span>
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

      <p className="mt-10 border-t border-border-token pt-5 font-mono text-xs text-muted">
        {data.slug}
      </p>
    </div>
  );
}
