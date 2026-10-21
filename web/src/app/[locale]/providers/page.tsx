import { setRequestLocale } from "next-intl/server";

import { AudiencePage } from "@/components/AudiencePage";
import { AwardIcon, NavigationIcon, TargetIcon } from "@/components/ui/icons";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AudiencePage
      namespace="providersPage"
      points={["one", "two", "three"]}
      // Recommended by gap, anchored to the framework, entry routes from the source.
      icons={[<TargetIcon key="one" />, <AwardIcon key="two" />, <NavigationIcon key="three" />]}
      showStats={true}
      primaryHref="/signup/provider"
      secondaryHref="/courses"
    />
  );
}
