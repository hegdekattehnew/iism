import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { type SignUpType, SignUpForm } from "@/components/SignUpForm";
import { SignUpTypeSwitch } from "@/components/SignUpTypeSwitch";

const TYPES = ["seeker", "employer", "provider"] as const;

export function generateStaticParams() {
  return TYPES.map((type) => ({ type }));
}

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; type: string }>;
}) {
  const { locale, type } = await params;
  setRequestLocale(locale);
  if (!TYPES.includes(type as (typeof TYPES)[number])) notFound();
  const t = await getTranslations("signup");

  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-16 sm:py-24">
      {/* All three kinds of account, from whichever one the link opened on. */}
      <SignUpTypeSwitch current={type as SignUpType} />
      <h1 className="mt-8 text-center text-3xl font-bold tracking-tight sm:text-4xl">
        {t(`${type}Title`)}
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-center text-base text-muted">
        {t(`${type}Subtitle`)}
      </p>
      <div className="mt-10">
        {/* Keyed by type. Switching reuses this route with a new param, and
            without the key React keeps the form's state -- a phone number
            typed as a job seeker would reappear in the employer's email
            field, and a code already sent would stay on screen. */}
        <SignUpForm key={type} type={type as SignUpType} />
      </div>
    </div>
  );
}
