import { Stack, useLocalSearchParams } from "expo-router";
import { Linking } from "react-native";
import { useTranslations } from "use-intl";

import { WEB_BASE_URL } from "../../src/config";
import { useLocale } from "../../src/runtime";
import { Button, Notice, Screen, Text } from "../../src/ui/primitives";

/**
 * An invitation to join an **organisation**. This app is the job seeker's (ADR-072): an organisation
 * works on the website, so this never accepts anything. It says so and hands the invitation to the
 * browser, where the token is what the website reads. The token is not logged or stored here.
 */
export default function Invite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const t = useTranslations("mobile.invite");
  const locale = useLocale();
  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <Text variant="title">{t("title")}</Text>
      <Notice tone="info">{t("body")}</Notice>
      <Button
        label={t("open")}
        onPress={() => void Linking.openURL(`${WEB_BASE_URL}/${locale}/invite/${encodeURIComponent(token)}`)}
      />
    </Screen>
  );
}
