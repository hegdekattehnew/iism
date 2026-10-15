import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../src/core/errors";
import { mandatoryFirst } from "../src/core/labels";
import { useCareers, useRoleHits } from "../src/lib/me-queries";
import { space } from "../src/theme";
import { BudgetField } from "../src/ui/BudgetField";
import { SeekerGate } from "../src/ui/gate";
import { Badge, BadgeRow, Card, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text, TextField } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";
import { SuggestedCourses } from "../src/ui/SuggestedCourses";

/**
 * Where the person could move next (ADR-049): the roles that build on theirs and what it would take.
 * Derived on the server from the national qualification data and **stored nowhere**; each step says
 * what it was derived from. The starting role is the person's own choice, or one guess the server
 * makes from their profile, **said to be a guess** and easy to change.
 */
export default function Careers() {
  const t = useTranslations("careerPaths");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <Text variant="title">{t("title")}</Text>
      <Text tone="muted">{t("subtitle")}</Text>
      <SeekerGate prompt={t("chooseIntro")}>
        <Body />
      </SeekerGate>
    </Screen>
  );
}

function Body() {
  const t = useTranslations("careerPaths");
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);
  const [changing, setChanging] = useState(false);
  const query = useCareers(role);

  if (query.isPending) return <SkeletonRows count={3} />;
  if (query.isError) {
    return isSignedOut(query.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  const ladder = query.data;
  const steps = ladder.steps ?? [];
  const choosing = changing || ladder.needs_choice;

  return (
    <View style={{ gap: space.lg }}>
      {ladder.anchor ? (
        <View style={{ gap: space.xs }}>
          <Text tone="muted" variant="small">
            {t("startingFrom")}
          </Text>
          <Text variant="lead">{ladder.anchor.job_role}</Text>
          <Text tone="muted">
            {[t("level", { level: ladder.anchor.nsqf_level }), ladder.anchor.sector_name].filter(Boolean).join(" · ")}
          </Text>
          {ladder.anchor_source === "guessed" ? <Notice tone="warning">{t("guessed")}</Notice> : null}
        </View>
      ) : (
        <Text>{t("chooseIntro")}</Text>
      )}

      {choosing ? (
        <RoleSearch
          onChoose={(slug) => {
            setRole(slug);
            setChanging(false);
          }}
          onKeep={ladder.anchor ? () => setChanging(false) : null}
        />
      ) : (
        <Button variant="secondary" label={t("changeRole")} onPress={() => setChanging(true)} />
      )}

      {!ladder.has_skills ? (
        <View style={{ gap: space.sm }}>
          <Text tone="muted">{t("noSkills")}</Text>
          <Button variant="secondary" label={t("addSkills")} onPress={() => router.push("/profile")} />
        </View>
      ) : null}

      {ladder.anchor && ladder.has_skills ? <BudgetField /> : null}

      {ladder.anchor && steps.length === 0 ? <Text tone="muted">{t("noSteps")}</Text> : null}
      {steps.map((step) => (
        <Step key={step.role.slug} step={step} anchorName={ladder.anchor?.job_role ?? ""} />
      ))}
      {steps.length > 0 ? (
        <Text tone="muted" variant="small">
          {t("note")}
        </Text>
      ) : null}
    </View>
  );
}

function RoleSearch({ onChoose, onKeep }: { onChoose: (slug: string) => void; onKeep: (() => void) | null }) {
  const t = useTranslations("careerPaths");
  const [term, setTerm] = useState("");
  const hits = useRoleHits(term);
  return (
    <View style={{ gap: space.sm }}>
      <Text tone="muted">{t("changeIntro")}</Text>
      <TextField label={t("searchLabel")} placeholder={t("searchPlaceholder")} value={term} onChangeText={setTerm} />
      {hits.isSuccess && hits.data.length === 0 ? <Text tone="muted">{t("noRoles")}</Text> : null}
      {(hits.data ?? []).map((hit) => (
        <Button
          key={hit.slug}
          variant="secondary"
          label={hit.job_role}
          accessibilityLabel={`${hit.job_role}${hit.nsqf_level != null ? `, ${t("level", { level: hit.nsqf_level })}` : ""}`}
          onPress={() => onChoose(hit.slug)}
        />
      ))}
      {onKeep ? <Button variant="secondary" label={t("keepRole")} onPress={onKeep} /> : null}
    </View>
  );
}

type StepData = NonNullable<ReturnType<typeof useCareers>["data"]>["steps"] extends (infer S)[] | undefined ? S : never;

function Step({ step, anchorName }: { step: StepData; anchorName: string }) {
  const t = useTranslations("careerPaths");
  const tm = useTranslations("matchesPage");
  const [open, setOpen] = useState(false);
  const missing = mandatoryFirst(step.missing ?? []);
  const courses = step.courses ?? [];

  return (
    <Card>
      <BadgeRow>
        <Badge tone="brand" label={tm("matchScore", { score: step.score })} />
        {step.basis.same_occupation ? <Badge tone="muted" label={t("sameOccupation")} /> : null}
        {step.basis.shared_nco ? <Badge tone="muted" label={t("sharedNco")} /> : null}
      </BadgeRow>
      <Text variant="lead">{step.role.job_role}</Text>
      <Text tone="muted" variant="small">
        {[t("level", { level: step.role.nsqf_level }), step.role.sector_name].filter(Boolean).join(" · ")}
      </Text>
      <Text tone="muted" variant="small">
        {t("basis", { shared: step.basis.shared_standards, total: step.basis.compulsory_count, role: anchorName })}
      </Text>
      <Button
        variant="secondary"
        label={open ? t("hide") : t("whatItTakes")}
        accessibilityLabel={`${open ? t("hide") : t("whatItTakes")}: ${step.role.job_role}`}
        onPress={() => setOpen((v) => !v)}
      />
      {open ? (
        <View style={{ gap: space.md }}>
          {missing.length === 0 ? <Text>{t("nothingMissing")}</Text> : null}
          {missing.map((s) => (
            <View key={`${s.nos_code ?? ""}${s.name}`} style={{ gap: 2 }}>
              <Text>{s.name}</Text>
              {s.is_mandatory ? <Badge tone="warning" label={tm("mandatory")} /> : null}
            </View>
          ))}
          {courses.length > 0 ? <SuggestedCourses courses={courses} /> : null}
          <View style={{ gap: space.xs }}>
            <Text tone="muted" variant="small">
              {t("entryHeading")}
            </Text>
            {step.entry ? (
              <>
                <Text>{`${step.entry.qp_name} · ${step.entry.qp_code}`}</Text>
                {step.entry.education_options.length > 0 ? (
                  <Text tone="muted" variant="small">
                    {t("education", { options: step.entry.education_options.slice(0, 3).join(" · ") })}
                  </Text>
                ) : null}
                {step.entry.lowest_experience_years != null ? (
                  <Text tone="muted" variant="small">
                    {t("experience", { years: step.entry.lowest_experience_years })}
                  </Text>
                ) : null}
              </>
            ) : (
              <Text tone="muted" variant="small">
                {t("noEntry")}
              </Text>
            )}
          </View>
        </View>
      ) : null}
    </Card>
  );
}
