import { getTranslations, setRequestLocale } from "next-intl/server";

import { RoleChooser } from "@/components/RoleChooser";
import { Link } from "@/i18n/navigation";

/**
 * The chooser, as a page.
 *
 * The header renders on every route, so the hero's copy of this would still
 * leave an employer standing on `/jobs` with a "Get started" button that
 * assumed they wanted work -- which is exactly what it did, pointing at
 * `/signup/seeker` from every page in the product.
 *
 * Same `RoleChooser` component the homepage mounts, so the three ways in can
 * never disagree about what they offer or where they lead.
 */
export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("chooser");
  const ts = await getTranslations("signup");

  return (
    <div className="mx-auto w-full max-w-lg px-5 py-16 sm:py-24">
      <h1 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
        {t("pageTitle")}
      </h1>
      <p className="mx-auto mt-3 text-center text-base text-muted">
        {t("pageSubtitle")}
      </p>

      <div className="mt-10">
        <RoleChooser />
      </div>

      <p className="mt-8 text-center text-sm text-muted">
        {ts("haveAccount")}{" "}
        <Link
          href="/signin"
          className="font-medium text-brand underline-offset-4 hover:underline"
        >
          {ts("signInInstead")}
        </Link>
      </p>
    </div>
  );
}
