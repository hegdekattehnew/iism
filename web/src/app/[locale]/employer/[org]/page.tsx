import { getTranslations, setRequestLocale } from "next-intl/server";

import { EmployerWorkspace } from "@/components/employer/EmployerWorkspace";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string }>;
}) {
  const { locale, org } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("employerWorkspace");

  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        {t("title")}
      </h1>
      <p className="mt-2 max-w-2xl text-base text-muted">{t("subtitle")}</p>
      <div className="mt-8">
        <EmployerWorkspace orgSlug={org} />
      </div>
    </div>
  );
}
