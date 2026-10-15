import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import { Switch, View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError, isSignedOut } from "../src/core/errors";
import {
  EDUCATION_LEVELS,
  EMPLOYMENT_TYPES,
  LIMITS,
  NOTICE_PERIODS,
  SALARY_DIGITS,
  basicsFrom,
  preferencesBody,
  preferencesFrom,
  profileBody,
  type BasicsForm,
  type PreferencesForm,
  type PreferencesProblem,
} from "../src/core/profile";
import { COLLECTIONS, type Collection } from "../src/core/profile-sections";
import { useProfile, useRemoveSkill, useUpdateProfile } from "../src/lib/me-queries";
import { space } from "../src/theme";
import { SeekerGate } from "../src/ui/gate";
import { Chip, ChipRow, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text, TextField } from "../src/ui/primitives";
import { RolePicker } from "../src/ui/RolePicker";
import { SessionExpired } from "../src/ui/session";

/**
 * The profile, on a phone: who you are in a few fields, and what you can do. The skills are the part
 * that moves a match score, so the role picker comes first and the basics after. Experience,
 * education history, certificates and languages are on the website (BL-15.3 does not ask for them).
 */
export default function Profile() {
  const t = useTranslations("profilePage");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <Text variant="title">{t("title")}</Text>
      <SeekerGate prompt={t("signInPrompt")}>
        <Body />
      </SeekerGate>
    </Screen>
  );
}

