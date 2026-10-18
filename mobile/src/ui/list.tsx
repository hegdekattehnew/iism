import type { UseInfiniteQueryResult } from "@tanstack/react-query";
import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  Text as NativeText,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { ApiError } from "../core/errors";
import { MAX_FONT_SCALE, MIN_TOUCH, radius, space, text, useColours } from "../theme";
import { Icon, type IconName } from "./icon";
import { Button, Text } from "./primitives";

/**
 * What the list screens are made of: cards, badges, filter chips, the loading placeholder and the
 * list itself with its four states. The rules the web learned the hard way are kept here, once:
 *
 * - **A list never says "no results" before it has had an answer** (Sprint 54): while the first page
 *   is on its way there is a placeholder, and it is shaped like the rows that will replace it.
 * - **A failed first page is an error with a way to retry; a failed next page is not**: the rows the
 *   person is reading stay, and the failure is a line beneath them (never an error that replaces
 *   what they were reading).
 * - **A 404 and an outage are different words** (Sprint 20): "this does not exist" is not what to
 *   say when the server could not be reached.
 */

/**
 * A surface. `level="default"` is a card on the page; `inset` is a box inside a card (the muted
 * surface, no second edge): the web's levels (ADR-089). Never a card in a card.
 */
export function Card({
  children,
  onPress,
  label,
  level = "default",
}: {
  children: ReactNode;
  onPress?: () => void;
  label?: string;
  level?: "default" | "inset";
}) {
  const c = useColours();
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : undefined}
      accessibilityLabel={label}
      disabled={!onPress}
      onPress={onPress}
      style={({ pressed }) => ({
        borderWidth: 1,
        borderColor: c.border,
        backgroundColor: level === "inset" ? c.surfaceMuted : c.surface,
        borderRadius: level === "inset" ? radius.md : radius.lg,
        padding: space.lg,
        gap: space.sm,
        opacity: pressed ? 0.85 : 1,
      })}
    >
      {children}
    </Pressable>
  );
}

export function Badge({
  label,
  tone = "muted",
}: {
  label: string;
  tone?: "brand" | "muted" | "success" | "warning" | "danger" | "info";
}) {
  const c = useColours();
  const palette = {
    brand: [c.accentSoft, c.brand],
    muted: [c.surfaceMuted, c.muted],
    success: [c.successSurface, c.successText],
    warning: [c.warningSurface, c.warningText],
    danger: [c.dangerSurface, c.dangerText],
    info: [c.infoSurface, c.infoText],
  }[tone];
  return (
    <View
      style={{
        backgroundColor: palette[0],
        borderRadius: radius.sm,
        paddingHorizontal: space.sm,
        paddingVertical: 2,
        alignSelf: "flex-start",
      }}
    >
      <NativeText
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        style={{ color: palette[1], fontSize: text.small, fontWeight: "600" }}
      >
        {label}
      </NativeText>
    </View>
  );
}

/**
 * One place to go, as a row (Sprint 82, BL-19.14): an icon in a tinted disc, a title, a line under it
 * if there is one, and a chevron. The phone's Me tab was eight identical buttons; a row says what
 * each is before it is read. At least 56 dp tall (above the 48 dp floor, since a row is the thing a
 * thumb scans), a button to a screen reader with the **title as its name** unless a longer one is
 * given (it must contain the title: "Updates: 3 new updates"). `count` is drawn in a pill before the
 * chevron and is not read by itself, because the name already says it.
 */
