import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError } from "../../src/core/errors";
import { useJob } from "../../src/lib/queries";
import { useMatch } from "../../src/lib/me-queries";
import { space } from "../../src/theme";
import { ApplyPanel } from "../../src/ui/ApplyPanel";
import { SeekerGate } from "../../src/ui/gate";
import { Button, Screen, Text } from "../../src/ui/primitives";
import { FailureNotice, SkeletonRows } from "../../src/ui/list";
import { GapLists, ScoreSummary } from "../../src/ui/match";
import { SessionExpired } from "../../src/ui/session";
import { SuggestedCourses } from "../../src/ui/SuggestedCourses";
import { Section } from "../../src/ui/detail";

/**
 * One match opened: the score and what caps it, what the person has and still needs (required
 * standards first), the courses that close this gap with where, when and what they cost, how to
 * become qualified at all, and apply. Everything shown is a field the server computed.
 */
export default function MatchDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const t = useTranslations("matchesPage");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <SeekerGate prompt={t("subtitle")}>
        <Body slug={slug} />
      </SeekerGate>
    </Screen>
  );
}

function Body({ slug }: { slug: string }) {
  const t = useTranslations("matchesPage");
  const router = useRouter();
  const match = useMatch(slug);
  const job = useJob(slug);

  if (match.isPending) return <SkeletonRows count={3} />;
  if (match.isError) {
    return match.error instanceof ApiError && match.error.status === 401 ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={match.error} onRetry={() => void match.refetch()} />
    );
  }
  const m = match.data;
  const courses = m.courses ?? [];
  const place = [m.job.location_district, m.job.location_state].filter(Boolean).join(", ");

  return (
    <View style={{ gap: space.lg }}>
      <Text variant="title">{m.job.title}</Text>
      {place ? (
        <Text tone="muted" variant="lead">
          {place}
        </Text>
      ) : null}

      <ScoreSummary match={m} />
      <GapLists match={m} />

      <Section title={t("coursesHeading")}>
        {courses.length > 0 ? <SuggestedCourses courses={courses} /> : <Text tone="muted">{t("noCourses")}</Text>}
      </Section>

      {m.entry ? (
        <Section title={t("entryHeading")}>
          <Text>{t("entryVia", { name: m.entry.qp_name, code: m.entry.qp_code })}</Text>
          <Text tone="muted">
            {t("entryRoutes", { count: m.entry.routes_total })}
            {m.entry.lowest_experience_years != null
              ? ` · ${t("entryExperience", { years: m.entry.lowest_experience_years })}`
              : ""}
          </Text>
          {m.entry.education_options.length > 0 ? (
            <Text tone="muted" variant="small">
              {`${t("entryEducation")}: ${m.entry.education_options.slice(0, 3).join(" · ")}`}
            </Text>
          ) : null}
        </Section>
      ) : null}

      <ApplyPanel
        jobSlug={m.job.slug}
        organisation={job.data?.tenant.name ?? ""}
        isOpen={job.data ? job.data.is_open : true}
      />
      <Button variant="secondary" label={t("viewJob")} onPress={() => router.push(`/job/${m.job.slug}`)} />
    </View>
  );
}
