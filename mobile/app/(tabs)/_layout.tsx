import type { ColorValue } from "react-native";
import { Tabs, useRouter } from "expo-router";
import { useEffect } from "react";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { useAccount, useUnreadCount } from "../../src/lib/me-queries";
import { listenForTaps, showForegroundNotifications, usePushRegistration } from "../../src/push";
import { api, useLocale } from "../../src/runtime";
import { useColours } from "../../src/theme";
import { Icon, type IconName } from "../../src/ui/icon";

/** dp above the bottom inset: a 24 dp icon, a 14 pt label and a little air, and at least the 48 dp floor. */
const TAB_BAR_HEIGHT = 64;

const TAB_ICONS: Record<string, IconName> = {
  index: "Home",
  jobs: "Briefcase",
  courses: "BookOpen",
  matches: "Target",
  me: "User",
};

/**
 * An icon in the tab's tint; it sits beside the label, so it is hidden from a screen reader. The
 * navigator hands over a `ColorValue`; every colour here is a hex token, so it is a string.
 */
function tabIcon(name: IconName) {
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <Icon name={name} color={String(color)} size={size} />;
  }
  return TabIcon;
}

/**
 * The five places a person can go: home, vacancies, courses, their matches and their own page.
 * Each has an icon **and** its word (Sprint 82, BL-19.21): the icon is found at a glance, the label
 * is what makes it unambiguous, and a label that is always readable is never dropped.
 */
export default function TabsLayout() {
  const t = useTranslations("mobile.tabs");
  const tn = useTranslations("notificationsPage");
  const c = useColours();
  const insets = useSafeAreaInsets();
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
        // An icon over a 14-point word does not fit the navigator's 49 dp default (the words were cut
        // off in the browser run), so the bar is taller, and still clears the home indicator.
        tabBarStyle: {
          backgroundColor: c.surface,
          borderTopColor: c.border,
          height: TAB_BAR_HEIGHT + insets.bottom,
          paddingTop: 6,
          paddingBottom: insets.bottom + 6,
        },
        tabBarLabelStyle: { fontSize: 14, fontWeight: "600" },
        tabBarBadgeStyle: { backgroundColor: c.brand, color: c.brandContrast, fontSize: 12 },
      }}
    >
      <Tabs.Screen name="index" options={{ title: t("home"), tabBarIcon: tabIcon(TAB_ICONS.index) }} />
      <Tabs.Screen name="jobs" options={{ title: t("jobs"), tabBarIcon: tabIcon(TAB_ICONS.jobs) }} />
      <Tabs.Screen name="courses" options={{ title: t("courses"), tabBarIcon: tabIcon(TAB_ICONS.courses) }} />
      <Tabs.Screen name="matches" options={{ title: t("matches"), tabBarIcon: tabIcon(TAB_ICONS.matches) }} />
      <Tabs.Screen
        name="me"
        options={{
          title: t("me"),
          tabBarIcon: tabIcon(TAB_ICONS.me),
          // A drawn number (the badge hangs off the icon now there is one) and a spoken one: the
          // count is part of the tab's name, and the label stays the plain word. Capped at 99.
          tabBarBadge: unread > 0 ? (unread > 99 ? "99+" : unread) : undefined,
          tabBarAccessibilityLabel: unread > 0 ? `${t("me")}, ${tn("summary", { unread })}` : t("me"),
        }}
      />
      {/* Standards stay reachable from Home's browse buttons and the search; five labels is what fits. */}
      <Tabs.Screen name="skills" options={{ title: t("standards"), href: null }} />
    </Tabs>
  );
}