export function ListRow({
  title,
  subtitle,
  icon,
  onPress,
  count,
  accessibilityLabel,
  divider = false,
}: {
  title: string;
  subtitle?: string;
  icon: IconName;
  onPress: () => void;
  /** A number to draw beside the title (unread updates). Say it in `accessibilityLabel` too. */
  count?: number;
  accessibilityLabel?: string;
  /** A hairline above this row; `RowGroup` sets it on every row but the first. */
  divider?: boolean;
}) {
  const c = useColours();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      onPress={onPress}
      style={({ pressed }) => ({
        minHeight: MIN_TOUCH + 8,
        flexDirection: "row",
        alignItems: "center",
        gap: space.md,
        paddingHorizontal: space.lg,
        paddingVertical: space.sm,
        borderTopWidth: divider ? 1 : 0,
        borderTopColor: c.border,
        backgroundColor: pressed ? c.surfaceMuted : c.surface,
      })}
    >
      <View
        importantForAccessibility="no-hide-descendants"
        style={{
          width: 36,
          height: 36,
          borderRadius: radius.md,
          backgroundColor: c.accentTint,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name={icon} size={20} color={c.accentText} />
      </View>
      <View style={{ flex: 1 }}>
        <NativeText
          maxFontSizeMultiplier={MAX_FONT_SCALE}
          style={{ color: c.foreground, fontSize: text.body, fontWeight: "600" }}
        >
          {title}
        </NativeText>
        {subtitle ? (
          <NativeText
            maxFontSizeMultiplier={MAX_FONT_SCALE}
            style={{ color: c.muted, fontSize: text.small, marginTop: 2 }}
          >
            {subtitle}
          </NativeText>
        ) : null}
      </View>
      {count ? (
        <View
          importantForAccessibility="no-hide-descendants"
          style={{
            minWidth: 24,
            height: 24,
            borderRadius: 12,
            paddingHorizontal: space.sm,
            backgroundColor: c.brand,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <NativeText
            maxFontSizeMultiplier={MAX_FONT_SCALE}
            style={{ color: c.brandContrast, fontSize: text.small, fontWeight: "700" }}
          >
            {count > 99 ? "99+" : String(count)}
          </NativeText>
        </View>
      ) : null}
      <Icon name="ChevronRight" size={20} color={c.muted} />
    </Pressable>
  );
}

/** Rows in one rounded box with a hairline between them. Children are `ListRow`s. */
export function RowGroup({ children }: { children: ReactNode }) {
  const c = useColours();
  const rows = Children.toArray(children).filter(isValidElement) as ReactElement<{ divider?: boolean }>[];
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: c.border,
        borderRadius: radius.lg,
        overflow: "hidden",
        backgroundColor: c.surface,
      }}
    >
      {rows.map((row, i) => cloneElement(row, { divider: i > 0 }))}
    </View>
  );
}

/**
 * The heading of a section: an icon in a tinted disc, the title (a heading to a screen reader) and a
 * line under it. Used by `Panel` and, bare, above a `RowGroup` (Sprint 83, BL-19.23).
 */
export function PanelHeader({ icon, title, subtitle }: { icon: IconName; title: string; subtitle?: string }) {
  const c = useColours();
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: space.md }}>
      <View
        importantForAccessibility="no-hide-descendants"
        style={{
          width: 36,
          height: 36,
          borderRadius: radius.md,
          backgroundColor: c.accentTint,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name={icon} size={20} color={c.accentText} />
      </View>
      <View style={{ flex: 1 }}>
        <NativeText
          accessibilityRole="header"
          maxFontSizeMultiplier={MAX_FONT_SCALE}
          style={{ color: c.foreground, fontSize: text.lead, fontWeight: "600", lineHeight: 28 }}
        >
          {title}
        </NativeText>
        {subtitle ? (
          <NativeText
            maxFontSizeMultiplier={MAX_FONT_SCALE}
            style={{ color: c.muted, fontSize: text.secondary, marginTop: 2, lineHeight: 22 }}
          >
            {subtitle}
          </NativeText>
        ) : null}
      </View>
    </View>
  );
}

/**
 * A section of a screen as one surface, with its own heading and (when it has one) its own Save: the
 * profile is a stack of these, not one long form. Not pressable. Anything pressable inside it that is
 * itself a card is an `inset` one: never a card in a card.
 */
export function Panel({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: IconName;
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  const c = useColours();
  return (
    <View
      style={{
        borderWidth: 1,
        borderColor: c.border,
        backgroundColor: c.surface,
        borderRadius: radius.lg,
        padding: space.lg,
        gap: space.md,
      }}
    >
      <PanelHeader icon={icon} title={title} subtitle={subtitle} />
      {children}
    </View>
  );
}

export function BadgeRow({ children }: { children: ReactNode }) {
  return <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>{children}</View>;
}

export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  const c = useColours();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected }}
      onPress={onPress}
      style={{
        minHeight: MIN_TOUCH,
        justifyContent: "center",
        borderRadius: radius.lg,
        paddingHorizontal: space.md,
        borderWidth: 1,
        borderColor: selected ? c.brand : c.inputBorder,
        backgroundColor: selected ? c.brand : c.surface,
      }}
    >
      <NativeText
        maxFontSizeMultiplier={MAX_FONT_SCALE}
        style={{ color: selected ? c.brandContrast : c.foreground, fontSize: text.small, fontWeight: "600" }}
      >
        {label}
      </NativeText>
    </Pressable>
  );
}

