import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { OFFERED_LOCALES } from "../../src/core/locale";
import { useAccount } from "../../src/lib/me-queries";
import { endSession, setLocale, useLocale } from "../../src/runtime";
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
  const tct = useTranslations("contactPage");
  const router = useRouter();
  const { signedIn, isJobSeeker } = useAccount();
  const locale = useLocale();
  const [q, setQ] = useState("");

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
        <Button variant="secondary" label={tct("title")} onPress={() => router.push("/contact")} />
      </View>

      {signedIn ? (
        <>
          <Text>{t("home.signedIn")}</Text>
          {isJobSeeker === false ? <Notice tone="warning">{t("home.organisationNote")}</Notice> : null}
          <Button variant="secondary" label={ta("signOut")} onPress={() => void endSession()} />
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
