import { getTranslations, setRequestLocale } from "next-intl/server";

import { SkillBrowser } from "@/components/SkillBrowser";

export default async function SkillsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  // The homepage hero posts here as ?q=…, so the search arrives pre-filled.
  const { q } = await searchParams;
  const t = await getTranslations("skillsPage");

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-2 max-w-3xl text-base text-muted">{t("subtitle")}</p>
      <div className="mt-8">
        <SkillBrowser initialQuery={q ?? ""} />
      </div>
    </div>
  );
}
