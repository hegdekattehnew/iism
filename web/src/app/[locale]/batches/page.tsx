import { getTranslations, setRequestLocale } from "next-intl/server";

import { BatchBrowser } from "@/components/BatchBrowser";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ course?: string }>;
}) {
  const { locale } = await params;
  const { course } = await searchParams;
  setRequestLocale(locale);
  const t = await getTranslations("publicBatches");
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight">{t("heading")}</h1>
      <p className="mt-2 text-muted">{t("subheading")}</p>
      <BatchBrowser course={course} />
    </div>
  );
}
