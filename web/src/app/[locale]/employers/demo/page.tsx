import { getTranslations, setRequestLocale } from "next-intl/server";

import { EmployerConsole } from "@/components/employer/EmployerConsole";

export default async function EmployerDemoPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("employerConsole");

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        {t("title")}
      </h1>
      <p className="mt-2 max-w-2xl text-base text-muted">{t("subtitle")}</p>
      <div className="mt-8">
        <EmployerConsole />
      </div>
    </div>
  );
}
