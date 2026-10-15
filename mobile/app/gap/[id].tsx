import { Stack, useLocalSearchParams } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../../src/core/errors";
import { useApplicationGap } from "../../src/lib/me-queries";
import { space } from "../../src/theme";
import { BudgetField } from "../../src/ui/BudgetField";
import { Section } from "../../src/ui/detail";
import { SeekerGate } from "../../src/ui/gate";
import { Badge, BadgeRow, FailureNotice, SkeletonRows } from "../../src/ui/list";
import { GapLists, ScoreSummary } from "../../src/ui/match";
import { Screen, Text } from "../../src/ui/primitives";
import { SessionExpired } from "../../src/ui/session";
import { SuggestedCourses } from "../../src/ui/SuggestedCourses";

/**
 * "Why not me" (ADR-048): what one of the person's own applications was missing, and the courses
 * that teach it. **Computed now from their skills as they stand**, through the one scorer: it
 * changes as they add to them, it is never stored, and it says nothing about why the employer
 * decided as they did, because the product does not know.
 */
export default function Gap() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("applications");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("whyNotMe") }} />
      <Text variant="title">{t("whyNotMe")}</Text>
      <SeekerGate prompt={t("pageSubtitle")}>
        <Body id={id ?? ""} />
      </SeekerGate>
    </Screen>
  );
}

function Body({ id }: { id: string }) {
  const t = useTranslations("applications");
  const tm = useTranslations("matchesPage");
  const query = useApplicationGap(id);

  if (query.isPending) return <SkeletonRows count={3} />;
  if (query.isError) {
    return isSignedOut(query.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  const gap = query.data;
  const missing = gap.missing ?? [];
  const courses = gap.courses ?? [];

  return (
    <View style={{ gap: space.lg }}>
      <View style={{ gap: space.xs }}>
        <BadgeRow>
          <Badge tone="warning" label={t(`status.${gap.status}`)} />
        </BadgeRow>
        <Text variant="lead">{gap.job.title}</Text>
        <Text tone="muted">{gap.job.tenant.name}</Text>
        <Text tone="muted" variant="small">
          {t("gapIntro")}
        </Text>
      </View>

      <ScoreSummary match={{ ...gap, job: {} }} />
      {missing.length === 0 ? <Text>{t("gapNothing")}</Text> : <GapLists match={{ ...gap, matched: [], job: {} }} />}

      {missing.length > 0 ? (
        <Section title={tm("coursesHeading")}>
          <BudgetField />
          {courses.length > 0 ? <SuggestedCourses courses={courses} /> : <Text tone="muted">{tm("noCourses")}</Text>}
        </Section>
      ) : null}
    </View>
  );
}
