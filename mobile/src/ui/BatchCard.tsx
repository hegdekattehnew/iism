import type { ReactNode } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { batchLines, type PublicBatch } from "../core/batches";
import { useMonthName } from "../lib/months";
import { Badge, BadgeRow, Card } from "./list";
import { Text } from "./primitives";

/**
 * One batch as a learner sees it (Sprint 102, BL-20.5): the course and **who runs it** ("Course by
 * X", "Delivered by Y at Z", each organisation's own mark), how near it is, when it starts, what is
 * left and what it costs. The web's `PublicBatchCard`, from the same words (`publicBatches`).
 *
 * Pressable as a whole only when `onPress` is given and `footer` is not: **a card that holds a button
 * is not a button** (a button inside a button hides the inner one from a screen reader), so a card
 * with actions is a plain card and the list gives it a "Batch details" button of its own.
 */
export function BatchCard({
  batch,
  onPress,
  footer,
}: {
  batch: PublicBatch;
  onPress?: () => void;
  footer?: ReactNode;
}) {
  const t = useTranslations("publicBatches");
  const monthName = useMonthName();
  const lines = batchLines(batch, (k, v) => t(k, v), monthName);
  const body = (
    <>
      <BadgeRow>
        <Badge tone="brand" label={lines.mode} />
        {lines.reach ? <Badge tone={lines.reach.tone} label={lines.reach.text} /> : null}
        {lines.verifiedSeller || lines.verifiedOrganisation ? <Badge tone="success" label={t("reviewed")} /> : null}
        {lines.verifiedCentre ? <Badge tone="success" label={t("addressChecked")} /> : null}
      </BadgeRow>
      <Text variant="lead">{lines.course}</Text>
      {lines.label ? <Text tone="muted">{lines.label}</Text> : null}
      <Text tone="muted" variant="small">
        {lines.byLine}
      </Text>
      <Text tone="muted" variant="small">
        {lines.deliveredLine}
      </Text>
      <View style={{ gap: 2 }}>
        <Text>{lines.dates}</Text>
        {lines.place ? <Text tone="muted">{lines.place}</Text> : null}
        <Text>{[lines.seats, lines.fee].filter(Boolean).join(" · ")}</Text>
        {lines.feeNote ? (
          <Text tone="muted" variant="small">
            {lines.feeNote}
          </Text>
        ) : null}
        {lines.schedule ? (
          <Text tone="muted" variant="small">
            {lines.schedule}
          </Text>
        ) : null}
      </View>
      {footer}
    </>
  );
  if (footer || !onPress) return <Card>{body}</Card>;
  return (
    <Card onPress={onPress} label={`${lines.course}. ${lines.deliveredLine}`}>
      {body}
    </Card>
  );
}
