import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { suggestionBadges, suggestionFacts, type Suggestion } from "../core/suggestions";
import { useMonthName } from "../lib/months";
import { space } from "../theme";
import { Badge, BadgeRow, Card } from "./list";
import { Text } from "./primitives";

/**
 * The one list of courses that close a gap, with what a person needs to act on each: where, when,
 * what it costs, how long, whether there is room, and how near it is. **Nothing is hidden**: a
 * started, full, faraway or over-budget course is labelled, because it may be the only one that
 * teaches the missing standard. The order is the server's; this renders it and computes nothing.
 */
export function SuggestedCourses({ courses }: { courses: readonly Suggestion[] }) {
  const t = useTranslations("suggestedCourses");
  const router = useRouter();
  const monthName = useMonthName();
  const say = (key: string, values?: Record<string, string | number>) => t(key, values);

  return (
    <View style={{ gap: space.sm }}>
      {courses.map((c) => (
        <Card key={c.slug} onPress={() => router.push(`/course/${c.slug}`)} label={c.title}>
          <Text>{c.title}</Text>
          <Text tone="muted" variant="small">
            {suggestionFacts(c, say, monthName).join(" · ")}
          </Text>
          <BadgeRow>
            {suggestionBadges(c).map((b) => (
              <Badge key={b.key} tone={b.tone} label={t(b.key)} />
            ))}
          </BadgeRow>
          <Text variant="small">{t("closesGap", { closed: c.closes_count, total: c.gap_size })}</Text>
        </Card>
      ))}
    </View>
  );
}
