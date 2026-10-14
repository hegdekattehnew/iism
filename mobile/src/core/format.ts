/**
 * Numbers and dates, **without `Intl`**.
 *
 * The web uses `Intl.NumberFormat("en-IN")` and `format.dateTime`. On a phone the JavaScript engine
 * (Hermes) implements a subset of `Intl`, differently on each platform, and nothing here can check it
 * on a device. Both of these are small, closed problems, so they are plain functions that behave the
 * same on every engine and run in Node tests:
 *
 * - **Indian digit grouping**: the last three digits, then pairs (2,38,370 and 1,00,00,000), for
 *   Hindi and Indian English alike (the web's `formatCount`, Sprint 50.5).
 * - **A calendar date**: a course's `starts_on` is a *date*, not an instant, so it has no timezone and
 *   must not drift by one across midnight (the web's `timeZone: "UTC"`, Sprint 58). It is read from
 *   its `YYYY-MM-DD` text and never through `new Date`.
 *
 * No React Native import: this file is tested in Node.
 */

/** `238370` -> `"2,38,370"`; a negative keeps its sign; a fraction is rounded away (rupees). */
export function formatInr(value: number): string {
  if (!Number.isFinite(value)) return "";
  const rounded = Math.round(Math.abs(value));
  const digits = String(rounded);
  const sign = value < 0 && rounded > 0 ? "-" : "";
  if (digits.length <= 3) return sign + digits;
  const head = digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",");
  return `${sign}${head},${digits.slice(-3)}`;
}

export type MonthStyle = "short" | "long";
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/;

/**
 * `"2026-10-14"` -> `"14 Oct 2026"` (`short`) or `"14 October 2026"` (`long`). `monthName` is given
 * the zero-based month and the style, so the words come from the message catalogue and this file
 * knows no language. Anything that is not a real date returns `null`, never a wrong one.
 */
export function formatDate(
  iso: string,
  monthName: (month: number, style: MonthStyle) => string,
  style: MonthStyle = "short",
): string | null {
  const match = ISO_DATE.exec(iso);
  if (!match) return null;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  if (month < 1 || month > 12 || day < 1 || day > daysIn(year, month)) return null;
  return `${day} ${monthName(month - 1, style)} ${year}`;
}

function daysIn(year: number, month: number): number {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}
