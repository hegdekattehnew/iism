import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import { Linking, Share, View } from "react-native";
import { useTranslations } from "use-intl";

import { WEB_BASE_URL } from "../src/config";
import { canDelete, consentOf } from "../src/core/account";
import { ApiError, isSignedOut } from "../src/core/errors";
import { useAccount, useDeleteAccount, useDeletionPreview, useExportData } from "../src/lib/me-queries";
import { useInstantDate } from "../src/lib/months";
import { tokens, useLocale } from "../src/runtime";
import { space } from "../src/theme";
import { Card } from "../src/ui/list";
import { Button, Notice, Screen, Text } from "../src/ui/primitives";
import { SessionExpired } from "../src/ui/session";

/**
 * Your account: what you agreed to, taking your data with you, and leaving (the web's
 * `AccountPanel`, DPDP Act 2023). The app stores require the last two inside the app.
 *
 * - **The export goes through the share sheet** as text, the whole document the server built. It
 *   never contains a device token (ADR-075).
 * - **Deleting is two steps**: the server's preview of what would go with the account, or what
 *   blocks it (the only owner of an organisation others belong to), and then the act. The server
 *   has by then ended every session; this phone forgets its own, and so everything cached.
 */
export default function Account() {
  const t = useTranslations("account");
  const tm = useTranslations("mobile.account");
  const router = useRouter();
  const locale = useLocale();
  const day = useInstantDate();
  const { signedIn, query } = useAccount();
  const [confirming, setConfirming] = useState(false);
  const [shareFailed, setShareFailed] = useState(false);
  const exportData = useExportData();
  const preview = useDeletionPreview(confirming);
  const remove = useDeleteAccount();

  if (!signedIn) {
    return (
      <Screen>
        <Stack.Screen options={{ title: t("title") }} />
        <Text variant="title">{t("title")}</Text>
        <Text tone="muted">{t("signedOut")}</Text>
        <Button label={t("signIn")} onPress={() => router.push("/sign-in")} />
      </Screen>
    );
  }

  const consent = query.data ? consentOf(query.data) : null;
  const when = consent ? day(consent.at) : null;
  const blocked = preview.data?.blocked_by ?? [];
  const going = preview.data?.organisations_deleted ?? [];
  const deleteFailure =
    remove.error instanceof ApiError && remove.error.detail ? remove.error.detail : t("deleteError");

  const doExport = () => {
    setShareFailed(false);
    exportData.mutate(new Date().toISOString().slice(0, 10), {
      onSuccess: async (file) => {
        try {
          await Share.share({ title: tm("shareTitle"), message: file.text });
        } catch {
          setShareFailed(true);
        }
      },
    });
  };

  const doDelete = () =>
    remove.mutate(undefined, {
      // The server has ended every session. Forget this phone's too: the sign-out watch in the root
      // layout then drops every cached query, and the person lands on Home signed out.
      onSuccess: async () => {
        await tokens.clear();
        router.replace("/");
      },
    });

  return (
    <Screen>
      <Stack.Screen options={{ title: t("title") }} />
      <Text variant="title">{t("title")}</Text>
      <Text tone="muted">{t("subtitle")}</Text>

      <Card>
        <Text variant="lead">{t("consentTitle")}</Text>
        <Text tone="muted">
          {consent && when ? t("consentGiven", { version: consent.version, date: when }) : t("consentMissing")}
        </Text>
        <Button
          variant="secondary"
          label={tm("readNotice")}
          onPress={() => void Linking.openURL(`${WEB_BASE_URL}/${locale}/privacy`)}
        />
      </Card>

      <Card>
        <Text variant="lead">{t("exportTitle")}</Text>
        <Text tone="muted">{t("exportBody")}</Text>
        <Button
          variant="secondary"
          label={exportData.isPending ? t("exporting") : t("exportButton")}
          busy={exportData.isPending}
          onPress={doExport}
        />
        {exportData.isError ? (
          isSignedOut(exportData.error) ? <SessionExpired /> : <Notice tone="danger">{t("exportError")}</Notice>
        ) : null}
        {shareFailed ? <Notice tone="danger">{tm("shareFailed")}</Notice> : null}
      </Card>

      <Card>
        <Text variant="lead">{t("deleteTitle")}</Text>
        <Text tone="muted">{t("deleteBody")}</Text>
        {!confirming ? (
          <Button label={t("deleteButton")} onPress={() => setConfirming(true)} />
        ) : (
          <View style={{ gap: space.md }}>
            <Text variant="lead">{t("confirmTitle")}</Text>
            {preview.isPending ? (
              <Text tone="muted">{t("loadingPreview")}</Text>
            ) : preview.isError ? (
              isSignedOut(preview.error) ? <SessionExpired /> : <Notice tone="danger">{t("deleteError")}</Notice>
            ) : blocked.length > 0 ? (
              <>
                <Text>{t("blocked")}</Text>
                {blocked.map((o) => (
                  <Text key={o.slug}>{o.name}</Text>
                ))}
              </>
            ) : going.length > 0 ? (
              <>
                <Text>{t("orgsGoing")}</Text>
                {going.map((o) => (
                  <Text key={o.slug}>{t("orgLine", { name: o.name, listings: o.listings })}</Text>
                ))}
              </>
            ) : (
              <Text>{t("nothingElse")}</Text>
            )}
            {remove.isError ? (
              isSignedOut(remove.error) ? <SessionExpired /> : <Notice tone="danger">{deleteFailure}</Notice>
            ) : null}
            <Button
              label={remove.isPending ? t("deleting") : t("confirmButton")}
              busy={remove.isPending}
              disabled={!preview.data || !canDelete(preview.data)}
              onPress={doDelete}
            />
            <Button
              variant="secondary"
              label={t("cancel")}
              onPress={() => {
                setConfirming(false);
                remove.reset();
              }}
            />
          </View>
        )}
      </Card>
    </Screen>
  );
}
