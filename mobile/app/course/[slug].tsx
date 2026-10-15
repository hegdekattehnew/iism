import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { feeLabel, intakeLabel, seatsLabel, whereLabel } from "../../src/core/labels";
import { useCourse } from "../../src/lib/queries";
import { useMonthName } from "../../src/lib/months";
import { useSignedIn } from "../../src/runtime";
import { InterestPanel } from "../../src/ui/InterestPanel";
import { ReportPanel } from "../../src/ui/ReportPanel";
import { space } from "../../src/theme";
import { Badge, BadgeRow, Card, Screen, Text } from "../../src/ui";
import { Fact, Facts, RecordState, Section, SignInToMatch } from "../../src/ui/detail";

export default function CourseDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const t = useTranslations("coursesPage");
  const router = useRouter();
  const monthName = useMonthName();
  const signedIn = useSignedIn();
  const query = useCourse(slug);
  const course = query.data;
  const say = (k: string, v?: Record<string, string | number>) => t(k, v);

  return (
    <Screen>
      <Stack.Screen options={{ title: course?.title ?? "" }} />
      <RecordState query={query}>
        {course ? (
          <>
            <BadgeRow>
              <Badge tone="brand" label={t(`mode.${course.mode}`)} />
              <Badge label={t(`language.${course.language}`)} />
              {course.nsqf_level != null ? <Badge label={t("level", { level: course.nsqf_level })} /> : null}
            </BadgeRow>
            <Text variant="title">{course.title}</Text>
            <Text variant="lead" tone="muted">
              {course.tenant.name}
            </Text>

            <Facts>
              <Fact label={t("feeLabel")} value={feeLabel(course, say)} />
              {course.duration_hours != null ? (
                <Fact label={t("durationLabel")} value={t("duration", { hours: course.duration_hours })} />
              ) : null}
              {whereLabel(course, say, true) ? <Fact label={t("placeLabel")} value={whereLabel(course, say, true) ?? ""} /> : null}
              <Fact label={t("intakeLabel")} value={intakeLabel(course, say, monthName, "long") ?? t("startNotStated")} />
              {seatsLabel(course.seats_left, say) ? (
                <Fact label={t("seatsLabel")} value={seatsLabel(course.seats_left, say) ?? ""} />
              ) : null}
            </Facts>

            {course.description ? <Text>{course.description}</Text> : null}

            <Section title={t("skillsTaught")}>
              <View style={{ gap: space.sm }}>
                {(course.skills ?? []).map((s) => (
                  <Card key={s.skill.slug} onPress={() => router.push(`/skill/${s.skill.slug}`)} label={s.skill.name}>
                    <Text>{s.skill.name}</Text>
                    {s.level_taught != null ? (
                      <Text tone="muted" variant="small">
                        {t("teachesToLevel", { level: s.level_taught })}
                      </Text>
                    ) : null}
                  </Card>
                ))}
              </View>
            </Section>

            <InterestPanel courseSlug={course.slug} organisation={course.tenant.name} />
            <ReportPanel target="course" slug={course.slug} />

            {signedIn ? null : <SignInToMatch onPress={() => router.push("/sign-in")} />}
          </>
        ) : null}
      </RecordState>
    </Screen>
  );
}
