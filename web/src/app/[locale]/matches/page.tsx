import { getTranslations, setRequestLocale } from "next-intl/server";

import { MatchBrowser } from "@/components/MatchBrowser";

export default async function MatchesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("matchesPage");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-2 text-base text-muted">{t("subtitle")}</p>
      <div className="mt-8">
        <MatchBrowser />
      </div>
    </div>
  );
}
