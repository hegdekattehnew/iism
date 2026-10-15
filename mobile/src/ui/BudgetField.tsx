import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { parseBudget } from "../core/course-budget";
import { setCourseBudget, useCourseBudget } from "../runtime";
import { space } from "../theme";
import { Button, Notice, Text, TextField } from "./primitives";

/**
 * "What would you pay for a course?" It reorders suggested courses and labels the ones over it
 * (ADR-068): never a filter, never on the profile. Remembered on this phone and forgotten at
 * sign-out (ADR-078), and said so under the field.
 */
export function BudgetField() {
  const t = useTranslations("suggestedCourses");
  const m = useTranslations("mobile.budget");
  const budget = useCourseBudget();
  const [text, setText] = useState(budget === null ? "" : String(budget));
  const [invalid, setInvalid] = useState(false);

  const apply = () => {
    const parsed = parseBudget(text);
    setInvalid(!parsed.ok);
    if (parsed.ok) setCourseBudget(parsed.value);
  };

  return (
    <View style={{ gap: space.sm }}>
      <TextField
        label={t("budgetLabel")}
        value={text}
        onChangeText={(v) => {
          setText(v);
          setInvalid(false);
        }}
        keyboardType="number-pad"
        maxLength={11}
        onSubmitEditing={apply}
      />
      {invalid ? <Notice tone="danger">{m("invalid")}</Notice> : null}
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <View style={{ flex: 1 }}>
          <Button variant="secondary" label={m("apply")} onPress={apply} />
        </View>
        {budget !== null ? (
          <Button
            variant="secondary"
            label={t("budgetClear")}
            onPress={() => {
              setText("");
              setInvalid(false);
              setCourseBudget(null);
            }}
          />
        ) : null}
      </View>
      <Text tone="muted" variant="small">
        {m("note")}
      </Text>
    </View>
  );
}
