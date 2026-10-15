import { Tabs, useRouter } from "expo-router";
import { useEffect } from "react";
import { useTranslations } from "use-intl";

import { useAccount, useUnreadCount } from "../../src/lib/me-queries";
import { listenForTaps, showForegroundNotifications, usePushRegistration } from "../../src/push";
import { api, useLocale } from "../../src/runtime";
import { useColours } from "../../src/theme";

/**
 * The five places a person can go: home, vacancies, courses, their matches and their own page. Text labels only for
 * now: the icon set is part of store readiness (BL-15.5), and a label that is always readable is
 * better than an icon that has to be learned.
 */
export default function TabsLayout() {
  const t = useTranslations("mobile.tabs");
  const tn = useTranslations("notificationsPage");
  const c = useColours();
  const router = useRouter();
  const locale = useLocale();
  const { signedIn, isJobSeeker } = useAccount();
  const unread = useUnreadCount().data ?? 0;

  // Notifications (ADR-075): shown as a banner while the app is open, this phone registered once the
  // person has allowed them, and a tap on one opens the in-app place it names.
  usePushRegistration(api, locale, { signedIn, isJobSeeker });
  useEffect(() => {
    showForegroundNotifications();
    return listenForTaps((path) => router.push(path as never));
  }, [router]);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: c.brand,
        tabBarInactiveTintColor: c.muted,
        tabBarStyle: { backgroundColor: c.surface, borderTopColor: c.border },
        tabBarLabelStyle: { fontSize: 14, fontWeight: "600" },
        tabBarIcon: () => null,
        tabBarIconStyle: { display: "none" },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("home") }} />
      <Tabs.Screen name="jobs" options={{ title: t("jobs") }} />
      <Tabs.Screen name="courses" options={{ title: t("courses") }} />
      <Tabs.Screen name="matches" options={{ title: t("matches") }} />
      <Tabs.Screen
        name="me"
        options={{
          title: t("me"),
          // The number is in the label, not a badge: this bar has no icons (`tabBarIconStyle`
          // hides them), and a badge hangs off the icon, so it was drawn nowhere (found by running
          // it). A drawn number and a spoken one: the count is part of the tab's name too.
          tabBarLabel: unread > 0 ? `${t("me")} (${unread})` : t("me"),
          tabBarAccessibilityLabel: unread > 0 ? `${t("me")}, ${tn("summary", { unread })}` : t("me"),
        }}
      />
      {/* Standards stay reachable from Home's browse buttons and the search; five labels is what fits. */}
      <Tabs.Screen name="skills" options={{ title: t("standards"), href: null }} />
    </Tabs>
  );
}
