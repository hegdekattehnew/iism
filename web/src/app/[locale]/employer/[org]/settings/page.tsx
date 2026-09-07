import { setRequestLocale } from "next-intl/server";

import { OrgSettings } from "@/components/employer/OrgSettings";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string }>;
}) {
  const { locale, org } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <OrgSettings orgSlug={org} />
    </div>
  );
}
