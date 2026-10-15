import { useRouter } from "expo-router";
import type { ReactNode } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError } from "../core/errors";
import { useAccount } from "../lib/me-queries";
import { space } from "../theme";
import { FailureNotice, SkeletonRows } from "./list";
import { Button, Notice, Text } from "./primitives";
import { SessionExpired } from "./session";

/**
 * What stands between a visitor and a screen about *them*. Four answers, in order:
 *
 * 1. **Signed out** gets the way in, and the screen below makes **no request** (the web's rule since
 *    Sprint 52: a signed-out visitor makes nothing that can only answer 401).
 * 2. **A session the server has ended** says so, rather than showing an empty screen.
 * 3. **While the account is loading** a placeholder, never a flash of the wrong thing.
 * 4. **An organisation-only account** is told this is the job seeker's app and where to go
 *    instead: v1 is candidate-only, and a button that always fails is worse than none.
 */
export function SeekerGate({ prompt, children }: { prompt: string; children: ReactNode }) {
  const { signedIn, isJobSeeker, query } = useAccount();
  const router = useRouter();
  const t = useTranslations("mobile");
  const ta = useTranslations("auth");

  if (!signedIn) {
    return (
      <View style={{ gap: space.md }}>
        <Text tone="muted">{prompt}</Text>
        <Button label={ta("signInTitle")} onPress={() => router.push("/sign-in")} />
      </View>
    );
  }
  if (query.isError) {
    return query.error instanceof ApiError && query.error.status === 401 ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  if (isJobSeeker === undefined) return <SkeletonRows count={2} />;
  if (!isJobSeeker) return <Notice tone="warning">{t("home.organisationNote")}</Notice>;
  return <>{children}</>;
}
