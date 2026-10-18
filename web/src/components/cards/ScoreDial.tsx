"use client";

import { useTranslations } from "next-intl";

/**
 * "87% match", in a tint that is a second way to scan and never the only one: the number says it.
 * Shared by the matches page and by a job card on a list when the person is a signed-in job seeker
 * (Sprint 84, BL-19.15, UI-04), so the same score looks the same wherever it is read.
 */
export function ScoreDial({ score, className = "" }: { score: number; className?: string }) {
  const t = useTranslations("matchesPage");
  const tone =
    score >= 75
      ? "bg-success-surface text-success-text"
      : score >= 45
        ? "bg-warning-surface text-warning-text"
        : "bg-surface-muted text-foreground";
  return (
    <span className={`shrink-0 rounded-lg px-2.5 py-1 text-sm font-semibold ${tone} ${className}`}>
      {t("matchScore", { score })}
    </span>
  );
}
