import { getTranslations, setRequestLocale } from "next-intl/server";

import { CourseBrowser } from "@/components/CourseBrowser";

export default async function CoursesPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ skill?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const { skill } = await searchParams;
  const t = await getTranslations("coursesPage");

  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-2 max-w-3xl text-base text-muted">{t("subtitle")}</p>
      <div className="mt-8">
        <CourseBrowser initialSkill={skill ?? ""} />
      </div>
    </div>
  );
}
