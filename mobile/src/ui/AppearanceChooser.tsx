import { View } from "react-native";
import { useTranslations } from "use-intl";

import { THEME_PREFERENCES, type ThemePreference } from "../core/theme-preference";
import { setThemePreference } from "../runtime";
import { space } from "../theme";
import { useThemePreference } from "../theme/preference";
import { Chip } from "./list";
import { Text } from "./primitives";

const LABEL: Record<ThemePreference, "system" | "light" | "dark"> = { system: "system", light: "light", dark: "dark" };

/**
 * Light, dark, or follow the phone (Sprint 78, BL-19.8, ADR-087): three chips, the chosen one
 * selected (a name and a state, not a colour alone), each at the 48 dp floor. It makes no request
 * and needs no account, so it sits on the Me tab for a signed-out visitor too; what it keeps is
 * forgotten when a signed-in session ends (`forgetPersistedCache`).
 */
export function AppearanceChooser() {
  const t = useTranslations("mobile.appearance");
  const choice = useThemePreference();
  return (
    <View style={{ gap: space.sm }}>
      <Text variant="small" tone="muted">
        {t("title")}
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
        {THEME_PREFERENCES.map((value) => (
          <Chip key={value} label={t(LABEL[value])} selected={choice === value} onPress={() => setThemePreference(value)} />
        ))}
      </View>
    </View>
  );
}
