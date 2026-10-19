import { getTranslations } from "next-intl/server";

import { Section, SectionHeading } from "@/components/ui";
import { IconTile } from "@/components/ui/icon-tile";
import { BookOpenIcon, BriefcaseIcon, SearchIcon, TargetIcon } from "@/components/ui/icons";

// One icon a step (Sprint 85, BL-19.15): aim, look at the gap, close it, get matched.
const STEP_ICONS = { 1: TargetIcon, 2: SearchIcon, 3: BookOpenIcon, 4: BriefcaseIcon } as const;

export async function HowItWorks() {
  const t = await getTranslations("how");
  const steps = [1, 2, 3, 4] as const;

  return (
    <Section id="how-it-works">
      <SectionHeading title={t("title")} subtitle={t("subtitle")} />

      <ol className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((n) => {
          const Icon = STEP_ICONS[n];
          return (
            <li
              key={n}
              className="relative rounded-xl border border-border-token bg-surface p-5"
            >
              {/* The number beside the title, not above it: four stacked cards were 700px of a phone
                  screen for sixteen words (Sprint 70, UI-01). */}
              <div className="flex items-center gap-3">
                <IconTile>
                  <Icon />
                </IconTile>
                <h3 className="min-w-0 flex-1 text-base font-semibold">{t(`step${n}Title`)}</h3>
                {/* The order stays visible: the icon says what the step is, the number says which. */}
                <span aria-hidden="true" className="text-sm font-semibold text-muted">
                  {n}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                {t(`step${n}Body`)}
              </p>
            </li>
          );
        })}
      </ol>

      <p className="mt-8 border-l-2 border-brand pl-4 text-sm text-muted">
        {t("note")}
      </p>
    </Section>
  );
}
