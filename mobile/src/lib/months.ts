import { useTranslations } from "use-intl";

import { formatInstantDate } from "../core/format";
import type { MonthName } from "../core/labels";

/** Month names from the catalogue, in the language on screen: `core/format.ts` knows no language. */
export function useMonthName(): MonthName {
  const t = useTranslations("mobile.months");
  return (month, style) => t(`${style}.m${month + 1}`);
}

/** A moment as the day it happened in India, in the language on screen (`null` if it is not one). */
export function useInstantDate(): (instant: string) => string | null {
  const monthName = useMonthName();
  return (instant) => formatInstantDate(instant, monthName, "short");
}
