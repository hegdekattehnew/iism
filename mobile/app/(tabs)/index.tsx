import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { OFFERED_LOCALES } from "../../src/core/locale";
import { ApiError, readDetail } from "../../src/core/errors";
import { signOut } from "../../src/core/sign-in";
import { api, setLocale, tokens, useLocale, useSignedIn } from "../../src/runtime";
import { Button, Notice, Screen, SearchBox, Text } from "../../src/ui";

/**
 * Home: where to start. A search box, three ways to browse, and sign-in. Signed in, it says so and,
 * for an account that holds no job-seeker profile (an organisation owner who signed in on a phone),
 * says where to go instead: v1 is the job seeker's app and an organisation works on the website.
 */
export default function Home() {
  const t = useTranslations("mobile");
  const ta = useTranslations("auth");
  const ts = useTranslations("searchPage");
  const router = useRouter();
  const signedIn = useSignedIn();
  const locale = useLocale();
  const [q, setQ] = useState("");

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
  const search = () => {
    const term = q.trim();
    if (term) router.push({ pathname: "/search", params: { q: term } });
  };

  return (
    <Screen>
      <Text variant="title">{t("home.title")}</Text>
      <Text tone="muted">{t("home.subtitle")}</Text>

      <SearchBox value={q} onChangeText={setQ} placeholder={ts("placeholder")} onSubmit={search} />
      <Button label={ts("submit")} onPress={search} disabled={q.trim().length === 0} />

      <View style={{ gap: 8 }}>
        <Button variant="secondary" label={t("home.browseJobs")} onPress={() => router.navigate("/jobs")} />
        <Button variant="secondary" label={t("home.browseCourses")} onPress={() => router.navigate("/courses")} />
        <Button variant="secondary" label={t("home.browseStandards")} onPress={() => router.navigate("/skills")} />
      </View>

      {signedIn ? (
        <>
          <Text>{t("home.signedIn")}</Text>
          {me.data && !isJobSeeker ? <Notice tone="warning">{t("home.organisationNote")}</Notice> : null}
          <Button variant="secondary" label={ta("signOut")} onPress={() => void signOut(api, tokens)} />
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
