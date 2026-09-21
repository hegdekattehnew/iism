"use client";

import { useTranslations } from "next-intl";

import { Progress } from "@/components/ui";

/**
 * The score, drawn.
 *
 * **Every number here is a field of `MatchOut`.** Nothing on this screen is
 * derived, averaged or rounded into a new figure, because the moment a picture
 * computes its own number it can disagree with the score it claims to explain —
 * and then the explanation explains nothing.
 *
 * The one arithmetic step is `required − shortfall`, which is the identity the
 * scorer used to produce `shortfall` in the first place, run backwards.
 */

export function CoverageBar({
  coverage,
  missingMandatory,
  capped,
}: {
  coverage: number;
  missingMandatory: number;
  capped: boolean;
}) {
  const t = useTranslations("matchViz");
  const pct = Math.round(coverage * 100);

  return (
    <div>
      <Progress
        value={pct}
        label={t("coverageLabel", { percent: pct })}
        indicatorClassName={missingMandatory > 0 ? "bg-amber-500" : "bg-brand"}
      />
      <p className="mt-1.5 text-xs text-muted">
        {t("coverageWeighted", { percent: pct })}
        {capped && (
          <span className="ml-2 text-amber-700 dark:text-amber-400">
            {t("cappedBy", { count: missingMandatory })}
          </span>
        )}
      </p>
    </div>
  );
}

/**
 * Where the candidate stands on the NSQF scale, rather than how many levels
 * short they are. "Level 3 against a floor of 5" is a fact somebody can act on;
 * "two levels short" is a number they have to translate first.
 */
export function LevelScale({
  required,
  shortfall,
}: {
  required: number;
  shortfall?: number | null;
}) {
  const t = useTranslations("matchViz");
  // The identity the scorer used, reversed — not a second opinion about level.
  const attained = shortfall == null ? required : required - shortfall;
  const steps = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">
        {t("levelHeading")}
      </p>
      <div
        className="mt-2 flex gap-1"
        role="img"
        aria-label={t("levelLabel", { attained, required })}
      >
        {steps.map((step) => {
          const held = step <= attained;
          const beyond = step > attained && step <= required;
          return (
            <span
              key={step}
              className={`h-6 flex-1 rounded-sm text-center text-[10px] leading-6 ${
                held
                  ? "bg-brand text-[var(--brand-contrast)]"
                  : beyond
                    ? "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100"
                    : "bg-surface-muted text-muted"
              }`}
            >
              {step}
            </span>
          );
        })}
      </div>
      <p className="mt-1.5 text-xs text-muted">
        {shortfall == null
          ? t("levelMet", { required })
          : t("levelShort", { attained, required })}
      </p>
    </div>
  );
}
