import { setRequestLocale } from "next-intl/server";

import { CandidateShortlist } from "@/components/employer/CandidateShortlist";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string; org: string; job: string }>;
}) {
  const { locale, org, job } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-12 sm:py-16">
      <CandidateShortlist orgSlug={org} jobSlug={job} />
    </div>
  );
}
