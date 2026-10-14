import { useColorScheme } from "react-native";

import { dark, light, type Colours } from "./tokens";

/**
 * The colours for the phone's current appearance. One rule, carried over from the web: **no screen
 * names a colour**. Every colour is a token from `tokens.ts`, which is generated from the web's
 * `globals.css`, so a colour cannot exist for one theme and be missing in the other.
 */
export function useColours(): Colours {
  return useColorScheme() === "dark" ? dark : light;
}

/** Spacing and type on one scale, so a screen never invents a number. */
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 6, md: 10, lg: 16 } as const;
export const text = { small: 13, body: 16, lead: 18, title: 24 } as const;
/** The smallest touch target either platform's guidelines allow (48 dp / 44 pt). */
export const MIN_TOUCH = 48;
