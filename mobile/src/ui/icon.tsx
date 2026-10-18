import Svg, { Path } from "react-native-svg";

import { useColours } from "../theme";
import { SHAPES, type IconName } from "./icon-shapes";

export type { IconName } from "./icon-shapes";

type Props = {
  name: IconName;
  /** Points on both axes. Defaults to the web's 20 px (`h-5 w-5`). */
  size?: number;
  /** A token colour passed in by the caller; the default is the theme's body text. */
  color?: string;
  /**
   * Gives the icon a name for a screen reader. Leave it off when the icon sits beside its word: it
   * would only repeat it, so the icon is then hidden from TalkBack and VoiceOver.
   */
  title?: string;
};

/**
 * One of the icons the web draws (Sprint 78, BL-19.7, ADR-087): the shapes are the web's own,
 * generated into `icon-shapes.ts`, drawn here with the `react-native-svg` the app already declares.
 * The stroke is `currentColor`'s counterpart: the caller's token colour, or the theme's text colour.
 */
export function Icon({ name, size = 20, color, title }: Props) {
  const colours = useColours();
  const stroke = color ?? colours.foreground;
  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      accessible={title !== undefined}
      accessibilityRole={title !== undefined ? "image" : undefined}
      accessibilityLabel={title}
      importantForAccessibility={title !== undefined ? "yes" : "no-hide-descendants"}
    >
      {SHAPES[name].map((d) => (
        <Path key={d} d={d} />
      ))}
    </Svg>
  );
}
