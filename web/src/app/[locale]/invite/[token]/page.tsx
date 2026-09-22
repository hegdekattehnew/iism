import { setRequestLocale } from "next-intl/server";

import { InvitePanel } from "@/components/InvitePanel";

/**
 * Public by design: the person holding this link may have no account at all,
 * and sending them through sign-in first would ask them to create the thing
 * the invitation is for.
 */
export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; token: string }>;
}) {
  const { locale, token } = await params;
  setRequestLocale(locale);
  return (
    <div className="mx-auto w-full max-w-lg px-5 py-12 sm:py-16">
      <InvitePanel token={token} />
    </div>
  );
}
