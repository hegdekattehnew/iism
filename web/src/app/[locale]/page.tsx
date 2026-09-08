import { setRequestLocale } from "next-intl/server";

import { Audiences } from "@/components/Audiences";
import { BrowsePanels } from "@/components/BrowsePanels";
import { CtaBand } from "@/components/CtaBand";
import { HowItWorks } from "@/components/HowItWorks";
import { StatsBand } from "@/components/StatsBand";
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
      <StatsBand />
      <HowItWorks />
      <Audiences />
      <BrowsePanels />
      <CtaBand />
    </>
  );
}
