import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProviderInterestSummary } from "@/components/employer/ProviderInterestSummary";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string }>;
}) {
  const { locale, org } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("providerInbox");
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight">{t("summaryTitle")}</h1>
      <p className="mt-2 text-muted">{t("summarySubtitle")}</p>
      <ProviderInterestSummary org={org} />
    </div>
  );
}
