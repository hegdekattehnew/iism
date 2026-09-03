import { setRequestLocale } from "next-intl/server";

import { Audiences } from "@/components/Audiences";
import { BrowsePanels } from "@/components/BrowsePanels";
import { CtaBand } from "@/components/CtaBand";
import { DevPanel } from "@/components/DevPanel";
import { HowItWorks } from "@/components/HowItWorks";
import { Hero } from "@/components/Hero";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <>
      <Hero />
      <HowItWorks />
      <Audiences />
      <BrowsePanels />
      <CtaBand />
      {/* Sprint 1 verification, deliberately last and visually separated. */}
      <DevPanel />
    </>
  );
}
