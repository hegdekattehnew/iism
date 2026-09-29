import { getTranslations, setRequestLocale } from "next-intl/server";

import { InterestList } from "@/components/InterestList";
import { SeekerOnly } from "@/components/SeekerOnly";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("courseInterest");
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <SeekerOnly>
        <h1 className="text-3xl font-bold tracking-tight">{t("pageTitle")}</h1>
        <p className="mt-2 text-muted">{t("pageSubtitle")}</p>
        <InterestList />
      </SeekerOnly>
    </div>
  );
}
