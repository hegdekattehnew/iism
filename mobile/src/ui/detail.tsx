import type { ReactNode } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { space, useColours } from "../theme";
import { Button, Text } from "./primitives";
import { FailureNotice, SkeletonRows } from "./list";

/**
 * The pieces a detail screen is made of: a labelled fact, a titled section, and the three states a
 * single record can be in before it can be shown. A **404 says "does not exist"; anything else says
 * "could not load, try again"**: the web's rule since Sprint 20, when an outage was telling visitors
 * that a vacancy had never existed.
 */

export function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flexBasis: "47%", flexGrow: 1, gap: 2 }}>
      <Text tone="muted" variant="small">
        {label}
      </Text>
      <Text variant="lead">{value}</Text>
    </View>
  );
}

export function Facts({ children }: { children: ReactNode }) {
  const c = useColours();
  return (
    <View
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        gap: space.lg,
        borderWidth: 1,
        borderColor: c.border,
        backgroundColor: c.surface,
        borderRadius: 16,
        padding: space.lg,
      }}
    >
      {children}
    </View>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={{ gap: space.sm }}>
      <Text tone="muted" variant="small">
        {title}
      </Text>
      {children}
    </View>
  );
}

export function RecordState({
  query,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  children: ReactNode;
}) {
  if (query.isPending) return <SkeletonRows count={3} />;
  if (query.isError) return <FailureNotice error={query.error} onRetry={() => void query.refetch()} />;
  return <>{children}</>;
}

/** The nudge a visitor gets where, once signed in, the screen would say how well they match. */
export function SignInToMatch({ onPress }: { onPress: () => void }) {
  const t = useTranslations("mobile.detail");
  return (
    <View style={{ gap: space.sm }}>
      <Text tone="muted">{t("signInToMatch")}</Text>
      <Button variant="secondary" label={t("signInAction")} onPress={onPress} />
    </View>
  );
}
