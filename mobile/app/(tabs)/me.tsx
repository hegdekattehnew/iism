import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { useProfile, useUnreadCount } from "../../src/lib/me-queries";
import { endSession, useSignedIn } from "../../src/runtime";
import { space } from "../../src/theme";
import { SeekerGate } from "../../src/ui/gate";
import { Card } from "../../src/ui/list";
import { Button, Screen, Text } from "../../src/ui/primitives";

/**
 * Where a signed-in person's own things are: their profile and how complete it is, their
 * applications, the vacancies they saved and the courses they asked about. Signed out, it is the
 * way in and makes no request.
 */
export default function Me() {
  const t = useTranslations("mobile");
  const ta = useTranslations("auth");
  const signedIn = useSignedIn();
  return (
    <Screen>
      <Text variant="title">{t("me.title")}</Text>
      <SeekerGate prompt={t("me.signInPrompt")}>
        <Menu />
      </SeekerGate>
      {signedIn ? (
        <Button variant="secondary" label={ta("signOut")} onPress={() => void endSession()} />
      ) : null}
    </Screen>
  );
}

function Menu() {
  const t = useTranslations("mobile");
  const tp = useTranslations("profilePage");
  const ta = useTranslations("applications");
  const tc = useTranslations("courseInterest");
  const tn = useTranslations("notificationsPage");
  const ta2 = useTranslations("account");
  const tct = useTranslations("contactPage");
  const router = useRouter();
  const profile = useProfile();
  const unread = useUnreadCount().data ?? 0;
  const p = profile.data;

  return (
    <View style={{ gap: space.md }}>
      <Card onPress={() => router.push("/profile")} label={tp("title")}>
        <Text variant="lead">{p?.full_name || t("me.unnamed")}</Text>
        {p?.headline ? <Text tone="muted">{p.headline}</Text> : null}
        {p ? <Text tone="muted">{tp("completeness", { percent: p.completeness?.percent ?? 0 })}</Text> : null}
        <Text variant="small">{tp("title")}</Text>
      </Card>
      <Button
        variant="secondary"
        label={unread > 0 ? `${tn("title")} (${unread})` : tn("title")}
        accessibilityLabel={unread > 0 ? `${tn("title")}: ${t("me.updatesCount", { count: unread })}` : undefined}
        onPress={() => router.push("/notices")}
      />
      <Button variant="secondary" label={ta("pageTitle")} onPress={() => router.push("/applications")} />
      <Button variant="secondary" label={ta("savedPageTitle")} onPress={() => router.push("/saved")} />
      <Button variant="secondary" label={tc("pageTitle")} onPress={() => router.push("/interests")} />
      <Button variant="secondary" label={ta2("title")} onPress={() => router.push("/account")} />
      <Button variant="secondary" label={tct("title")} onPress={() => router.push("/contact")} />
    </View>
  );
}
