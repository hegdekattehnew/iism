import { getTranslations, setRequestLocale } from "next-intl/server";

import { NotificationsPage } from "@/components/NotificationsPage";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("notificationsPage");
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
      <p className="mt-2 text-muted">{t("subtitle")}</p>
      <div className="mt-6">
        <NotificationsPage />
      </div>
    </div>
  );
}
