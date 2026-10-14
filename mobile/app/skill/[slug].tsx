import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { useSkill, useSkillCourses, useSkillJobs } from "../../src/lib/queries";
import { space } from "../../src/theme";
import { Badge, BadgeRow, Card, Screen, Text } from "../../src/ui";
import { RecordState, Section } from "../../src/ui/detail";

export default function SkillDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const t = useTranslations("skillsPage");
  const tl = useTranslations("skillLinks");
  const router = useRouter();
  const query = useSkill(slug);
  const jobs = useSkillJobs(slug);
  const courses = useSkillCourses(slug);
  const skill = query.data;
  const ctx = skill?.context;

  return (
    <Screen>
      <Stack.Screen options={{ title: skill?.name ?? "" }} />
      <RecordState query={query}>
        {skill ? (
          <>
            <BadgeRow>
              <Badge tone="brand" label={t(`type.${skill.skill_type}`)} />
              {skill.nsqf_level != null ? <Badge label={t("level", { level: skill.nsqf_level })} /> : null}
            </BadgeRow>
            <Text variant="title">{skill.name}</Text>
            {skill.nos_code ? (
              <Text tone="muted">
                {t("nosCode")}: {skill.nos_code}
              </Text>
            ) : null}
            {ctx?.qualification_name ? (
              <Text tone="muted">{[ctx.qualification_name, ctx.sector, ctx.awarding_body].filter(Boolean).join(" · ")}</Text>
            ) : null}
            {skill.description ? <Text>{skill.description}</Text> : null}

            <Section title={tl("jobsTitle")}>
              {jobs.isPending ? null : (jobs.data ?? []).length === 0 ? (
                <Text tone="muted">{tl("noJobs")}</Text>
              ) : (
                <View style={{ gap: space.sm }}>
                  {(jobs.data ?? []).map((job) => (
                    <Card key={job.slug} onPress={() => router.push(`/job/${job.slug}`)} label={job.title}>
                      <Text>{job.title}</Text>
                      <Text tone="muted" variant="small">
                        {job.tenant.name}
                      </Text>
                    </Card>
                  ))}
                </View>
              )}
            </Section>

            <Section title={tl("coursesTitle")}>
              {courses.isPending ? null : (courses.data ?? []).length === 0 ? (
                <Text tone="muted">{tl("noCourses")}</Text>
              ) : (
                <View style={{ gap: space.sm }}>
                  {(courses.data ?? []).map((course) => (
                    <Card key={course.slug} onPress={() => router.push(`/course/${course.slug}`)} label={course.title}>
                      <Text>{course.title}</Text>
                      <Text tone="muted" variant="small">
                        {course.tenant.name}
                      </Text>
                    </Card>
                  ))}
                </View>
              )}
            </Section>
          </>
        ) : null}
      </RecordState>
    </Screen>
  );
}
