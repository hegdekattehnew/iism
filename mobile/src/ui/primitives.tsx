import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text as NativeText,
  TextInput,
  useWindowDimensions,
  View,
  type TextInputProps,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { MAX_FONT_SCALE, MIN_TOUCH, radius, space, text, useColours } from "../theme";

/**
 * The few primitives every screen is built from. They are the phone's `ui/` library: tokens only
 * (no colour is named here), a 48 dp minimum touch target, and an accessible name and role on
 * everything that can be pressed. Not a design system; the smallest set M1 needs.
 */

/**
 * A scrolling screen. `footer` is a bar **under** the scrolling content, outside it (Sprint 69,
 * UI-08): the one action a screen exists for stays under the thumb however far the person has read.
 * It is height-capped and scrolls on its own, so a confirmation opening inside it cannot push the
 * content off a short phone.
 */
export function Screen({ children, footer }: { children: ReactNode; footer?: ReactNode }) {
  const c = useColours();
  const { height } = useWindowDimensions();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }}>
      <ScrollView
        testID="screen-content"
        contentContainerStyle={{ padding: space.xl, gap: space.lg, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
      {footer ? (
        <View
          testID="screen-footer"
          style={{
            borderTopWidth: 1,
            borderTopColor: c.border,
            backgroundColor: c.surface,
            maxHeight: height * 0.6,
          }}
        >
          <ScrollView
            contentContainerStyle={{ padding: space.md, gap: space.md }}
            keyboardShouldPersistTaps="handled"
          >
            {footer}
          </ScrollView>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

export function Text({
  children,
  variant = "body",
  tone = "foreground",
}: {
  children: ReactNode;
  variant?: keyof typeof text;
  tone?: "foreground" | "muted" | "danger";
}) {
  const c = useColours();
  const colour = tone === "foreground" ? c.foreground : tone === "muted" ? c.muted : c.dangerText;
  return (
    <NativeText
      maxFontSizeMultiplier={MAX_FONT_SCALE}
      accessibilityRole={variant === "title" ? "header" : "text"}
      style={{
        color: colour,
        fontSize: text[variant],
        fontWeight: variant === "title" ? "700" : "400",
        // Devanagari needs more line height than Latin (the web's `html[lang=hi]` rule).
        lineHeight: Math.round(text[variant] * 1.6),
      }}
    >
      {children}
    </NativeText>
  );
}

export function Button({
  label,
  accessibilityLabel,
  onPress,
  disabled = false,
  busy = false,
  variant = "primary",
  expanded,
}: {
  label: string;
  /** What a screen reader says when it needs more than the visible words ("Remove: Hand hygiene"); it must contain `label`. */
  accessibilityLabel?: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "secondary";
  /** Set on a button that shows or hides something: a screen reader says "expanded" or "collapsed". */
  expanded?: boolean;
}) {
  const c = useColours();
  const inactive = disabled || busy;
  const primary = variant === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: inactive, busy, ...(expanded === undefined ? {} : { expanded }) }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: MIN_TOUCH,
        borderRadius: radius.md,
        paddingHorizontal: space.lg,
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "row",
        gap: space.sm,
        opacity: inactive ? 0.5 : pressed ? 0.85 : 1,
        backgroundColor: primary ? c.brand : c.surface,
        borderWidth: primary ? 0 : StyleSheet.hairlineWidth * 2,
        borderColor: c.inputBorder,
      })}
    >
      {busy && <ActivityIndicator color={primary ? c.brandContrast : c.brand} />}
      <NativeText
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        style={{
          color: primary ? c.brandContrast : c.brand,
          fontSize: text.body,
          fontWeight: "600",
        }}
      >
        {label}
      </NativeText>
    </Pressable>
  );
}

export function TextField({
  label,
  ...input
}: { label: string } & Omit<TextInputProps, "style" | "accessibilityLabel">) {
  const c = useColours();
  return (
    <View style={{ gap: space.xs }}>
      <NativeText
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        style={{ color: c.foreground, fontSize: text.small, fontWeight: "600" }}
      >
        {label}
      </NativeText>
      <TextInput
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        accessibilityLabel={label}
        placeholderTextColor={c.muted}
        style={{
          minHeight: MIN_TOUCH,
          borderRadius: radius.md,
          borderWidth: 1,
          // Not `border`: a control's edge must be findable (WCAG 1.4.11), as on the web.
          borderColor: c.inputBorder,
          backgroundColor: c.surface,
          color: c.foreground,
          paddingHorizontal: space.md,
          fontSize: text.body,
        }}
        {...input}
      />
    </View>
  );
}

export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "danger" | "warning";
}) {
  const c = useColours();
  const palette = {
    info: [c.infoSurface, c.infoBorder, c.infoText],
    danger: [c.dangerSurface, c.dangerBorder, c.dangerText],
    warning: [c.warningSurface, c.warningBorder, c.warningText],
  }[tone];
  return (
    <View
      // One focusable item, so a screen reader reads the notice whole and an alert is announced.
      accessible
      accessibilityRole={tone === "danger" ? "alert" : undefined}
      accessibilityLiveRegion={tone === "danger" ? "polite" : "none"}
      style={{
        backgroundColor: palette[0],
        borderColor: palette[1],
        borderWidth: 1,
        borderRadius: radius.md,
        padding: space.md,
      }}
    >
      <NativeText
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        style={{ color: palette[2], fontSize: text.body, lineHeight: 26 }}
      >
        {children}
      </NativeText>
    </View>
  );
}
