import { setRequestLocale } from "next-intl/server";

import { AudiencePage } from "@/components/AudiencePage";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AudiencePage
      namespace="aboutPage"
      points={["one", "two", "three"]}
      primaryHref="/skills"
      secondaryHref="/jobs"
    />
  );
}
