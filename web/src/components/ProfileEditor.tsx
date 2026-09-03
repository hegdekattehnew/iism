"use client";

import { useTranslations } from "next-intl";

import { AboutSection } from "@/components/profile/AboutSection";
import { CompletenessMeter } from "@/components/profile/CompletenessMeter";
import { OnboardingWizard } from "@/components/profile/OnboardingWizard";
import { SectionEditor, useSectionDefs } from "@/components/profile/SectionEditor";
import { SkillsSection } from "@/components/profile/SkillsSection";
import { TagSection } from "@/components/profile/TagSection";
import { ButtonLink } from "@/components/ui";
import { useIsSignedIn } from "@/lib/auth";
import { useProfile } from "@/lib/profile";

export function ProfileEditor() {
  const t = useTranslations("profilePage");
  const f = useTranslations("profilePage.fields");
  const signedIn = useIsSignedIn();
  const profile = useProfile(signedIn);
  const defs = useSectionDefs(profile.data ?? null);

  if (!signedIn) {
    return (
      <div className="rounded-xl border border-border-token bg-surface p-8 text-center">
        <p className="text-sm text-muted">{t("signInPrompt")}</p>
        <div className="mt-4">
          <ButtonLink href="/signin">{t("goToSignIn")}</ButtonLink>
        </div>
      </div>
    );
  }

  if (profile.isPending) return null;

  const data = profile.data ?? null;

  // First visit gets the guided wizard; everyone else the sectioned editor.
  if (data && !data.onboarding_completed_at) {
    return <OnboardingWizard profile={data} />;
  }

  return (
    <div className="space-y-6">
      <CompletenessMeter
        percent={data?.completeness?.percent ?? 0}
        missing={data?.completeness?.missing ?? []}
      />

      <AboutSection profile={data} />

      <TagSection
        collection="preferred_roles"
        title={f("roleTitleWanted")}
        entries={(data?.preferred_roles ?? []) as never[]}
        label={f("roleTitleWanted")}
        toBody={(a) => ({ title: a })}
        render={(e) => e.title as string}
      />
      <TagSection
        collection="preferred_locations"
        title={f("state")}
        entries={(data?.preferred_locations ?? []) as never[]}
        label={f("state")}
        secondLabel={f("district")}
        toSecond
        toBody={(a, b) => ({ state: a, district: b || null })}
        render={(e) => [e.district, e.state].filter(Boolean).join(", ")}
      />

      <SkillsSection profile={data} />

      {defs.map((d) => (
        <SectionEditor key={d.collection} {...d} />
      ))}
    </div>
  );
}
