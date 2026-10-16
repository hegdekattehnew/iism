import { getTranslations, setRequestLocale } from "next-intl/server";

import { AdminNav } from "@/components/ops/AdminNav";
import { ReferencePanels } from "@/components/ops/AdminPanels";
import { sectionId } from "@/components/ops/admin-sections";
import { GrievanceQueue } from "@/components/ops/GrievanceQueue";
import { ReportQueue } from "@/components/ops/ReportQueue";
import { OperatorDashboard } from "@/components/ops/OperatorDashboard";
import { OperatorOnly } from "@/components/ops/OperatorOnly";
import { VerificationQueue } from "@/components/ops/VerificationQueue";

/**
 * The back office (ADR-042).
 *
 * Deliberately **not** guarded by environment, unlike `/status`: verifying an
 * organisation is a production activity, and the guard here is authority
 * rather than a build flag. Linked from nowhere -- an operator is told the
 * address -- and in `sw.js`'s DENY list, so none of it is ever cached.
 *
 * Sprint 73 (UI-16): it was one scroll of 31 screens. The three queues an operator works every day
 * come first and stay open; the four reference panels (programme outcomes, the district skill gap,
 * role aliases, enrolment) fold away and load when opened; `AdminNav` jumps between all of them.
 * The section ids come from `admin-sections.ts`, which the nav reads too.
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
        <AdminNav />
        <section id={sectionId("overview")} className="scroll-mt-32">
          <OperatorDashboard />
        </section>
        <section id={sectionId("verification")} className="mt-10 scroll-mt-32">
          <h1 className="text-3xl font-bold tracking-tight">{t("queueTitle")}</h1>
          <p className="mt-2 text-muted">{t("queueSubtitle")}</p>
          <VerificationQueue />
        </section>
        <section id={sectionId("grievances")} className="mt-12 scroll-mt-32">
          <GrievanceQueue />
        </section>
        <section id={sectionId("reports")} className="mt-12 scroll-mt-32">
          <ReportQueue />
        </section>
        <div className="mt-12">
          <ReferencePanels />
        </div>
      </OperatorOnly>
    </div>
  );
}
