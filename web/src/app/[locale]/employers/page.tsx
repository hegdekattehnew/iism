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
      namespace="employersPage"
      points={["one", "two", "three"]}
      showStats={true}
      primaryHref="/employers/demo"
      secondaryHref="/jobs"
    />
  );
}
