import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { lookalikeNames } from "../src/core/labels";
import { useSearch } from "../src/lib/queries";
import { space } from "../src/theme";
import { Badge, BadgeRow, Button, Card, Screen, SearchBox, SkeletonRows, Text } from "../src/ui";
import { FailureNotice } from "../src/ui/list";
import { Section } from "../src/ui/detail";

/**
 * What a search answers: **jobs first, then roles, then standards** (the web's order, Sprint 23): the
 * work that is open now, the job roles behind it, and the standards for anyone who came for the
 * taxonomy. Each band is a preview and links to its full list with the term kept.
 */
export default function Search() {
  const params = useLocalSearchParams<{ q?: string }>();
  const t = useTranslations("searchPage");
  const tj = useTranslations("jobsPage");
  const ts = useTranslations("skillsPage");
  const router = useRouter();
  const [draft, setDraft] = useState(params.q ?? "");
  const term = (params.q ?? "").trim();
  const { jobs, roles, standards } = useSearch(term);
  const standardRows = (standards.data ?? []).slice(0, 6);
  const twins = lookalikeNames(standardRows);

  const submit = () => {
    const next = draft.trim();
    if (next) router.setParams({ q: next });
  };

  return (
    <Screen>
      <Stack.Screen options={{ title: term ? t("title", { q: term }) : t("titleEmpty") }} />
      <SearchBox value={draft} onChangeText={setDraft} placeholder={t("placeholder")} onSubmit={submit} />
      <Button label={t("submit")} onPress={submit} disabled={draft.trim().length === 0} />

      {term ? (
        <>
          <Section title={t("jobsHeading")}>
            {jobs.isPending ? (
              <SkeletonRows count={2} />
            ) : jobs.isError ? (
              <FailureNotice error={jobs.error} onRetry={() => void jobs.refetch()} />
            ) : (jobs.data?.items ?? []).length === 0 ? (
              <Text tone="muted">{t("noJobs")}</Text>
            ) : (
              <View style={{ gap: space.sm }}>
                {(jobs.data?.items ?? []).map((job) => (
                  <Card key={job.slug} onPress={() => router.push(`/job/${job.slug}`)} label={job.title}>
                    <BadgeRow>
                      <Badge tone="brand" label={tj(`employmentType.${job.employment_type}`)} />
                    </BadgeRow>
                    <Text variant="lead">{job.title}</Text>
                    <Text tone="muted">{job.tenant.name}</Text>
                  </Card>
                ))}
                {(jobs.data?.total ?? 0) > (jobs.data?.items ?? []).length ? (
                  <Button
                    variant="secondary"
                    label={t("seeAllJobs", { count: jobs.data?.total ?? 0 })}
                    onPress={() => router.navigate({ pathname: "/jobs", params: { q: term } })}
                  />
                ) : null}
              </View>
            )}
          </Section>

          <Section title={t("rolesHeading")}>
            {roles.isPending ? (
              <SkeletonRows count={1} />
            ) : roles.isError ? (
              <FailureNotice error={roles.error} onRetry={() => void roles.refetch()} />
            ) : (roles.data ?? []).length === 0 ? (
              <Text tone="muted">{t("noRoles")}</Text>
            ) : (
              <View style={{ gap: space.sm }}>
                <Text tone="muted" variant="small">
                  {t("rolesNote")}
                </Text>
                {(roles.data ?? []).map((role) => (
                  <Card key={role.slug}>
                    <Text variant="lead">{role.job_role}</Text>
                    <Text tone="muted" variant="small">
                      {[role.sector_name, t("standardsCount", { count: role.standards_count })].filter(Boolean).join(" · ")}
                    </Text>
                  </Card>
                ))}
              </View>
            )}
          </Section>

          <Section title={t("standardsHeading")}>
            {standards.isPending ? (
              <SkeletonRows count={2} />
            ) : standards.isError ? (
              <FailureNotice error={standards.error} onRetry={() => void standards.refetch()} />
            ) : standardRows.length === 0 ? (
              <Text tone="muted">{t("noStandards")}</Text>
            ) : (
              <View style={{ gap: space.sm }}>
                {standardRows.map((skill) => (
                  <Card key={skill.slug} onPress={() => router.push(`/skill/${skill.slug}`)} label={skill.name}>
                    <Text>{skill.name}</Text>
                    <Text tone="muted" variant="small">
                      {[skill.nos_code, skill.context?.qualification_name].filter(Boolean).join(" · ")}
                    </Text>
                    {twins.has(skill.name.trim().toLowerCase()) ? (
                      <Text tone="muted" variant="small">
                        {ts("lookalike")}
                      </Text>
                    ) : null}
                  </Card>
                ))}
                {(standards.data ?? []).length > standardRows.length ? (
                  <Button
                    variant="secondary"
                    label={t("seeAllStandards")}
                    onPress={() => router.navigate({ pathname: "/skills", params: { q: term } })}
                  />
                ) : null}
              </View>
            )}
          </Section>
        </>
      ) : (
        <Text tone="muted">{t("prompt")}</Text>
      )}
    </Screen>
  );
}
