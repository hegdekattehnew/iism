import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { consentPrompt } from "../../src/core/account";
import { useAccount, useProfile, useUnreadCount } from "../../src/lib/me-queries";
import { endSession, useSignedIn } from "../../src/runtime";
import { space } from "../../src/theme";
import { AppearanceChooser } from "../../src/ui/AppearanceChooser";
import { SeekerGate } from "../../src/ui/gate";
import { Card, ListRow, RowGroup } from "../../src/ui/list";
import { Button, Notice, Screen, Text } from "../../src/ui/primitives";

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
      {/* Not behind the gate: it asks nothing of the server and a visitor may prefer the dark. */}
      <AppearanceChooser />
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
  const tcp = useTranslations("careerPaths");
  const router = useRouter();
  const profile = useProfile();
  const unread = useUnreadCount().data ?? 0;
  const account = useAccount().query.data;
  const prompt = account ? consentPrompt(account) : null;
  const p = profile.data;

  return (
    <View style={{ gap: space.md }}>
      <Card onPress={() => router.push("/profile")} label={tp("title")}>
        <Text variant="lead">{p?.full_name || t("me.unnamed")}</Text>
        {p?.headline ? <Text tone="muted">{p.headline}</Text> : null}
        {p ? <Text tone="muted">{tp("completeness", { percent: p.completeness?.percent ?? 0 })}</Text> : null}
        <Text variant="small">{tp("title")}</Text>
      </Card>
      {/* Two groups, each with an icon per row (Sprint 82, BL-19.22): what the person did, then the
          account and the way to reach us. The unread count is drawn in a pill and spoken in the name. */}
      <RowGroup>
        <ListRow
          icon="Bell"
          title={tn("title")}
          count={unread}
          accessibilityLabel={unread > 0 ? `${tn("title")}: ${t("me.updatesCount", { count: unread })}` : undefined}
          onPress={() => router.push("/notices")}
        />
        <ListRow icon="Inbox" title={ta("pageTitle")} onPress={() => router.push("/applications")} />
        <ListRow icon="Bookmark" title={ta("savedPageTitle")} onPress={() => router.push("/saved")} />
        <ListRow icon="GraduationCap" title={tc("pageTitle")} onPress={() => router.push("/interests")} />
        <ListRow icon="Navigation" title={tcp("title")} onPress={() => router.push("/careers")} />
      </RowGroup>
      <RowGroup>
        <ListRow icon="ShieldCheck" title={ta2("title")} onPress={() => router.push("/account")} />
        <ListRow icon="Info" title={tct("title")} onPress={() => router.push("/contact")} />
      </RowGroup>
      {/* After everything else, never above it: it arrives when the account does (Sprint 72). A stale
          notice asks and blocks nothing; a withdrawal says the account is paused. */}
      {prompt ? (
        <Notice tone={prompt === "paused" ? "warning" : "info"}>
          {prompt === "paused" ? ta2("bannerPausedBody") : ta2("bannerStaleBody")}
        </Notice>
      ) : null}
    </View>
  );
}
