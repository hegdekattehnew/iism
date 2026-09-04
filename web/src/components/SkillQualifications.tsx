import { getLocale, getTranslations } from "next-intl/server";

import { api } from "@/lib/api";

// Enough to show the shape of a unit's use without turning the page into a
// listing. The cross-cutting employability unit sits in 1,195 qualifications.
const SHOWN = 12;

const TONE: Record<string, string> = {
  compulsory: "bg-accent-soft text-brand",
  elective: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
  optional: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

export async function SkillQualifications({ slug }: { slug: string }) {
  const t = await getTranslations("skillsPage");
  const locale = await getLocale();
  const isHi = locale === "hi";

  const { data, error } = await api.GET("/skills/{slug}/qualifications", {
    params: { path: { slug }, query: { limit: SHOWN } },
  });

  // A failure here must not take down the skill page around it.
  if (error || !data) return null;

  const { items, total } = data;
  const fmtLevel = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

  return (
    <section className="mt-10">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
        {t("qualifications")}
      </h2>

      {total === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("noQualifications")}</p>
      ) : (
        <>
          {/* Why one unit shows several different levels. Without this the list
              looks inconsistent rather than correct. */}
          <p className="mt-2 text-sm text-muted">{t("qualificationsIntro")}</p>
          <p className="mt-1 text-sm font-medium">
            {t("qualificationsCount", { count: total })}
          </p>

          <ul className="mt-4 space-y-2">
            {items.map((q) => (
              <li
                key={`${q.qp_code}-${q.version}-${q.requirement}-${q.group_name ?? ""}`}
                className="rounded-xl border border-border-token bg-surface p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                      TONE[q.requirement] ?? TONE.optional
                    }`}
                  >
                    {t(`requirement.${q.requirement}`)}
                  </span>
                  {q.nsqf_level != null && (
                    <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                      {t("levelShort", { level: fmtLevel(q.nsqf_level) })}
                    </span>
                  )}
                  <span className="font-mono text-[11px] text-muted">
                    {q.qp_code} v{q.version}
                  </span>
                </div>

                <p className="mt-2 text-sm font-semibold">
                  {isHi && q.name_hi ? q.name_hi : q.name_en}
                </p>
                {q.sector_name_en && (
                  <p className="mt-0.5 text-xs text-muted">{q.sector_name_en}</p>
                )}

                {/* An elective belongs to a named "choose one of these" bundle.
                    Showing it without the group presents a choice as a rule. */}
                {q.group_name && (
                  <p className="mt-1.5 text-xs text-brand">
                    {t("electiveGroup", { group: q.group_name })}
                  </p>
                )}
              </li>
            ))}
          </ul>

          {total > items.length && (
            <p className="mt-3 text-sm text-muted">
              {t("qualificationsMore", { count: total - items.length })}
            </p>
          )}
        </>
      )}
    </section>
  );
}
