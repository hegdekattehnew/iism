import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { OFFERED_LOCALES } from "../src/core/locale";
import { signOut } from "../src/core/sign-in";
import { ApiError, readDetail } from "../src/core/errors";
import { api, setLocale, tokens, useLocale, useSignedIn } from "../src/runtime";
import { Button, Notice, Screen, Text } from "../src/ui";

/**
 * Home, for M1: the front door only. Signed out, it offers sign-in. Signed in, it says so and, for
 * an account that holds no job-seeker profile (an organisation owner who signed in on a phone),
 * says where to go instead: v1 is the job seeker's app and an organisation works on the website.
 * The real home (search, matches) arrives in M2 and M3.
 */
export default function Home() {
  const t = useTranslations("mobile");
  const ta = useTranslations("auth");
  const signedIn = useSignedIn();
  const router = useRouter();
  const locale = useLocale();

  // Signed out makes no request that can only answer 401 (the web's rule, Sprint 52).
  const me = useQuery({
    queryKey: ["me"],
    enabled: signedIn,
    queryFn: async () => {
      // Status read before the check: `/auth/me` documents no error body, so on the failure branch
      // openapi-fetch narrows the whole result to `never` (the web's `useOperatorDashboard`).
      const result = await api.GET("/auth/me");
      const status = result.response.status;
      const errorBody: unknown = result.error;
      if (errorBody || !result.data) throw new ApiError(status, readDetail(errorBody));
      return result.data;
    },
  });

  const isJobSeeker = me.data?.memberships?.some((m) => m.tenant.tenant_type === "personal");

  return (
    <Screen>
      <Text variant="title">{t("home.title")}</Text>
      <Text tone="muted">{t("home.subtitle")}</Text>

      {signedIn ? (
        <>
          <Text>{t("home.signedIn")}</Text>
          {me.data && !isJobSeeker ? <Notice tone="warning">{t("home.organisationNote")}</Notice> : null}
          <Button
            variant="secondary"
            label={ta("signOut")}
            onPress={() => void signOut(api, tokens)}
          />
        </>
      ) : (
        <Button label={ta("signInTitle")} onPress={() => router.push("/sign-in")} />
      )}

      <View style={{ flexDirection: "row", gap: 8 }} accessibilityRole="radiogroup">
        {OFFERED_LOCALES.map((code) => (
          <Button
            key={code}
            variant={code === locale ? "primary" : "secondary"}
            label={t(code === "en" ? "common.english" : "common.hindi")}
            onPress={() => setLocale(code)}
          />
        ))}
      </View>
    </Screen>
  );
}
