import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { isSignedOut } from "../core/errors";
import { DETAIL_MAX, REASONS, reportFailure, type Reason, type Target } from "../core/report";
import { useReportListing } from "../lib/me-queries";
import { useSignedIn } from "../runtime";
import { space } from "../theme";
import { Chip } from "./list";
import { Button, Notice, Text, TextField } from "./primitives";
import { SessionExpired } from "./session";

/**
 * "Report this vacancy / course" (ADR-069). **A report is accountable, so it needs an account**:
 * signed out, this says to sign in instead of offering a form that cannot succeed. The server's own
 * sentences are shown for the two refusals a person can act on ("you manage this listing", "you have
 * already reported it"), and the person is told only that it was received: what an operator decides,
 * and who reported, are not for them or the organisation to be told. The stores require a way to
 * report content; this is it.
 */
export function ReportPanel({ target, slug }: { target: Target; slug: string }) {
  const t = useTranslations("reportListing");
  const signedIn = useSignedIn();
  const report = useReportListing(target, slug);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<Reason>("fake_or_misleading");
  const [detail, setDetail] = useState("");

  // Signed out: a line that says why there is no form. The way in is already on the page (the apply
  // and match prompts above), so a third sign-in button would only be noise.
  if (!signedIn) return <Text tone="muted">{t("signedOut")}</Text>;
  if (report.isSuccess) return <Notice tone="info">{t("received")}</Notice>;

  const failure = report.isError ? reportFailure(report.error) : null;

  return (
    <View style={{ gap: space.md }}>
      <Button
        variant="secondary"
        label={t(target === "job" ? "openJob" : "openCourse")}
        onPress={() => setOpen((v) => !v)}
      />
      {open ? (
        <View style={{ gap: space.md }}>
          <Text tone="muted">{t("intro")}</Text>
          <Text variant="small" tone="muted">
            {t("reasonLabel")}
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            {REASONS.map((r) => (
              <Chip key={r} label={t(`reason.${r}`)} selected={reason === r} onPress={() => setReason(r)} />
            ))}
          </View>
          <TextField
            label={t("detailLabel")}
            placeholder={t("detailHint")}
            value={detail}
            onChangeText={setDetail}
            maxLength={DETAIL_MAX}
            multiline
            numberOfLines={3}
          />
          {isSignedOut(report.error) ? (
            <SessionExpired />
          ) : failure ? (
            <Notice tone="danger">{failure.detail ?? t(failure.key)}</Notice>
          ) : null}
          <Button
            label={report.isPending ? t("sending") : t("send")}
            busy={report.isPending}
            onPress={() => report.mutate({ reason, detail })}
          />
        </View>
      ) : null}
    </View>
  );
}
