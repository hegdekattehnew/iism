import { getLocale, getTranslations } from "next-intl/server";

import { api } from "@/lib/api";

// A standard can publish thirty-odd elements. Enough to show what it demands
// without turning the page into a syllabus.
const SHOWN = 8;

export async function SkillRequirements({ slug }: { slug: string }) {
  const t = await getTranslations("skillsPage");
  const locale = await getLocale();
  const isHi = locale === "hi";

  const { data, error } = await api.GET("/skills/{slug}/requirements", {
    params: { path: { slug } },
  });

  // Never let this take down the skill page around it.
  if (error || !data) return null;

  const { elements, criteria_count, knowledge, generic_skills } = data;
  if (elements.length === 0 && knowledge.length === 0 && generic_skills.length === 0) {
    return null;
  }

  const text = (en: string, hi?: string | null) => (isHi && hi ? hi : en);

  return (
    <section className="mt-10">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
        {t("requirements")}
      </h2>

      {elements.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("noRequirements")}</p>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">{t("requirementsIntro")}</p>
          <p className="mt-1 text-sm font-medium">
            {t("criteriaCount", { count: criteria_count })}
          </p>

          <ol className="mt-4 space-y-4">
            {elements.slice(0, SHOWN).map((element, i) => (
              <li key={i} className="rounded-xl border border-border-token bg-surface p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold">
                    {text(element.name_en, element.name_hi)}
                  </h3>
                  {element.total_marks != null && (
                    <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted">
                      {t("marks", { marks: element.total_marks })}
                    </span>
                  )}
                </div>

                <ul className="mt-2.5 space-y-1.5">
                  {(element.criteria ?? []).map((c, j) => (
                    <li key={j} className="flex gap-2 text-sm">
                      {c.pc_ref && (
                        <span className="shrink-0 font-mono text-[11px] text-muted">
                          {c.pc_ref}
                        </span>
                      )}
                      <span className="text-muted">
                        {text(c.description_en, c.description_hi)}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>

          {elements.length > SHOWN && (
            <p className="mt-3 text-sm text-muted">
              {t("qualificationsMore", { count: elements.length - SHOWN })}
            </p>
          )}
        </>
      )}

      {knowledge.length > 0 && (
        <div className="mt-8">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("knowledge")}
          </h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
            {knowledge.slice(0, SHOWN).map((k, i) => (
              <li key={i}>{k}</li>
            ))}
          </ul>
        </div>
      )}

      {generic_skills.length > 0 && (
        <div className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("genericSkills")}
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {generic_skills.slice(0, SHOWN * 2).map((g, i) => (
              <span
                key={i}
                className="rounded-lg border border-border-token bg-surface px-3 py-1.5 text-sm text-muted"
              >
                {g}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
