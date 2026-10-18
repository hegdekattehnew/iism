import { useRouter } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { applicationsWithNews } from "../core/home";
import { useApplications, useMatches, useProfile, useUnreadCount } from "../lib/me-queries";
import { space } from "../theme";
import { Badge, BadgeRow, Card, ListRow, RowGroup, SkeletonRows } from "./list";
import { MatchSentence } from "./match";
import { Button, Text } from "./primitives";

/** The height the block is held at while it loads, and the least it is once loaded (dp). Measured on the seeded demo account. */
const HOME_PLACE = 330;

/**
 * A signed-in job seeker's home (Sprint 70, UI-19): **their** things, not the signed-out page with
 * "You are signed in" added. The best match with its sentence and a way into it, how complete the
 * profile is and the next step, new updates, and the applications an employer has acted on lately.
 *
 * Every figure is one the person's other screens already read (`useMatches`, `useProfile`,
 * `useUnreadCount`, `useApplications`), so this adds no request the app did not already make, and it
 * is mounted only for an account that holds a job-seeker profile: an organisation-only account makes
 * no personal request (`Home` decides, and `useSeeker` underneath would refuse anyway). Each block is
 * absent when it has nothing to say, and a placeholder while it does not yet know: a "0" shown early
 * would be a claim nobody checked.
 *
 * Applying is **not** offered here. The summary a match list carries has no employer name, and the
 * consent step names the employer ("this sends your name … to Apollo Care"), so the one place that
 * knows it, the match screen, is one tap away.
 */
export function SignedInHome() {
  const t = useTranslations("mobile");
  const tm = useTranslations("matchesPage");
  const tp = useTranslations("profilePage");
  const tn = useTranslations("notificationsPage");
  const router = useRouter();
  const matches = useMatches();
  const profile = useProfile();
  const unreadQuery = useUnreadCount();
  const unread = unreadQuery.data ?? 0;
  const applications = useApplications();
  // Read once when the screen opens; a render must give the same answer twice.
  const [openedAt] = useState(() => Date.now());

  // **One block, shown when every part has answered** (Sprint 83): the four used to land one by one
  // above the search box and each pushed it down (layout shift 0.17 to 0.22 on a phone). Held at a
  // height of its own meanwhile, and never shorter than that once it arrives, so the usual account
  // moves nothing and an unusually short one moves things once, not four times.
  const settled = [matches, profile, applications, unreadQuery].every((q) => !q.isPending);
  if (!settled) return <SkeletonRows count={1} height={HOME_PLACE} />;

  const top = matches.data?.items[0];
  const news = applications.data ? applicationsWithNews(applications.data, openedAt) : 0;
  const completeness = profile.data?.completeness;
  const next = completeness?.missing?.[0];
  const sentence = completeness ? tp("completeness", { percent: completeness.percent ?? 0 }) : null;

  return (
    <View testID="signed-in-home" style={{ gap: space.lg, minHeight: HOME_PLACE }}>
      {top ? (
        <View style={{ gap: space.sm }}>
          <Text tone="muted" variant="small">
            {t("home.topMatch")}
          </Text>
          <Card onPress={() => router.push(`/match/${top.job.slug}`)} label={top.job.title}>
            <BadgeRow>
              <Badge tone="brand" label={tm("matchScore", { score: top.score })} />
            </BadgeRow>
            <Text variant="lead">{top.job.title}</Text>
            <MatchSentence match={top} />
          </Card>
          <Button label={t("home.openMatch")} onPress={() => router.push(`/match/${top.job.slug}`)} />
        </View>
      ) : matches.data && !matches.data.has_skills ? (
        <View style={{ gap: space.sm }}>
          <Text tone="muted">{tm("noSkills")}</Text>
          <Button label={tm("addSkills")} onPress={() => router.push("/profile")} />
        </View>
      ) : matches.data ? (
        <Text tone="muted">{t("home.noTopMatch")}</Text>
      ) : null}

      {/* What needs a look, as rows: the profile and its next step, new updates, applications with news. */}
      {completeness || unread > 0 || news > 0 ? (
        <RowGroup>
          {completeness && sentence ? (
            <ListRow
              icon="User"
              title={sentence}
              subtitle={next ? tp("completeNext", { what: tp(`field.${next}`) }) : undefined}
              accessibilityLabel={next ? `${sentence}. ${tp("completeNext", { what: tp(`field.${next}`) })}` : sentence}
              onPress={() => router.push("/profile")}
            />
          ) : null}
          {unread > 0 ? (
            <ListRow
              icon="Bell"
              title={tn("title")}
              count={unread}
              accessibilityLabel={`${tn("title")}: ${t("me.updatesCount", { count: unread })}`}
              onPress={() => router.push("/notices")}
            />
          ) : null}
          {news > 0 ? (
            <ListRow
              icon="Inbox"
              title={t("home.applicationsNews", { count: news })}
              onPress={() => router.push("/applications")}
            />
          ) : null}
        </RowGroup>
      ) : null}
    </View>
  );
}
