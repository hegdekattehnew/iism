/**
 * What a suggested course says about itself, so a person can tell whether they can take it:
 * where, when, what it costs, how long, whether there is room, and how near it is. The wording of
 * the web's `SuggestedCourses`, as pure functions over a translator (the `suggestedCourses`
 * catalogue namespace), tested in Node.
 *
 * **Nothing is hidden.** A started, full, faraway or over-budget course is *labelled*, never
 * removed: it may be the only one that teaches the missing standard, and many intakes are rolling.
 * The order is the server's (`matching.attendance.rank_key`); this computes nothing about it.
 *
 * No React Native import.
 */

import type { components } from "../api/schema";
import { formatDate, formatInr } from "./format";
import type { MonthName, Translate } from "./labels";

export type Suggestion = components["schemas"]["CourseSuggestionOut"];

/** The plain facts, in reading order, with the ones a course does not state left out. */
export function suggestionFacts(c: Suggestion, t: Translate, monthName: MonthName): string[] {
  const place =
    c.mode === "online"
      ? null
      : [c.location_district, c.location_state].filter(Boolean).join(", ") || t("placeNotStated");
  const fee = c.fee_inr == null || c.fee_inr === 0 ? t("free") : t("fee", { amount: formatInr(c.fee_inr) });
  const date = c.starts_on ? formatDate(c.starts_on, monthName, "short") : null;
  const when = date ? t(c.started ? "startedOn" : "startsOn", { date }) : t("startNotStated");
  return [
    t(`mode.${c.mode}`),
    place,
    when,
    fee,
    c.duration_hours != null ? t("hours", { hours: c.duration_hours }) : null,
    c.seats_left != null && !c.full ? t("seatsLeft", { count: c.seats_left }) : null,
  ].filter((x): x is string => Boolean(x));
}

export type SuggestionBadge = { key: string; tone: "success" | "warning" };

/**
 * The labels beside a course. `forPerson` is false where no candidate is known (a sponsor panel),
 * where "in your district" would be a claim about nobody.
 */
export function suggestionBadges(c: Suggestion, forPerson = true): SuggestionBadge[] {
  const out: SuggestionBadge[] = [];
  if (forPerson) {
    if (c.reach === "online") out.push({ key: "reach.online", tone: "success" });
    else if (c.reach === "district") out.push({ key: "reach.district", tone: "success" });
    else if (c.reach === "state") out.push({ key: "reach.state", tone: "success" });
    else if (c.reach === "elsewhere") out.push({ key: "reach.elsewhere", tone: "warning" });
  }
  if (c.started) out.push({ key: "started", tone: "warning" });
  if (c.full) out.push({ key: "full", tone: "warning" });
  if (forPerson && c.within_budget === false) out.push({ key: "overBudget", tone: "warning" });
  return out;
}
