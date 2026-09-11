import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { SkillQualifications } from "@/components/SkillQualifications";
import { SkillRequirements } from "@/components/SkillRequirements";
import { SkillRelated } from "@/components/SkillRelated";
import { ButtonLink } from "@/components/ui";
import { api } from "@/lib/api";

// Rendered per request: skills change as the taxonomy is imported, and there is
// no build-time guarantee the API is reachable.
export const dynamic = "force-dynamic";

const SCRIPTS = ["latin", "devanagari", "transliteration"] as const;

export default async function SkillDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const locale = await getLocale();
  const t = await getTranslations("skillsPage");

  const { data, error, response } = await api.GET("/skills/{slug}", {
    params: { path: { slug } },
  });
  // Only a 404 is "not found". Every failure used to land here, so an API
  // outage told visitors the listing did not exist; `error.tsx` now says the
  // page is unavailable instead.
  if (response.status === 404) notFound();
  if (error || !data) throw new Error(`API responded ${response.status}`);

  const isHi = locale === "hi";
  const title = isHi && data.name_hi ? data.name_hi : data.name_en;
  const secondary = isHi && data.name_hi ? data.name_en : data.name_hi;
  const description =
    isHi && data.description_hi ? data.description_hi : data.description_en;

  const byScript = SCRIPTS.map((script) => ({
    script,
    forms: (data.aliases ?? []).filter((a) => a.script === script),
  })).filter((g) => g.forms.length > 0);

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ButtonLink href="/skills" variant="ghost" size="sm" className="-ml-3">
        ← {t("backToSkills")}
      </ButtonLink>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-brand">
          {t(`type.${data.skill_type}`)}
        </span>
        <span className="rounded-md bg-surface-muted px-2.5 py-1 text-xs font-medium text-muted">
          {data.nsqf_level != null
            ? t("level", { level: data.nsqf_level })
            : t("noLevel")}
        </span>
        {data.nos_code && (
          <span className="rounded-md border border-border-token px-2.5 py-1 font-mono text-xs text-muted">
            {data.nos_code}
            {data.nos_version ? ` v${data.nos_version}` : ""}
          </span>
        )}
      </div>

      {/* Retired: superseded by the standards it maps to, but still reachable
          because profiles reference it. Saying so beats letting it look like a
          standard it is not. */}
      {data.source === "legacy" && (
        <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300">
          {t("curatedNotice")}
        </p>
      )}

      <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
      {secondary && <p className="mt-1 text-lg text-muted">{secondary}</p>}

      {description && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("description")}
          </h2>
          <p className="mt-2 text-base leading-relaxed">{description}</p>
        </section>
      )}

      {byScript.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("aliases")}
          </h2>
          <dl className="mt-3 space-y-4">
            {byScript.map(({ script, forms }) => (
              <div key={script}>
                <dt className="text-xs text-muted">{t(`aliasScript.${script}`)}</dt>
                <dd className="mt-1.5 flex flex-wrap gap-2">
                  {forms.map((a) => (
                    <span
                      key={a.surface_form}
                      className="rounded-lg border border-border-token bg-surface px-3 py-1.5 text-sm"
                    >
                      {a.surface_form}
                    </span>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <SkillRequirements slug={data.slug} />

      <SkillQualifications slug={data.slug} />

      <SkillRelated slug={data.slug} />

      <p className="mt-10 border-t border-border-token pt-5 font-mono text-xs text-muted">
        {data.slug}
      </p>
    </div>
  );
}
