import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import {
  REPLY_WITHIN_DAYS,
  awaitingReply,
  batchFailureText,
  canWithdrawBatch,
  replyByInstant,
} from "../core/batches";
import { formatInstantDate } from "../core/format";
import { isSignedOut } from "../core/errors";
import { useBatchInterests, useWithdrawBatchInterest } from "../lib/me-queries";
import { useMonthName } from "../lib/months";
import { space } from "../theme";
import { BatchCard } from "./BatchCard";
import { Badge } from "./list";
import { Button, Notice, Text } from "./primitives";
import { SessionExpired } from "./session";

/**
 * The batches the learner asked about, beneath their course interests (Sprint 102). Shown only when
 * there is one: a learner who never looked at a batch is not told about a list that does not concern
 * them. A withdrawn or cancelled one says so and has nothing to press; one still waiting says when a
 * reply is expected (an ask, never a promise) and gives a way to tell us if it did not come.
 */
export function MyBatches() {
  const t = useTranslations("batchInterest");
  const tp = useTranslations("publicBatches");
  const router = useRouter();
  const monthName = useMonthName();
  const query = useBatchInterests();
  const withdraw = useWithdrawBatchInterest();
  if (!query.data || query.data.length === 0) return null;

  return (
    <View style={{ gap: space.md }}>
      <Text variant="lead">
        {t("heading")}
      </Text>
      <Text tone="muted">{t("subheading")}</Text>
      {query.data.map((i) => {
        const reply = awaitingReply(i) ? replyByInstant(i.registered_at) : null;
        const replyDate = reply ? formatInstantDate(reply, monthName, "short") : null;
        return (
          <BatchCard
            key={i.id}
            batch={i.batch}
            footer={
              <View style={{ gap: space.sm }}>
                <Badge
                  tone={i.status === "withdrawn" ? "muted" : i.batch.phase === "cancelled" ? "warning" : "success"}
                  label={t(`status.${i.status}`)}
                />
                {i.batch.phase === "cancelled" ? (
                  <Notice tone="warning">{t(`cancelled.${i.batch.cancel_reason ?? "by_organisation"}`)}</Notice>
                ) : null}
                {replyDate ? (
                  <View style={{ gap: 2 }}>
                    <Text>{t("replyBy", { date: replyDate })}</Text>
                    <Text tone="muted" variant="small">
                      {t("replyHelp", { days: REPLY_WITHIN_DAYS })}
                    </Text>
                    <Button variant="ghost" label={t("notHeard")} onPress={() => router.push("/contact")} />
                  </View>
                ) : null}
                <Button
                  variant="secondary"
                  label={tp("details")}
                  onPress={() => router.push(`/batches/${i.batch.id}`)}
                />
                {canWithdrawBatch(i) ? (
                  <Button
                    variant="secondary"
                    label={t("withdraw")}
                    accessibilityLabel={t("withdrawNamed", { name: i.batch.course.title })}
                    busy={withdraw.isPending && withdraw.variables === i.id}
                    onPress={() => withdraw.mutate(i.id)}
                  />
                ) : null}
              </View>
            }
          />
        );
      })}
      {withdraw.isError ? (
        isSignedOut(withdraw.error) ? (
          <SessionExpired />
        ) : (
          <Notice tone="danger">{batchFailureText(withdraw.error, (k) => tp(k))}</Notice>
        )
      ) : null}
    </View>
  );
}
