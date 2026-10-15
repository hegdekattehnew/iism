import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { space } from "../theme";
import { Button, Notice } from "./primitives";

/**
 * **401 and 403 are opposite answers** (the web's rule since Sprint 18). 403 is "this is not yours";
 * 401 is "you are signed out", which is not a permission problem and must not read as one. A write
 * that comes back 401 shows this, with the way back in, instead of a generic failure.
 */
export function SessionExpired() {
  const t = useTranslations("auth");
  const router = useRouter();
  return (
    <View style={{ gap: space.sm }}>
      <Notice tone="warning">{t("sessionExpired")}</Notice>
      <Button variant="secondary" label={t("signInAgain")} onPress={() => router.push("/sign-in")} />
    </View>
  );
}