export function ChipRow({ children }: { children: ReactNode }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
      {children}
    </ScrollView>
  );
}

export function SearchBox({
  value,
  onChangeText,
  placeholder,
  onSubmit,
}: {
  value: string;
  onChangeText: (text: string) => void;
  placeholder: string;
  onSubmit?: () => void;
}) {
  const c = useColours();
  return (
    <TextInput
      accessibilityLabel={placeholder}
      maxFontSizeMultiplier={MAX_FONT_SCALE}
      placeholder={placeholder}
      placeholderTextColor={c.muted}
      value={value}
      onChangeText={onChangeText}
      onSubmitEditing={onSubmit}
      returnKeyType="search"
      autoCorrect={false}
      style={{
        minHeight: MIN_TOUCH,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: c.inputBorder,
        backgroundColor: c.surface,
        color: c.foreground,
        paddingHorizontal: space.md,
        fontSize: text.body,
      }}
    />
  );
}

/** A row-shaped placeholder: the same box a card will occupy, so nothing moves when it arrives. */
export function SkeletonRows({ count = 4, height = 112 }: { count?: number; height?: number }) {
  const c = useColours();
  const t = useTranslations("mobile.list");
  return (
    <View accessibilityLabel={t("loading")} accessibilityState={{ busy: true }} style={{ gap: space.md }}>
      {Array.from({ length: count }, (_, i) => (
        <View
          key={i}
          style={{
            height,
            borderRadius: radius.lg,
            borderWidth: 1,
            borderColor: c.border,
            backgroundColor: c.surfaceMuted,
          }}
        />
      ))}
    </View>
  );
}

/** What went wrong, in the server's words when it said any, with a way to try again. */
export function FailureNotice({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const t = useTranslations("errors");
  const m = useTranslations("mobile.list");
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <View style={{ gap: space.md }}>
      <Text variant="lead">{notFound ? t("notFoundTitle") : t("title")}</Text>
      <Text tone="muted">{notFound ? t("notFoundBody") : t("body")}</Text>
      {notFound ? null : <Button variant="secondary" label={m("retry")} onPress={onRetry} />}
    </View>
  );
}

type Page<T> = { items: readonly T[]; total: number };

/**
 * An infinite list over a `useInfiniteQuery`. `header` carries the search box and the filters and
 * is passed as an element, never a component, so typing does not remount it and lose the keyboard.
 */
export function ResultList<T>({
  query,
  header,
  renderRow,
  keyOf,
  emptyText,
  countLabel,
}: {
  query: UseInfiniteQueryResult<{ pages: Page<T>[] }, Error>;
  header: ReactElement;
  renderRow: (row: T) => ReactElement;
  keyOf: (row: T) => string;
  emptyText: string;
  countLabel?: (total: number) => string;
}) {
  const c = useColours();
  const m = useTranslations("mobile.list");
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;
  const firstAnswerPending = query.isPending;
  const firstFailed = query.isError && rows.length === 0;

  return (
    <SafeAreaView edges={["top"]} style={{ flex: 1, backgroundColor: c.background }}>
      <FlatList
        testID="result-list"
        data={rows}
        keyExtractor={keyOf}
        renderItem={({ item }) => renderRow(item)}
        ItemSeparatorComponent={() => <View style={{ height: space.md }} />}
        contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
        refreshing={query.isRefetching && !query.isFetchingNextPage}
        onRefresh={() => void query.refetch()}
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (query.hasNextPage && !query.isFetchingNextPage && !query.isFetchNextPageError) {
            void query.fetchNextPage();
          }
        }}
        ListHeaderComponent={
          <View style={{ gap: space.md, paddingBottom: space.md }}>
            {header}
            {!firstAnswerPending && !firstFailed && countLabel ? (
              <Text tone="muted">{countLabel(total)}</Text>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          firstAnswerPending ? (
            <SkeletonRows />
          ) : firstFailed ? (
            <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <Text tone="muted">{emptyText}</Text>
          )
        }
        ListFooterComponent={
          query.isFetchingNextPage ? (
            <ActivityIndicator color={c.brand} accessibilityLabel={m("loading")} />
          ) : query.isFetchNextPageError ? (
            <View style={{ gap: space.sm }}>
              <Text tone="muted">{m("loadMoreFailed")}</Text>
              <Button variant="secondary" label={m("retry")} onPress={() => void query.fetchNextPage()} />
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}