function Body() {
  const t = useTranslations("profilePage");
  const query = useProfile();
  const remove = useRemoveSkill();

  if (query.isPending) return <SkeletonRows count={3} />;
  if (query.isError) {
    return isSignedOut(query.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  const profile = query.data;
  const skills = profile.skills ?? [];
  const held = new Set(skills.map((s) => s.skill.slug));
  const next = profile.completeness?.missing?.[0];

  return (
    <View style={{ gap: space.xl }}>
      <View style={{ gap: space.xs }}>
        <Text variant="lead">{t("completeness", { percent: profile.completeness?.percent ?? 0 })}</Text>
        {next ? <Text tone="muted">{t("completeNext", { what: t(`field.${next}`) })}</Text> : null}
      </View>

      <View style={{ gap: space.md }}>
        <Text variant="lead">{t("skillsTitle")}</Text>
        <Text tone="muted">{t("skillsSubtitle")}</Text>
        <RolePicker held={held} />
        {skills.length === 0 ? <Text tone="muted">{t("noSkills")}</Text> : null}
        {skills.map((s) => (
          <View key={s.skill.slug} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <View style={{ flex: 1 }}>
              <Text>{s.skill.name}</Text>
              <Text tone="muted" variant="small">
                {t("proficiency", { n: s.proficiency })}
              </Text>
            </View>
            <Button
              variant="secondary"
              label={t("remove")}
              accessibilityLabel={`${t("remove")}: ${s.skill.name}`}
              busy={remove.isPending && remove.variables === s.skill.slug}
              onPress={() => remove.mutate(s.skill.slug)}
            />
          </View>
        ))}
        {remove.isError ? (
          isSignedOut(remove.error) ? (
            <SessionExpired />
          ) : (
            <Notice tone="danger">
              {remove.error instanceof ApiError && remove.error.detail ? remove.error.detail : t("errors.skillWrite")}
            </Notice>
          )
        ) : null}
        <Text tone="muted" variant="small">
          {t("sourceNote")}
        </Text>
      </View>

      <Sections profile={profile as unknown as Record<string, unknown[] | undefined>} />

      {/* Keyed on the loaded profile, so a refetch can never overwrite what is being typed. */}
      <Basics key={profile.id} initial={basicsFrom(profile)} />

      <Preferences key={`${profile.id}-prefs`} initial={preferencesFrom(profile)} />
    </View>
  );
}

function Basics({ initial }: { initial: BasicsForm }) {
  const t = useTranslations("profilePage");
  const f = useTranslations("profilePage.fields");
  const [form, setForm] = useState(initial);
  const [badYears, setBadYears] = useState(false);
  const save = useUpdateProfile();
  const set = <K extends keyof BasicsForm>(key: K, value: BasicsForm[K]) => setForm((cur) => ({ ...cur, [key]: value }));

  const submit = () => {
    const body = profileBody(form);
    setBadYears(body === null);
    if (body) save.mutate(body);
  };

  return (
    <View style={{ gap: space.md }}>
      <TextField label={f("fullName")} value={form.fullName} onChangeText={(v) => set("fullName", v)} maxLength={LIMITS.fullName} />
      <TextField
        label={t("headline")}
        placeholder={t("headlinePlaceholder")}
        value={form.headline}
        onChangeText={(v) => set("headline", v)}
        maxLength={LIMITS.headline}
      />
      <TextField label={t("state")} value={form.state} onChangeText={(v) => set("state", v)} maxLength={LIMITS.place} />
      <TextField label={t("district")} value={form.district} onChangeText={(v) => set("district", v)} maxLength={LIMITS.place} />
      <TextField
        label={t("experience")}
        value={form.years}
        onChangeText={(v) => set("years", v)}
        keyboardType="number-pad"
        maxLength={2}
      />
      <Text tone="muted" variant="small">
        {t("education")}
      </Text>
      <ChipRow>
        {EDUCATION_LEVELS.map((level) => (
          <Chip
            key={level}
            label={t(`educationLevel.${level}`)}
            selected={form.education === level}
            onPress={() => set("education", form.education === level ? null : level)}
          />
        ))}
      </ChipRow>
      {badYears ? <Notice tone="danger">{t("errors.generic")}</Notice> : null}
      {save.isError ? (
        isSignedOut(save.error) ? (
          <SessionExpired />
        ) : (
          // The server names the field and the rule; the generic line is for a failure that carried nothing.
          <Notice tone="danger">{save.error instanceof ApiError && save.error.detail ? save.error.detail : t("errors.generic")}</Notice>
        )
      ) : null}
      <Button label={save.isPending ? t("saving") : t("save")} busy={save.isPending} onPress={submit} />
      {save.isSuccess && !save.isError ? <Text tone="muted">{t("saved")}</Text> : null}
    </View>
  );
}

/** The six history sections, each one screen (`profile/[section]`), with how many entries it holds. */
function Sections({ profile }: { profile: Record<string, unknown[] | undefined> }) {
  const s = useTranslations("mobile.profileSections");
  const router = useRouter();
  return (
    <View style={{ gap: space.md }}>
      <Text variant="lead">{s("title")}</Text>
      <Text tone="muted">{s("intro")}</Text>
      {COLLECTIONS.map((c: Collection) => {
        const count = profile[c]?.length ?? 0;
        return (
          <Button
            key={c}
            variant="secondary"
            label={`${s(`names.${c}`)} · ${s("count", { count })}`}
            onPress={() => router.push(`/profile/${c}`)}
          />
        );
      })}
    </View>
  );
}

/** Salary, notice period, work type, willingness to move and whether to be told of new vacancies. */
function Preferences({ initial }: { initial: PreferencesForm }) {
  const s = useTranslations("mobile.profileSections");
  const sp = useTranslations("mobile.profileSections.preferencesProblem");
  const t = useTranslations("profilePage");
  const f = useTranslations("profilePage.fields");
  const tj = useTranslations("jobsPage.employmentType");
  const tn = useTranslations("profilePage.notice");
  const [form, setForm] = useState(initial);
  const [problem, setProblem] = useState<PreferencesProblem | null>(null);
  const save = useUpdateProfile();
  const set = <K extends keyof PreferencesForm>(key: K, value: PreferencesForm[K]) =>
    setForm((cur) => ({ ...cur, [key]: value }));

  const submit = () => {
    const built = preferencesBody(form);
    setProblem(built.ok ? null : built.problem);
    if (built.ok) save.mutate(built.body);
  };

  return (
    <View style={{ gap: space.md }}>
      <Text variant="lead">{s("preferencesTitle")}</Text>
      <TextField
        label={f("salaryMin")}
        value={form.salaryMin}
        onChangeText={(v) => set("salaryMin", v)}
        keyboardType="number-pad"
        maxLength={SALARY_DIGITS + 3}
      />
      <TextField
        label={f("salaryMax")}
        value={form.salaryMax}
        onChangeText={(v) => set("salaryMax", v)}
        keyboardType="number-pad"
        maxLength={SALARY_DIGITS + 3}
      />
      <Text tone="muted" variant="small">
        {f("employmentType")}
      </Text>
      <ChipRow>
        {EMPLOYMENT_TYPES.map((type) => (
          <Chip
            key={type}
            label={tj(type)}
            selected={form.employment === type}
            onPress={() => set("employment", form.employment === type ? null : type)}
          />
        ))}
      </ChipRow>
      <Text tone="muted" variant="small">
        {f("noticePeriod")}
      </Text>
      <ChipRow>
        {NOTICE_PERIODS.map((n) => (
          <Chip
            key={n}
            label={tn(n)}
            selected={form.notice === n}
            onPress={() => set("notice", form.notice === n ? null : n)}
          />
        ))}
      </ChipRow>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <Switch value={form.relocate} onValueChange={(v) => set("relocate", v)} accessibilityLabel={f("relocate")} />
        <View style={{ flex: 1 }}>
          <Text>{f("relocate")}</Text>
        </View>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
        <Switch value={form.alerts} onValueChange={(v) => set("alerts", v)} accessibilityLabel={f("alertsOn")} />
        <View style={{ flex: 1 }}>
          <Text>{f("alertsOn")}</Text>
        </View>
      </View>
      {problem ? <Notice tone="danger">{sp(problem)}</Notice> : null}
      {save.isError ? (
        isSignedOut(save.error) ? (
          <SessionExpired />
        ) : (
          <Notice tone="danger">{save.error instanceof ApiError && save.error.detail ? save.error.detail : t("errors.generic")}</Notice>
        )
      ) : null}
      <Button
        label={save.isPending ? t("saving") : t("save")}
        // Two forms on this screen each end in "Save": a screen reader must say which one.
        accessibilityLabel={`${save.isPending ? t("saving") : t("save")}: ${s("preferencesTitle")}`}
        busy={save.isPending}
        onPress={submit}
      />
      {save.isSuccess && !save.isError ? <Text tone="muted">{t("saved")}</Text> : null}
    </View>
  );
}
