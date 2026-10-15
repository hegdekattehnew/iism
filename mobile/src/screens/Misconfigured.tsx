import { Linking } from "react-native";
import { useTranslations } from "use-intl";

import { STORE_URL } from "../config";
import { Button, Screen, Text } from "../ui";

/**
 * Shown instead of the app when a **release** build carries no HTTPS origin, or a local one
 * (`core/release.ts`, ADR-077). The reason is not shown (a person cannot act on "api-insecure"); it
 * is logged by the root layout. The one useful thing is to reinstall from the store.
 */
export function Misconfigured() {
  const t = useTranslations("mobile.misconfigured");
  const u = useTranslations("mobile.update");
  return (
    <Screen>
      <Text variant="title">{t("title")}</Text>
      <Text>{t("body")}</Text>
      <Button label={u("openStore")} onPress={() => void Linking.openURL(STORE_URL)} />
    </Screen>
  );
}
