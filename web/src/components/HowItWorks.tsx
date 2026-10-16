import { getTranslations } from "next-intl/server";

import { Section, SectionHeading } from "@/components/ui";

export async function HowItWorks() {
  const t = await getTranslations("how");
  const steps = [1, 2, 3, 4] as const;

  return (
    <Section id="how-it-works">
      <SectionHeading title={t("title")} subtitle={t("subtitle")} />

      <ol className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((n) => (
          <li
            key={n}
            className="relative rounded-xl border border-border-token bg-surface p-5"
          >
            {/* The number beside the title, not above it: four stacked cards were 700px of a phone
                screen for sixteen words (Sprint 70, UI-01). */}
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand text-sm font-bold text-brand-contrast">
                {n}
              </span>
              <h3 className="text-base font-semibold">{t(`step${n}Title`)}</h3>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              {t(`step${n}Body`)}
            </p>
          </li>
        ))}
      </ol>

      <p className="mt-8 border-l-2 border-brand pl-4 text-sm text-muted">
        {t("note")}
      </p>
    </Section>
  );
}
