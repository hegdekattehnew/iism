import { getTranslations, setRequestLocale } from "next-intl/server";

import { OperatorOnly } from "@/components/ops/OperatorOnly";
import { VerificationQueue } from "@/components/ops/VerificationQueue";

/**
 * The back office (ADR-042).
 *
 * Deliberately **not** guarded by environment, unlike `/status`: verifying an
 * organisation is a production activity, and the guard here is authority
 * rather than a build flag. Linked from nowhere -- an operator is told the
 * address -- and in `sw.js`'s DENY list, so none of it is ever cached.
 */
export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("ops");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-16">
      <OperatorOnly>
        <h1 className="text-3xl font-bold tracking-tight">{t("queueTitle")}</h1>
        <p className="mt-2 text-muted">{t("queueSubtitle")}</p>
        <VerificationQueue />
      </OperatorOnly>
    </div>
  );
}
