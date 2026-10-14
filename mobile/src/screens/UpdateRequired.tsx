import { Linking } from "react-native";
import { useTranslations } from "use-intl";

import { STORE_URL } from "../config";
import { Button, Screen, Text } from "../ui";

/**
 * Shown instead of the app when the API answers **426** (ADR-072). It names no version number a
 * person would not understand and offers the one thing they can do.
 */
export function UpdateRequired({ minVersion }: { minVersion?: string | null }) {
  const t = useTranslations("mobile.update");
  return (
    <Screen>
      <Text variant="title">{t("title")}</Text>
      <Text>{t("body")}</Text>
      {minVersion ? <Text tone="muted">{minVersion}</Text> : null}
      <Button label={t("openStore")} onPress={() => void Linking.openURL(STORE_URL)} />
    </Screen>
  );
}
