import { getTranslations, setRequestLocale } from "next-intl/server";

import { ApplicationList } from "@/components/ApplicationList";
import { Notices } from "@/components/Notices";
import { SeekerOnly } from "@/components/SeekerOnly";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("applications");
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <SeekerOnly>
        <h1 className="text-3xl font-bold tracking-tight">{t("pageTitle")}</h1>
        <p className="mt-2 text-muted">{t("pageSubtitle")}</p>
        <ApplicationList />
        {/* Below the list, not above it (Sprint 60): the panel appears only once its query has
            answered and only when something is unread, so above the list it pushed an already
            shown list down by its own height -- a layout shift the browser run measured at 0.110
            the first time the seeker had an unread update. The header's "Updates" link and
            `/notifications` are how an unread notice is found; this is a convenience. */}
        <Notices />
      </SeekerOnly>
    </div>
  );
}
