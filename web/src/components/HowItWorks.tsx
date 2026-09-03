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
            className="relative rounded-xl border border-border-token bg-surface p-6"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand text-sm font-bold text-brand-contrast">
              {n}
            </span>
            <h3 className="mt-4 text-base font-semibold">
              {t(`step${n}Title`)}
            </h3>
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
