import { setRequestLocale } from "next-intl/server";

import { AudiencePage } from "@/components/AudiencePage";
import { AwardIcon, BuildingIcon, UsersIcon } from "@/components/ui/icons";

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
      // A standard not a keyword, who is nearly there, what the market cannot supply.
      icons={[<AwardIcon key="one" />, <UsersIcon key="two" />, <BuildingIcon key="three" />]}
      showStats={true}
      primaryHref="/signup/employer"
      secondaryHref="/employers/demo"
    />
  );
}
