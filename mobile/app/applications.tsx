import { Stack, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { canWithdraw, withdrawFailureKey } from "../src/core/applying";
import { isSignedOut, statusOf } from "../src/core/errors";
import { useInstantDate } from "../src/lib/months";
import { useApplications, useWithdraw } from "../src/lib/me-queries";
import { space } from "../src/theme";
import { SeekerGate } from "../src/ui/gate";
import { Badge, BadgeRow, Card, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";

/**
 * Every job the person applied for, where each stands, and what the employer said. The employer's
 * message is **read from the application** (ADR-070), the one latest message with a status change;
 * a notice only says that there is one. A withdrawn application shows nothing of the employer's.
 */
export default function Applications() {
  const t = useTranslations("applications");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("pageTitle") }} />
      <Text variant="title">{t("pageTitle")}</Text>
      <SeekerGate prompt={t("pageSubtitle")}>
        <List />
      </SeekerGate>
    </Screen>
  );
}

function List() {
  const t = useTranslations("applications");
  const tm = useTranslations("matchesPage");
  const router = useRouter();
  const day = useInstantDate();
  const query = useApplications();
  const withdraw = useWithdraw();

  if (query.isPending) return <SkeletonRows />;
  if (query.isError) {
    return isSignedOut(query.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  if (query.data.length === 0) {
    return (
      <View style={{ gap: space.md }}>
        <Text tone="muted">{t("empty")}</Text>
        <Button label={t("emptyCta")} onPress={() => router.navigate("/matches")} />
      </View>
    );
  }

  return (
    <View style={{ gap: space.md }}>
      <Text tone="muted">{t("pageSubtitle")}</Text>
      {query.data.map((a) => {
        const date = day(a.applied_at);
        const mine = withdraw.variables === a.id;
        return (
          <Card key={a.id}>
            <BadgeRow>
              <Badge
                tone={a.status === "rejected" || a.status === "no_show" ? "warning" : a.status === "withdrawn" ? "muted" : "success"}
                label={t(`status.${a.status}`)}
              />
              {a.job.removed ? <Badge tone="warning" label={t("removed")} /> : null}
            </BadgeRow>
            <Text variant="lead">{a.job.title}</Text>
            <Text tone="muted" variant="small">
              {a.job.tenant.name}
            </Text>
            <Text tone="muted">{t(`statusHint.${a.status}`)}</Text>
            {date ? (
              <Text tone="muted" variant="small">
                {t("appliedOn", { date })}
              </Text>
            ) : null}
            {a.status !== "withdrawn" && a.status_message ? (
              <View style={{ gap: 2 }}>
                <Text variant="small" tone="muted">
                  {t("fromEmployer", { organisation: a.job.tenant.name })}
                </Text>
                <Text>{a.status_message}</Text>
              </View>
            ) : null}
            <Button variant="secondary" label={tm("viewJob")} onPress={() => router.push(`/job/${a.job.slug}`)} />
            {/* Only for a rejection: "why not me" answers a decision that was made (ADR-048). */}
            {a.status === "rejected" ? (
              <Button variant="secondary" label={t("whyNotMe")} onPress={() => router.push(`/gap/${a.id}`)} />
            ) : null}
            {canWithdraw(a.status) ? (
              <Button
                variant="secondary"
                label={mine && withdraw.isPending ? t("withdrawing") : t("withdraw")}
                busy={mine && withdraw.isPending}
                onPress={() => withdraw.mutate(a.id)}
              />
            ) : null}
            {mine && withdraw.isError ? (
              isSignedOut(withdraw.error) ? (
                <SessionExpired />
              ) : (
                <Notice tone="danger">{t(withdrawFailureKey(statusOf(withdraw.error)))}</Notice>
              )
            ) : null}
          </Card>
        );
      })}
    </View>
  );
}
