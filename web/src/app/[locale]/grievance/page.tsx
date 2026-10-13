import { setRequestLocale } from "next-intl/server";

import { GrievanceForm } from "@/components/GrievanceForm";
import { LegalPage } from "@/components/LegalPage";

export default async function Page({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <LegalPage doc="grievance">
      <GrievanceForm />
    </LegalPage>
  );
}
