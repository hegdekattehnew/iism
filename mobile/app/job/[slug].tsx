import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import {
  daysToClose,
  experienceLabel,
  postedText,
  salaryLabel,
  yearlyLabel,
} from "../../src/core/labels";
import { presentRequirements } from "../../src/core/requirements";
import { useJob } from "../../src/lib/queries";
import { useSignedIn } from "../../src/runtime";
import { ApplyPanel, useApplyVisible } from "../../src/ui/ApplyPanel";
import { ReportPanel } from "../../src/ui/ReportPanel";
import { space, useColours } from "../../src/theme";
import { Badge, BadgeRow, Button, Card, Screen, Text } from "../../src/ui";
import { Fact, Facts, RecordState, Section, SignInToMatch } from "../../src/ui/detail";

export default function JobDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const t = useTranslations("jobsPage");
  const router = useRouter();
  const c = useColours();
  const signedIn = useSignedIn();
  const query = useJob(slug);
  const job = query.data;
  const [showAlso, setShowAlso] = useState(false);
  // Read once when the screen opens; a render must give the same answer twice.
  const [openedAt] = useState(() => Date.now());
  // The apply bar is under the content, not in it (UI-08); and only when it has something to show.
  const applyVisible = useApplyVisible(job?.slug ?? "", job?.is_open ?? true);

  const say = (k: string, v?: Record<string, string | number>) => t(k, v);
  const { main, also } = presentRequirements(
    (job?.skills ?? []).map((s) => ({
      slug: s.skill.slug,
      name: s.skill.name,
      mandatory: s.is_mandatory,
      importance: s.importance,
    })),
  );
  const days = job ? daysToClose(job.closes_at, openedAt) : null;
  const yearly = job ? yearlyLabel(job, say) : null;
  const posted = job ? postedText(job.published_at, say, openedAt) : null;

  return (
    <Screen
      footer={
        job && applyVisible ? (
          <ApplyPanel jobSlug={job.slug} organisation={job.tenant.name} isOpen={job.is_open} compact />
        ) : undefined
      }
    >
      <Stack.Screen options={{ title: job?.title ?? "" }} />
      <RecordState query={query}>
        {job ? (
          <>
            <BadgeRow>
              <Badge tone="brand" label={t(`employmentType.${job.employment_type}`)} />
              {job.nsqf_level_min != null ? <Badge label={t("minLevel", { level: job.nsqf_level_min })} /> : null}
              {days !== null ? <Badge tone="warning" label={t("closesIn", { days })} /> : null}
            </BadgeRow>
            <Text variant="title">{job.title}</Text>
            <Text variant="lead" tone="muted">
              {job.tenant.name}
              {job.location_district ? ` · ${job.location_district}` : ""}
              {job.location_state ? `, ${job.location_state}` : ""}
            </Text>
            {posted !== null ? (
              <Text tone="muted" variant="small">
                {posted}
              </Text>
            ) : null}

            <Facts>
              <Fact label={t("salaryLabel")} value={salaryLabel(job, say)} />
              <Fact label={t("experienceLabel")} value={experienceLabel(job, say)} />
            </Facts>
            {yearly ? (
              <Text tone="muted" variant="small">
                {yearly}
              </Text>
            ) : null}

            {/* Who is behind it and what they may not ask for. The screen says "not yet verified"; a card
                in a list never does (it would read as an accusation of every employer without a mark). */}
            <View
              style={{
                gap: space.xs,
                borderWidth: 1,
                borderColor: c.border,
                backgroundColor: c.surface,
                borderRadius: 16,
                padding: space.lg,
              }}
            >
              {job.tenant.is_verified ? (
                <Badge tone="success" label={t("verifiedEmployer")} />
              ) : (
                <Text tone="muted">{t("notVerifiedYet")}</Text>
              )}
              <Text tone="muted">
                {t("neverPay")} {t("reportThis")}
              </Text>
            </View>

            {job.description ? <Text>{job.description}</Text> : null}

            <Section title={t("requiredSkills")}>
              <View style={{ gap: space.sm }}>
                {main.map((s) => (
                  <Card key={s.slug} onPress={() => router.push(`/skill/${s.slug}`)} label={s.name}>
                    {s.mandatory ? (
                      <BadgeRow>
                        <Badge tone="brand" label={t("mandatory")} />
                      </BadgeRow>
                    ) : null}
                    <Text>{s.name}</Text>
                  </Card>
                ))}
                {also.length > 0 ? (
                  <>
                    <Button
                      variant="secondary"
                      label={t("alsoCovered", { count: also.length })}
                      onPress={() => setShowAlso((v) => !v)}
                    />
                    {showAlso
                      ? also.map((s) => (
                          <Card key={s.slug} onPress={() => router.push(`/skill/${s.slug}`)} label={s.name}>
                            <Text tone="muted">{s.name}</Text>
                          </Card>
                        ))
                      : null}
                  </>
                ) : null}
              </View>
            </Section>

            <ReportPanel target="job" slug={job.slug} />

            {signedIn ? null : <SignInToMatch onPress={() => router.push("/sign-in")} />}
          </>
        ) : null}
      </RecordState>
    </Screen>
  );
}
