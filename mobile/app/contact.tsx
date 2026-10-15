import { Stack } from "expo-router";
import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import {
  BODY_MAX,
  BODY_MIN,
  REPLY_MAX,
  canSend,
  kindsFor,
  sendFailure,
  type Kind,
} from "../src/core/grievance";
import { useAccount, useMyMessages, useSendMessage } from "../src/lib/me-queries";
import { useInstantDate } from "../src/lib/months";
import { space } from "../src/theme";
import { Badge, BadgeRow, Card, Chip } from "../src/ui/list";
import { Button, Notice, Screen, Text, TextField } from "../src/ui/primitives";

/**
 * Write to the team: a question, a complaint, or a request about your own data (the web's
 * `/contact` and `/grievance`, ADR-067). **We never write to an address a stranger typed** (the
 * team replies out of band), and a signed-in person is answered through their account, so is never
 * asked for an address. Signed in, the person also sees what they sent and where each stands: the
 * other half of "acknowledged within a day". The operator's note is never shown.
 */
export default function Contact() {
  const t = useTranslations("messageForm");
  const tc = useTranslations("contactPage");
  const tm = useTranslations("mobile.contact");
  const { signedIn } = useAccount();
  const [kind, setKind] = useState<Kind>("contact");
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const send = useSendMessage();

  const draft = { kind, body, replyTo, signedIn };
  const failure = send.isError ? sendFailure(send.error) : null;
  const kinds = kindsFor(signedIn);

  return (
    <Screen>
      <Stack.Screen options={{ title: tc("title") }} />
      <Text variant="title">{tc("title")}</Text>
      {send.isSuccess ? (
        <View style={{ gap: space.md }}>
          <Text variant="lead">{t("sentTitle")}</Text>
          <Text>{`${t("reference")} ${send.data.reference}`}</Text>
          <Text tone="muted">
            {send.data.kind === "contact"
              ? t("sentContact")
              : t("sentPromise", { hours: send.data.acknowledge_within_hours, days: send.data.resolve_within_days })}
          </Text>
          <Text tone="muted">{signedIn ? t("sentSignedIn") : t("sentSignedOut")}</Text>
          <Button
            variant="secondary"
            label={t("another")}
            onPress={() => {
              send.reset();
              setBody("");
            }}
          />
        </View>
      ) : (
        <View style={{ gap: space.md }}>
          <Text tone="muted">{tm("intro")}</Text>
          <Text variant="small" tone="muted">
            {t("kindLegend")}
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            {kinds.map((k) => (
              <Chip key={k} label={t(`kind.${k}`)} selected={kind === k} onPress={() => setKind(k)} />
            ))}
          </View>
          {t(`kindHint.${kind}`) ? (
            <Text tone="muted" variant="small">
              {t(`kindHint.${kind}`)}
            </Text>
          ) : null}
          {signedIn ? null : <Text tone="muted">{tm("signedOutNote")}</Text>}
          <TextField
            label={t("bodyLabel")}
            value={body}
            onChangeText={setBody}
            maxLength={BODY_MAX}
            multiline
            numberOfLines={5}
          />
          <Text tone="muted" variant="small">
            {t("bodyHint", { min: BODY_MIN, max: BODY_MAX })}
          </Text>
          <Text tone="muted" variant="small">
            {t("counter", { used: body.length, max: BODY_MAX })}
          </Text>
          {signedIn ? null : (
            <>
              <TextField
                label={t("replyToLabel")}
                value={replyTo}
                onChangeText={setReplyTo}
                maxLength={REPLY_MAX}
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <Text tone="muted" variant="small">
                {t("replyToHint")}
              </Text>
            </>
          )}
          {failure ? (
            <Notice tone="danger">
              {failure.key === "errorWait"
                ? t("errorWait", { seconds: failure.seconds })
                : failure.key === "errorSignIn"
                  ? t("errorSignIn")
                  : (failure.detail ?? t("errorGeneric"))}
            </Notice>
          ) : null}
          <Button
            label={send.isPending ? t("sending") : t("send")}
            busy={send.isPending}
            disabled={!canSend(draft)}
            onPress={() => send.mutate(draft)}
          />
        </View>
      )}
      {signedIn ? <MyMessages /> : null}
    </Screen>
  );
}

function MyMessages() {
  const t = useTranslations("messageForm");
  const day = useInstantDate();
  const mine = useMyMessages();
  if (!mine.data || mine.data.length === 0) return null;
  return (
    <View style={{ gap: space.md }}>
      <Text variant="lead">{t("mineHeading")}</Text>
      {mine.data.map((m) => {
        const sent = day(m.created_at);
        const closed = m.resolved_at ? day(m.resolved_at) : null;
        return (
          <Card key={m.reference}>
            <BadgeRow>
              <Badge tone={m.status === "resolved" ? "success" : m.status === "dismissed" ? "muted" : "brand"} label={t(`status.${m.status}`)} />
              <Badge label={t(`kind.${m.kind}`)} />
            </BadgeRow>
            <Text>{m.reference}</Text>
            <Text tone="muted" variant="small">
              {[sent ? t("sentOn", { date: sent }) : null, closed ? t("closedOn", { date: closed }) : null]
                .filter(Boolean)
                .join(" · ")}
            </Text>
          </Card>
        );
      })}
    </View>
  );
}
