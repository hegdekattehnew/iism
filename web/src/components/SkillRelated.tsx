import { getLocale, getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";

const inr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

/**
 * The edges of the graph, rendered on a skill page: what this skill leads to,
 * and what teaches it. This is the point at which the taxonomy stops being a
 * glossary and starts being navigable.
 */
export async function SkillRelated({ slug }: { slug: string }) {
  const locale = await getLocale();
  const t = await getTranslations("skillLinks");
  const tc = await getTranslations("coursesPage");
  const isHi = locale === "hi";

  const [jobsRes, coursesRes] = await Promise.all([
    api.GET("/skills/{slug}/jobs", { params: { path: { slug }, query: { limit: 6 } } }),
    api.GET("/skills/{slug}/courses", { params: { path: { slug }, query: { limit: 6 } } }),
  ]);

  const jobs = jobsRes.data ?? [];
  const courses = coursesRes.data ?? [];

  return (
    <div className="mt-12 grid grid-cols-1 gap-8 border-t border-border-token pt-10 lg:grid-cols-2">
      <section>
        <h2 className="text-sm font-semibold">{t("jobsTitle")}</h2>
        {jobs.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{t("noJobs")}</p>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {jobs.map((j) => (
                <li key={j.slug}>
                  <Link
                    href={`/jobs/${j.slug}`}
                    className="block rounded-lg border border-border-token bg-surface px-3 py-2.5 transition-colors hover:border-brand"
                  >
                    <p className="text-sm font-medium">
                      {isHi && j.title_hi ? j.title_hi : j.title_en}
                    </p>
                    <p className="text-xs text-muted">
                      {j.tenant.name}
                      {j.location_district ? ` · ${j.location_district}` : ""}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            <Link
              href={`/jobs?skill=${slug}`}
              className="mt-3 inline-block text-sm font-medium text-brand hover:underline"
            >
              {t("viewAllJobs")} →
            </Link>
          </>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold">{t("coursesTitle")}</h2>
        {courses.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{t("noCourses")}</p>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {courses.map((c) => (
                <li key={c.slug}>
                  <Link
                    href={`/courses/${c.slug}`}
                    className="block rounded-lg border border-border-token bg-surface px-3 py-2.5 transition-colors hover:border-brand"
                  >
                    <p className="text-sm font-medium">
                      {isHi && c.title_hi ? c.title_hi : c.title_en}
                    </p>
                    <p className="text-xs text-muted">
                      {c.tenant.name} ·{" "}
                      {c.fee_inr ? tc("fee", { amount: inr(c.fee_inr) }) : tc("feeFree")}
                      {" · "}
                      {tc(`mode.${c.mode}`)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            <Link
              href={`/courses?skill=${slug}`}
              className="mt-3 inline-block text-sm font-medium text-brand hover:underline"
            >
              {t("viewAllCourses")} →
            </Link>
          </>
        )}
      </section>
    </div>
  );
}
