import { setRequestLocale } from "next-intl/server";

import { ProviderInbox } from "@/components/employer/ProviderInbox";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string; course: string }>;
}) {
  const { locale, org, course } = await params;
  setRequestLocale(locale);
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <ProviderInbox org={org} courseSlug={course} />
    </div>
  );
}
