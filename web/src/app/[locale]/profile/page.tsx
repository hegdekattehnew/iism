import { getTranslations, setRequestLocale } from "next-intl/server";

import { ProfileEditor } from "@/components/ProfileEditor";
import { ReturningNotice } from "@/components/ReturningNotice";
import { SeekerOnly } from "@/components/SeekerOnly";
import { WorkspaceIdentity } from "@/components/WorkspaceIdentity";

export default async function ProfilePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("profilePage");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <ReturningNotice />
      <SeekerOnly>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            {t("title")}
          </h1>
          <p className="mt-2 text-base text-muted">{t("subtitle")}</p>
          <WorkspaceIdentity sibling="matches" />
          <div className="mt-8">
            <ProfileEditor />
          </div>
      </SeekerOnly>
    </div>
  );
}
