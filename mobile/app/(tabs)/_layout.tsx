import { Tabs } from "expo-router";
import { useTranslations } from "use-intl";

import { useColours } from "../../src/theme";

/**
 * The five places a person can go: home, vacancies, courses, their matches and their own page. Text labels only for
 * now: the icon set is part of store readiness (BL-15.5), and a label that is always readable is
 * better than an icon that has to be learned.
 */
export default function TabsLayout() {
  const t = useTranslations("mobile.tabs");
  const c = useColours();
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
      <Tabs.Screen name="me" options={{ title: t("me") }} />
      {/* Standards stay reachable from Home's browse buttons and the search; five labels is what fits. */}
      <Tabs.Screen name="skills" options={{ title: t("standards"), href: null }} />
    </Tabs>
  );
}
