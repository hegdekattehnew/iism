import { getTranslations, setRequestLocale } from "next-intl/server";

import { BatchesPanel } from "@/components/employer/BatchesPanel";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string }>;
}) {
  const { locale, org } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("batches");
  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight">{t("heading")}</h1>
      <p className="mt-2 text-muted">{t("subheading")}</p>
      <BatchesPanel org={org} />
    </div>
  );
}
