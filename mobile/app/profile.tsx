import { Stack } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { ApiError, isSignedOut } from "../src/core/errors";
import {
  EDUCATION_LEVELS,
  LIMITS,
  basicsFrom,
  profileBody,
  type BasicsForm,
} from "../src/core/profile";
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

      {/* Keyed on the loaded profile, so a refetch can never overwrite what is being typed. */}
      <Basics key={profile.id} initial={basicsFrom(profile)} />
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
