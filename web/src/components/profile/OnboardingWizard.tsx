"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { AboutSection } from "@/components/profile/AboutSection";
import { SectionEditor, useSectionDefs } from "@/components/profile/SectionEditor";
import { SkillsSection } from "@/components/profile/SkillsSection";
import { TagSection } from "@/components/profile/TagSection";
import { Button } from "@/components/ui";
import { type Profile, useProfileMutations } from "@/lib/profile";

const TOTAL = 5;

/**
 * First-run guided setup. Each step writes immediately rather than collecting
 * everything and saving at the end, so abandoning halfway still leaves the
 * profile better than it was.
 */
export function OnboardingWizard({ profile }: { profile: Profile | null }) {
  const t = useTranslations("profilePage.wizard");
  const f = useTranslations("profilePage.fields");
  const { finishOnboarding } = useProfileMutations();
  const defs = useSectionDefs(profile);
  const [step, setStep] = useState(1);

  const byName = (name: string) => defs.find((d) => d.collection === name)!;

  const body = () => {
    switch (step) {
      case 1:
        return <AboutSection profile={profile} />;
      case 2:
        return (
          <div className="space-y-6">
            <TagSection
              collection="preferred_roles"
              title={f("roleTitleWanted")}
              entries={(profile?.preferred_roles ?? []) as never[]}
              label={f("roleTitleWanted")}
              toBody={(a) => ({ title: a })}
              render={(e) => e.title as string}
            />
            <TagSection
              collection="preferred_locations"
              title={f("state")}
              entries={(profile?.preferred_locations ?? []) as never[]}
              label={f("state")}
              secondLabel={f("district")}
              toSecond
              toBody={(a, b) => ({ state: a, district: b || null })}
              render={(e) =>
                [e.district, e.state].filter(Boolean).join(", ")
              }
            />
          </div>
        );
      case 3:
        return <SkillsSection profile={profile} />;
      case 4: {
        const exp = byName("experiences");
        const edu = byName("educations");
        return (
          <div className="space-y-6">
            <SectionEditor {...exp} />
            <SectionEditor {...edu} />
          </div>
        );
      }
      default: {
        const lang = byName("languages");
        return <SectionEditor {...lang} />;
      }
    }
  };

  const label = (["s1", "s2", "s3", "s4", "s5"] as const)[step - 1];

  return (
    <div>
      <div className="mb-6">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {t("step", { n: step, total: TOTAL })}
          </p>
          <button
            type="button"
            onClick={() => finishOnboarding.mutate()}
            className="text-xs text-muted hover:text-foreground hover:underline"
          >
            {t("skip")}
          </button>
        </div>
        <div className="mt-2 flex gap-1.5" aria-hidden>
          {Array.from({ length: TOTAL }, (_, i) => (
            <span
              key={i}
              className={`h-1.5 flex-1 rounded-full ${
                i < step ? "bg-brand" : "bg-surface-muted"
              }`}
            />
          ))}
        </div>
        <h2 className="mt-4 text-xl font-bold tracking-tight">{t(label)}</h2>
        <p className="mt-1 text-sm text-muted">{t("subtitle")}</p>
      </div>

      {body()}

      <div className="mt-8 flex items-center justify-between gap-3 border-t border-border-token pt-6">
        <Button
          variant="secondary"
          onClick={() => setStep((s) => Math.max(1, s - 1))}
          disabled={step === 1}
        >
          {t("back")}
        </Button>
        {step < TOTAL ? (
          <Button onClick={() => setStep((s) => s + 1)}>{t("next")}</Button>
        ) : (
          <Button onClick={() => finishOnboarding.mutate()} disabled={finishOnboarding.isPending}>
            {t("finish")}
          </Button>
        )}
      </div>
    </div>
  );
}
