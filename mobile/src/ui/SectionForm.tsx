import { useState } from "react";
import { Switch, View } from "react-native";
import { useTranslations } from "use-intl";

import {
  FIELDS,
  FIELD_LABEL,
  bodyFromForm,
  isVisible,
  monthKey,
  optionKey,
  problemFor,
  setFlag,
  yearKey,
  type Collection,
  type Field,
  type Form,
  type Problem,
} from "../core/profile-sections";
import { MIN_TOUCH, space } from "../theme";
import { Chip, ChipRow } from "./list";
import { Button, Notice, Text, TextField } from "./primitives";

/**
 * One entry of any of the six sections, driven by the table in `core/profile-sections.ts`: the
 * fields, their limits and the rules that span them are all there, so this file knows no section.
 * A problem is shown beside its field before a request is made; the server's own sentence is shown
 * by the screen when it still refuses.
 */
export function SectionForm({
  collection,
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  collection: Collection;
  initial: Form;
  busy: boolean;
  error: string | null;
  onSubmit: (body: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("profilePage");
  const f = useTranslations("profilePage.fields");
  const s = useTranslations("mobile.profileSections");
  const p = useTranslations("mobile.sectionProblem");
  const [form, setForm] = useState<Form>(initial);
  const [problems, setProblems] = useState<Problem[]>([]);

  const set = (patch: Form) => setForm((cur) => ({ ...cur, ...patch }));
  const label = (field: Field) => (field.key === "education_level" ? t("education") : f(FIELD_LABEL[field.key]));
  const problem = (field: Field) => {
    const code = problemFor(problems, field.key);
    return code ? <Text tone="danger" variant="small">{p(code)}</Text> : null;
  };

  const submit = () => {
    const built = bodyFromForm(collection, form);
    setProblems(built.ok ? [] : built.problems);
    if (built.ok) onSubmit(built.body);
  };

  return (
    <View style={{ gap: space.md }}>
      {FIELDS[collection].filter((field) => isVisible(field, form)).map((field) => {
        switch (field.kind) {
          case "text":
            return (
              <View key={field.key} style={{ gap: 2 }}>
                <TextField
                  label={label(field)}
                  value={String(form[field.key] ?? "")}
                  onChangeText={(v) => set({ [field.key]: v })}
                  maxLength={field.max}
                  multiline={field.long}
                />
                {problem(field)}
              </View>
            );
          case "year":
            return (
              <View key={field.key} style={{ gap: 2 }}>
                <TextField
                  label={label(field)}
                  value={String(form[field.key] ?? "")}
                  onChangeText={(v) => set({ [field.key]: v })}
                  keyboardType="number-pad"
                  maxLength={4}
                />
                {problem(field)}
              </View>
            );
          case "date":
            return (
              <View key={field.key} style={{ gap: 2 }}>
                <Text variant="small">{label(field)}</Text>
                <View style={{ flexDirection: "row", gap: space.sm }}>
                  <View style={{ flex: 1 }}>
                    <TextField
                      label={s("month")}
                      value={String(form[monthKey(field.key)] ?? "")}
                      onChangeText={(v) => set({ [monthKey(field.key)]: v })}
                      keyboardType="number-pad"
                      maxLength={2}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <TextField
                      label={s("year")}
                      value={String(form[yearKey(field.key)] ?? "")}
                      onChangeText={(v) => set({ [yearKey(field.key)]: v })}
                      keyboardType="number-pad"
                      maxLength={4}
                    />
                  </View>
                </View>
                {problem(field)}
              </View>
            );
          case "flag":
            return (
              <View
                key={field.key}
                style={{ minHeight: MIN_TOUCH, flexDirection: "row", alignItems: "center", gap: space.md }}
              >
                <Switch
                  value={form[field.key] === true}
                  onValueChange={(v) => setForm((cur) => setFlag(collection, cur, field.key, v))}
                  accessibilityLabel={label(field)}
                />
                <View style={{ flex: 1 }}>
                  <Text>{label(field)}</Text>
                </View>
              </View>
            );
          case "choice":
            return (
              <View key={field.key} style={{ gap: space.xs }}>
                <Text variant="small">{label(field)}</Text>
                <ChipRow>
                  {field.options.map((option) => (
                    <Chip
                      key={option}
                      label={t(optionKey(field.key, option))}
                      selected={form[field.key] === option}
                      onPress={() =>
                        set({ [field.key]: form[field.key] === option && !field.required ? "" : option })
                      }
                    />
                  ))}
                </ChipRow>
                {problem(field)}
              </View>
            );
        }
      })}
      {FIELDS[collection].some((field) => field.kind === "date") ? (
        <Text tone="muted" variant="small">
          {s("dateNote")}
        </Text>
      ) : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <Button label={busy ? s("saving") : s("save")} busy={busy} onPress={submit} />
      <Button variant="secondary" label={s("cancel")} onPress={onCancel} />
    </View>
  );
}
