import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError } from "../../src/core/errors";
import { localityKey } from "../../src/core/matches";
import { useMatches } from "../../src/lib/me-queries";
import { space } from "../../src/theme";
import { Badge, BadgeRow, Card, FailureNotice, SkeletonRows } from "../../src/ui/list";
import { SeekerGate } from "../../src/ui/gate";
import { Button, Screen, Text } from "../../src/ui/primitives";
import { MatchSentence } from "../../src/ui/match";
import { SessionExpired } from "../../src/ui/session";

/**
 * Jobs ranked by how much of what they need the person already has. A list of cards that open the
 * match with its gap; the score is the scorer's and is only displayed. "No skills yet" is a
 * different state from "no matches" and says so: it is the difference between a dead end and a
 * next step.
 */
export default function Matches() {
  const t = useTranslations("matchesPage");
  return (
    <Screen>
      <Text variant="title">{t("title")}</Text>
      <SeekerGate prompt={t("subtitle")}>
        <MatchList />
      </SeekerGate>
    </Screen>
  );
}

function MatchList() {
  const t = useTranslations("matchesPage");
  const v = useTranslations("matchViz");
  const router = useRouter();
  const query = useMatches();

  if (query.isPending) return <SkeletonRows />;
  if (query.isError) {
    return query.error instanceof ApiError && query.error.status === 401 ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  if (!query.data.has_skills) {
    return (
      <View style={{ gap: space.md }}>
        <Text tone="muted">{t("noSkills")}</Text>
        <Button label={t("addSkills")} onPress={() => router.push("/profile")} />
      </View>
    );
  }
  if (query.data.items.length === 0) return <Text tone="muted">{t("noMatches")}</Text>;

  return (
    <View style={{ gap: space.md }}>
      <Text tone="muted">{t("subtitle")}</Text>
      {query.data.items.map((m) => {
        const near = localityKey(m.locality);
        const place = [m.job.location_district, m.job.location_state].filter(Boolean).join(", ");
        return (
          <Card key={m.job.slug} onPress={() => router.push(`/match/${m.job.slug}`)} label={m.job.title}>
            <BadgeRow>
              <Badge tone="brand" label={t("matchScore", { score: m.score })} />
              {near ? <Badge tone="success" label={t(near)} /> : null}
              {m.capped_by_mandatory ? <Badge tone="warning" label={v("cappedBy", { count: m.missing_mandatory ?? 1 })} /> : null}
            </BadgeRow>
            <Text variant="lead">{m.job.title}</Text>
            {place ? (
              <Text tone="muted" variant="small">
                {place}
              </Text>
            ) : null}
            <MatchSentence match={m} />
          </Card>
        );
      })}
    </View>
  );
}
