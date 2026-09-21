import { setRequestLocale } from "next-intl/server";

import { SignInForm } from "@/components/SignInForm";

export default async function SignInPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:py-24">
      <SignInForm />
    </div>
  );
}
