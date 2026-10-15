import { Stack, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../src/core/errors";
import { useInstantDate } from "../src/lib/months";
import { useInterests, useWithdrawInterest } from "../src/lib/me-queries";
import { space } from "../src/theme";
import { SeekerGate } from "../src/ui/gate";
import { Badge, BadgeRow, Card, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";

/** The courses the person asked about, and where each stands (registered, contacted, enrolled). */
export default function Interests() {
  const t = useTranslations("courseInterest");
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
  const t = useTranslations("courseInterest");
  const tm = useTranslations("mobile.me");
  const router = useRouter();
  const day = useInstantDate();
  const query = useInterests();
  const withdraw = useWithdrawInterest();

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
        <Button label={t("emptyCta")} onPress={() => router.navigate("/courses")} />
      </View>
    );
  }

  return (
    <View style={{ gap: space.md }}>
      <Text tone="muted">{t("pageSubtitle")}</Text>
      {query.data.map((i) => {
        const date = day(i.registered_at);
        return (
          <Card key={i.id}>
            <BadgeRow>
              <Badge tone={i.status === "withdrawn" ? "muted" : "success"} label={t(`status.${i.status}`)} />
            </BadgeRow>
            <Text variant="lead">{i.course.title}</Text>
            <Text tone="muted" variant="small">
              {i.course.tenant.name}
            </Text>
            {date ? (
              <Text tone="muted" variant="small">
                {t("registeredOn", { date })}
              </Text>
            ) : null}
            <Button variant="secondary" label={tm("viewCourse")} onPress={() => router.push(`/course/${i.course.slug}`)} />
            {i.status !== "withdrawn" ? (
              <Button
                variant="secondary"
                label={withdraw.isPending && withdraw.variables === i.id ? t("withdrawing") : t("withdraw")}
                busy={withdraw.isPending && withdraw.variables === i.id}
                onPress={() => withdraw.mutate(i.id)}
              />
            ) : null}
          </Card>
        );
      })}
      {withdraw.isError ? (
        isSignedOut(withdraw.error) ? <SessionExpired /> : <Notice tone="danger">{t("errorGeneric")}</Notice>
      ) : null}
    </View>
  );
}
