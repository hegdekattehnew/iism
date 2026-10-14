import { useTranslations } from "use-intl";

import type { MonthName } from "../core/labels";

/** Month names from the catalogue, in the language on screen: `core/format.ts` knows no language. */
export function useMonthName(): MonthName {
  const t = useTranslations("mobile.months");
  return (month, style) => t(`${style}.m${month + 1}`);
}
