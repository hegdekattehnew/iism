import { Stack, useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../src/core/errors";
import { noticePath, noticeText } from "../src/core/notices";
import { shouldAsk } from "../src/core/push";
import { useReadAll, useReadOne, useNoticePages } from "../src/lib/me-queries";
import { useInstantDate } from "../src/lib/months";
import { usePushPermission, registerThisDevice } from "../src/push";
import { api, useLocale } from "../src/runtime";
import { space } from "../src/theme";
import { SeekerGate } from "../src/ui/gate";
import { Badge, BadgeRow, Card, FailureNotice, SkeletonRows } from "../src/ui/list";
import { Button, Notice, Screen, Text } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";

/**
 * Everything the product has told the person, newest first, a page at a time (the web's
 * `/notifications`, Sprint 60). The words come from `core/notices.ts`, the same switch the website
 * uses, so the two cannot disagree about what a notice says. **Asking to send notifications is
 * here, in context**, the first time somebody looks at their updates, and never at launch.
 */
export default function Notices() {
  const t = useTranslations("notificationsPage");
  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <Text variant="title">{t("title")}</Text>
      <SeekerGate prompt={t("signedOut")}>
        <Body />
      </SeekerGate>
    </Screen>
  );
}

function PushPrompt() {
  const t = useTranslations("mobile.push");
  const locale = useLocale();
  const { permission, declined, ask, decline } = usePushPermission();
  if (!shouldAsk({ signedIn: true, isJobSeeker: true, permission, declined })) return null;
  return (
    <Card>
      <Text variant="lead">{t("title")}</Text>
      <Text tone="muted">{t("body")}</Text>
      <Button
        label={t("allow")}
        onPress={() => {
          void ask().then(() => registerThisDevice(api, locale));
        }}
      />
      <Button variant="secondary" label={t("later")} onPress={decline} />
    </Card>
  );
}

function Body() {
  const t = useTranslations("notificationsPage");
  const tn = useTranslations("notices");
  const router = useRouter();
  const day = useInstantDate();
  const pages = useNoticePages();
  const readOne = useReadOne();
  const readAll = useReadAll();

  if (pages.isPending) return <SkeletonRows />;
  if (pages.isError) {
    return isSignedOut(pages.error) ? (
      <SessionExpired />
    ) : (
      <FailureNotice error={pages.error} onRetry={() => void pages.refetch()} />
    );
  }
  const notices = pages.data.pages.flat();
  const unread = notices.filter((n) => !n.read_at).length;
  const failure = readOne.error ?? readAll.error;
  const say = (key: string, values?: Record<string, string | number>) => tn(key, values);

  return (
    <View style={{ gap: space.md }}>
      <PushPrompt />
      {notices.length === 0 ? (
        <Text tone="muted">{t("empty")}</Text>
      ) : (
        <>
          <Text tone="muted">{t("summary", { unread })}</Text>
          {unread > 0 ? (
            <Button
              variant="secondary"
              label={t("markAll")}
              busy={readAll.isPending}
              onPress={() => readAll.mutate()}
            />
          ) : null}
          {failure ? (
            isSignedOut(failure) ? <SessionExpired /> : <Notice tone="danger">{t("actionFailed")}</Notice>
          ) : null}
          {notices.map((n) => {
            const path = noticePath(n);
            const when = day(n.created_at);
            return (
              <Card key={n.id}>
                <BadgeRow>{n.read_at ? null : <Badge tone="brand" label={t("new")} />}</BadgeRow>
                <Text>{noticeText(n, say)}</Text>
                {when ? (
                  <Text tone="muted" variant="small">
                    {when}
                  </Text>
                ) : null}
                {path ? (
                  <Button
                    variant="secondary"
                    label={t("open")}
                    onPress={() => {
                      if (!n.read_at) readOne.mutate(n.id);
                      router.push(path);
                    }}
                  />
                ) : null}
                {n.read_at ? null : (
                  <Button
                    variant="secondary"
                    label={t("markOne")}
                    busy={readOne.isPending && readOne.variables === n.id}
                    onPress={() => readOne.mutate(n.id)}
                  />
                )}
              </Card>
            );
          })}
          {pages.hasNextPage ? (
            <Button
              variant="secondary"
              label={pages.isFetchingNextPage ? t("loading") : t("older")}
              busy={pages.isFetchingNextPage}
              onPress={() => void pages.fetchNextPage()}
            />
          ) : null}
        </>
      )}
    </View>
  );
}
