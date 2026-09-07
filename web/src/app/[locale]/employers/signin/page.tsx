import { getTranslations, setRequestLocale } from "next-intl/server";

import { OrgSignInForm } from "@/components/employer/OrgSignInForm";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("orgAuth");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-16 sm:py-24">
      <h1 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
        {t("title")}
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-center text-base text-muted">
        {t("subtitle")}
      </p>
      <div className="mt-10">
        <OrgSignInForm />
      </div>
    </div>
  );
}
