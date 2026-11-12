import { getTranslations, setRequestLocale } from "next-intl/server";

import { BatchPage } from "@/components/BatchPage";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("publicBatches");
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight">{t("details")}</h1>
      <BatchPage id={id} />
    </div>
  );
}
