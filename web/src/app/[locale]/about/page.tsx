import { setRequestLocale } from "next-intl/server";

import { AudiencePage } from "@/components/AudiencePage";
import { FrameworkBand } from "@/components/FrameworkBand";
import { BookOpenIcon, GlobeIcon, TargetIcon } from "@/components/ui/icons";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <>
      <AudiencePage
        namespace="aboutPage"
        points={["one", "two", "three"]}
        // One vocabulary, scores you can interrogate, a low-end phone.
        icons={[<BookOpenIcon key="one" />, <TargetIcon key="two" />, <GlobeIcon key="three" />]}
        primaryHref="/skills"
        secondaryHref="/jobs"
      />
      {/* The framework figures (Sprint 70): the homepage's second band, moved to where the reader
          who wants the depth of the product looks. */}
      <FrameworkBand />
    </>
  );
}
