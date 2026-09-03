"use client";

import { useTranslations } from "next-intl";

export function CompletenessMeter({
  percent,
  missing,
}: {
  percent: number;
  missing: string[];
}) {
  const t = useTranslations("profilePage");
  const tone =
    percent >= 80 ? "bg-emerald-500" : percent >= 40 ? "bg-brand" : "bg-amber-500";

  return (
    <div className="rounded-xl border border-border-token bg-surface p-5">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium">{t("completeness", { percent })}</p>
        {/* Naming the single most valuable next step beats a bare percentage. */}
        {missing.length > 0 && (
          <p className="text-xs text-muted">
            {t("completeNext", { what: t(`field.${missing[0]}`) })}
          </p>
        )}
      </div>
      <div
        className="mt-3 h-2 w-full overflow-hidden rounded-full bg-surface-muted"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${tone}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
