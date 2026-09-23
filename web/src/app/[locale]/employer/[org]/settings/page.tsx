import { setRequestLocale } from "next-intl/server";

import { DeleteOrganisation } from "@/components/employer/DeleteOrganisation";
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
      {/* Owner only; renders nothing for anybody else, because the preview
          it depends on is owner-gated. */}
      <DeleteOrganisation orgSlug={org} />
    </div>
  );
}
