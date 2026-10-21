"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { Badge, Button } from "@/components/ui";
import { Field, Input } from "@/components/ui/field";
import { Link } from "@/i18n/navigation";
import type { components } from "@/lib/api-schema";
import {
  BUDGET_MAX,
  setCourseBudget,
  useCourseBudget,
} from "@/lib/course-budget";

type Suggestion = components["schemas"]["CourseSuggestionOut"];

/**
 * A course that closes part of a gap, and whether the person can take it (Sprint 58, BL-14.6).
 *
 * One list for every screen that suggests a course -- matches, "why not me", career ladders and the
 * employer's sponsor panel -- because the four hand-rolled copies each showed a title and a number
 * of hours and nothing a person needs to act: where, when, what it costs and whether there is room.
 *
 * **Nothing is hidden.** A started, full, faraway or over-budget course is labelled, not removed:
 * it may be the only one that teaches the missing standard, and many intakes are rolling. The order
 * is the server's (`matching.attendance.rank_key`); this renders it and computes nothing.
 *
 * `forPerson` is false for the employer's sponsor panel, which knows no candidate: there "in your
 * district" would be a claim about nobody, so only the course's own facts are shown.
 */
export function SuggestedCourses({
  courses,
  forPerson = true,
  onOpen,
}: {
  courses: Suggestion[];
  forPerson?: boolean;
  onOpen?: (slug: string) => void;
}) {
  const t = useTranslations("suggestedCourses");
  const format = useFormatter();
  // A start date is a calendar day, not a moment: read and formatted in UTC so it is the same day
  // in every time zone (parsed as local midnight it slips a day west of Greenwich).
  const day = (iso: string) =>
    format.dateTime(new Date(`${iso}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });

  return (
    <ul className="space-y-2">
      {courses.map((c) => {
        const place =
          c.mode === "online"
            ? null
            : [c.location_district, c.location_state]
                .filter(Boolean)
                .join(", ") || t("placeNotStated");
        const fee =
          c.fee_inr == null || c.fee_inr === 0
            ? t("free")
            : t("fee", { amount: format.number(c.fee_inr) });
        const when = c.starts_on
          ? t(c.started ? "startedOn" : "startsOn", { date: day(c.starts_on) })
          : t("startNotStated");
        const facts = [
          t(`mode.${c.mode}`),
          place,
          when,
          fee,
          c.duration_hours != null
            ? t("hours", { hours: c.duration_hours })
            : null,
          c.seats_left != null && !c.full
            ? t("seatsLeft", { count: c.seats_left })
            : null,
        ].filter((x): x is string => Boolean(x));

        return (
          <li
            key={c.slug}
            className="rounded-lg border border-border-token p-3"
          >
            <Link
              href={`/courses/${c.slug}`}
              onClick={onOpen ? () => onOpen(c.slug) : undefined}
              className="text-sm font-semibold underline-offset-4 hover:underline"
            >
              {c.title}
            </Link>
            <p className="mt-1 text-xs text-muted">{facts.join(" · ")}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {forPerson && c.reach === "online" && (
                <Badge tone="good">{t("reach.online")}</Badge>
              )}
              {forPerson && c.reach === "district" && (
                <Badge tone="good">{t("reach.district")}</Badge>
              )}
              {forPerson && c.reach === "state" && (
                <Badge tone="good">{t("reach.state")}</Badge>
              )}
              {forPerson && c.reach === "elsewhere" && (
                <Badge tone="warn">{t("reach.elsewhere")}</Badge>
              )}
              {c.started && <Badge tone="warn">{t("started")}</Badge>}
              {c.full && <Badge tone="warn">{t("full")}</Badge>}
              {forPerson && c.within_budget === false && (
                <Badge tone="warn">{t("overBudget")}</Badge>
              )}
            </div>
            <p className="mt-1.5 text-xs text-brand">
              {t("closesGap", { closed: c.closes_count, total: c.gap_size })}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * "What would you pay?" -- one number, applied when the person leaves the field or presses Enter
 * (not on every keystroke: each change asks the server for a new order). Remembered in this browser
 * only; see `lib/course-budget.ts`.
 */
export function CourseBudgetControl() {
  const t = useTranslations("suggestedCourses");
  const budget = useCourseBudget();
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? (budget === null ? "" : String(budget));

  const apply = () => {
    if (draft === null) return;
    const trimmed = draft.trim();
    if (trimmed === "") setCourseBudget(null);
    else {
      const n = Number(trimmed);
      if (Number.isInteger(n) && n >= 0 && n <= BUDGET_MAX) setCourseBudget(n);
    }
    setDraft(null);
  };

  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <Field label={t("budgetLabel")}>
        <Input
          type="number"
          name="budget_inr"
          inputMode="numeric"
          min={0}
          max={10000000}
          step={1}
          value={shown}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={apply}
          className="w-36"
        />
      </Field>
      {budget !== null && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setDraft(null);
            setCourseBudget(null);
          }}
        >
          {t("budgetClear")}
        </Button>
      )}
    </form>
  );
}
