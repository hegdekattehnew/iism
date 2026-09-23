import { setRequestLocale } from "next-intl/server";

import { OperatorOnly } from "@/components/ops/OperatorOnly";
import { OrganisationReview } from "@/components/ops/OrganisationReview";
import { Link } from "@/i18n/navigation";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <OperatorOnly>
        <Link href="/admin" className="text-sm text-muted underline-offset-4 hover:underline">
          &larr; /admin
        </Link>
        <OrganisationReview slug={slug} />
      </OperatorOnly>
    </div>
  );
}
