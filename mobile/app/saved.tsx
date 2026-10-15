import { Stack, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../src/core/errors";
import { useSaved, useToggleSave } from "../src/lib/me-queries";
import { space } from "../src/theme";
import { SeekerGate } from "../src/ui/gate";
import { Card, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";

/** Vacancies kept to look at again. Saving tells the employer nothing. */
export default function Saved() {
  const t = useTranslations("applications");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("savedPageTitle") }} />
      <Text variant="title">{t("savedPageTitle")}</Text>
      <SeekerGate prompt={t("savedPageSubtitle")}>
        <List />
      </SeekerGate>
    </Screen>
  );
}

function List() {
  const t = useTranslations("applications");
  const tm = useTranslations("matchesPage");
  const router = useRouter();
  const query = useSaved();
  const toggle = useToggleSave();

  if (query.isPending) return <SkeletonRows />;
  if (query.isError) {
    return isSignedOut(query.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  if (query.data.length === 0) return <Text tone="muted">{t("savedEmpty")}</Text>;

  return (
    <View style={{ gap: space.md }}>
      <Text tone="muted">{t("savedPageSubtitle")}</Text>
      {query.data.map((s) => (
        <Card key={s.job.slug}>
          <Text variant="lead">{s.job.title}</Text>
          <Text tone="muted" variant="small">
            {s.job.tenant.name}
          </Text>
          <Button variant="secondary" label={tm("viewJob")} onPress={() => router.push(`/job/${s.job.slug}`)} />
          <Button
            variant="secondary"
            label={t("savedLabel")}
            busy={toggle.isPending && toggle.variables?.slug === s.job.slug}
            onPress={() => toggle.mutate({ slug: s.job.slug, saved: true })}
          />
        </Card>
      ))}
      {toggle.isError ? (
        isSignedOut(toggle.error) ? <SessionExpired /> : <Notice tone="danger">{t("errorGeneric")}</Notice>
      ) : null}
    </View>
  );
}
