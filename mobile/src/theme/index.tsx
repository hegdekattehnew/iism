import { useColorScheme } from "react-native";

import { dark, light, radius as radiusTokens, type as typeTokens, type Colours } from "./tokens";

/**
 * The colours for the phone's current appearance. One rule, carried over from the web: **no screen
 * names a colour**. Every colour is a token from `tokens.ts`, which is generated from the web's
 * `globals.css`, so a colour cannot exist for one theme and be missing in the other.
 */
export function useColours(): Colours {
  return useColorScheme() === "dark" ? dark : light;
}

/** Spacing on one scale (multiples of 4, the web's own spacing unit), so a screen never invents a number. */
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
/** Corners, generated from the web's `--r-*` tokens (Sprint 77), so a corner is the same on both. */
export const radius = radiusTokens;
/**
 * Type sizes, generated from the web's `--type-*` scale (Sprint 77). `small` is the step the phone
 * has always called small (13, now named `caption` on the web) and `secondary` is the web's 15 px
 * "small": the names below keep every existing screen unchanged until the phone's own stories move
 * it. A test holds every size here to a step of the shared scale.
 */
export const text = {
  small: typeTokens.caption.size,
  secondary: typeTokens.small.size,
  body: typeTokens.body.size,
  lead: typeTokens.lead.size,
  title: typeTokens.title.size,
  display: typeTokens.display.size,
} as const;
/** The line height that goes with each step, from the same scale. */
export const lineHeight = {
  small: typeTokens.caption.lineHeight,
  secondary: typeTokens.small.lineHeight,
  body: typeTokens.body.lineHeight,
  lead: typeTokens.lead.lineHeight,
  title: typeTokens.title.lineHeight,
  display: typeTokens.display.lineHeight,
} as const;
/** The smallest touch target either platform's guidelines allow (48 dp / 44 pt). */
export const MIN_TOUCH = 48;
/**
 * The most a person's system font size may enlarge our text (200%, Android's and iOS's largest
 * accessibility steps). Uncapped, a card's fixed-width badge or a tab label breaks the layout at the
 * very size somebody chose in order to read it; capped, it still doubles.
 */
export const MAX_FONT_SCALE = 2;
