import { getTranslations, setRequestLocale } from "next-intl/server";

import { ContactForm } from "@/components/ContactForm";
import { Link } from "@/i18n/navigation";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("contactPage");
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-12 sm:py-16">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-4 text-base leading-relaxed">{t("intro")}</p>
      <p className="mt-2 text-sm">
        <Link
          href="/grievance"
          className="text-brand underline underline-offset-4 hover:text-brand-strong"
        >
          {t("grievanceLink")}
        </Link>
      </p>
      <div className="mt-8">
        <ContactForm />
      </div>
    </div>
  );
}
