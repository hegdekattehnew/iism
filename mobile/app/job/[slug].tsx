import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { experienceLabel, mandatoryFirst, salaryLabel } from "../../src/core/labels";
import { useJob } from "../../src/lib/queries";
import { useSignedIn } from "../../src/runtime";
import { space } from "../../src/theme";
import { Badge, BadgeRow, Card, Notice, Screen, Text } from "../../src/ui";
import { Fact, Facts, RecordState, Section, SignInToMatch } from "../../src/ui/detail";

export default function JobDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const t = useTranslations("jobsPage");
  const ta = useTranslations("applications");
  const router = useRouter();
  const signedIn = useSignedIn();
  const query = useJob(slug);
  const job = query.data;

  return (
    <Screen>
      <Stack.Screen options={{ title: job?.title ?? "" }} />
      <RecordState query={query}>
        {job ? (
          <>
            <BadgeRow>
              <Badge tone="brand" label={t(`employmentType.${job.employment_type}`)} />
              {job.nsqf_level_min != null ? <Badge label={t("minLevel", { level: job.nsqf_level_min })} /> : null}
            </BadgeRow>
            <Text variant="title">{job.title}</Text>
            <Text variant="lead" tone="muted">
              {job.tenant.name}
              {job.location_district ? ` · ${job.location_district}` : ""}
              {job.location_state ? `, ${job.location_state}` : ""}
            </Text>

            {job.is_open ? null : <Notice tone="warning">{ta("vacancyClosed")}</Notice>}

            <Facts>
              <Fact label={t("experienceLabel")} value={experienceLabel(job, (k, v) => t(k, v))} />
              <Fact label={t("salaryLabel")} value={salaryLabel(job, (k, v) => t(k, v))} />
            </Facts>

            {job.description ? <Text>{job.description}</Text> : null}

            <Section title={t("requiredSkills")}>
              <View style={{ gap: space.sm }}>
                {mandatoryFirst(job.skills ?? []).map((s) => (
                  <Card key={s.skill.slug} onPress={() => router.push(`/skill/${s.skill.slug}`)} label={s.skill.name}>
                    <BadgeRow>
                      <Badge tone={s.is_mandatory ? "brand" : "muted"} label={s.is_mandatory ? t("mandatory") : t("optional")} />
                    </BadgeRow>
                    <Text>{s.skill.name}</Text>
                    <Text tone="muted" variant="small">
                      {t("importance", { n: s.importance })}
                    </Text>
                  </Card>
                ))}
              </View>
            </Section>

            {signedIn ? null : <SignInToMatch onPress={() => router.push("/sign-in")} />}
          </>
        ) : null}
      </RecordState>
    </Screen>
  );
}
