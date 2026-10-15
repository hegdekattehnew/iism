import type { UseInfiniteQueryResult } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";
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

export function Card({
  children,
  onPress,
  label,
}: {
  children: ReactNode;
  onPress?: () => void;
  label?: string;
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
        backgroundColor: c.surface,
        borderRadius: radius.lg,
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
  tone?: "brand" | "muted" | "success" | "warning";
}) {
  const c = useColours();
  const palette = {
    brand: [c.accentSoft, c.brand],
    muted: [c.surfaceMuted, c.muted],
    success: [c.successSurface, c.successText],
    warning: [c.warningSurface, c.warningText],
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
export function SkeletonRows({ count = 4 }: { count?: number }) {
  const c = useColours();
  const t = useTranslations("mobile.list");
  return (
    <View accessibilityLabel={t("loading")} accessibilityState={{ busy: true }} style={{ gap: space.md }}>
      {Array.from({ length: count }, (_, i) => (
        <View
          key={i}
          style={{
            height: 112,
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
