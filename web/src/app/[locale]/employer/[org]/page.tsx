import { setRequestLocale } from "next-intl/server";

import { OrgWorkspace } from "@/components/employer/OrgWorkspace";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string }>;
}) {
  const { locale, org } = await params;
  setRequestLocale(locale);

  // The heading lives inside OrgWorkspace, not here: it depends on the kind of
  // organisation, and only the client knows that. A server-rendered title said
  // "Post a vacancy" to training providers.
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <OrgWorkspace orgSlug={org} />
    </div>
  );
}
