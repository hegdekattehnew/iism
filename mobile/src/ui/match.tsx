import { useState } from "react";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { coveragePercent, localityKey } from "../core/matches";
import { mandatoryFirst } from "../core/labels";
import { matchSummary } from "../core/match-summary";
import { space } from "../theme";
import { Badge, BadgeRow } from "./list";
import { Button, Text } from "./primitives";

type Gap = {
  name: string;
  nos_code?: string | null;
  importance: number;
  is_mandatory: boolean;
};

type Shape = {
  score: number;
  coverage: number;
  matched?: readonly Gap[];
  missing?: readonly Gap[];
  missing_mandatory?: number;
  level_shortfall?: number | null;
  experience_shortfall?: number | null;
  capped_by_mandatory?: boolean;
  locality?: number;
  job: { nsqf_level_min?: number | null };
};

/**
 * Why this score, and what to do, in a sentence (Sprint 70, UI-13): the web's `Sentence`, the same
 * words from the same catalogue. `matchSummary` counts the two lists the scorer returned and computes
 * nothing else; it says "skills this job asks for", never "the score is", because the score counts the
 * generic standards the sentence leaves out.
 */
export function MatchSentence({
  match,
  variant = "body",
}: {
  match: Pick<Shape, "matched" | "missing">;
  variant?: "body" | "lead";
}) {
  const t = useTranslations("matchesPage");
  const summary = matchSummary(match.matched ?? [], match.missing ?? []);
  if (summary.kind === "all") return <Text variant={variant}>{t("sentenceAll")}</Text>;
  const names = summary.names.join(", ");
  const missing = summary.more > 0 ? t("missingAnd", { names, more: summary.more }) : names;
  return (
    <Text variant={variant}>
      {t(summary.kind === "none" ? "sentenceNone" : "sentenceSome", {
        have: summary.have,
        total: summary.total,
        missing,
      })}
    </Text>
  );
}

/** The report behind the sentence, closed until asked for: what the person has and what they still need. */
export function GapDetails({ match }: { match: Shape }) {
  const t = useTranslations("mobile.detail");
  const [open, setOpen] = useState(false);
  return (
    <View style={{ gap: space.md }}>
      <Button
        variant="secondary"
        label={t("gapToggle")}
        expanded={open}
        onPress={() => setOpen((v) => !v)}
      />
      {open ? <GapLists match={match} /> : null}
    </View>
  );
}

/**
 * The score and what is behind it, rendered from the scorer's own fields. **Nothing is derived
 * here**: a picture that works out its own number can disagree with the score it claims to explain.
 * The cap, the level and experience shortfalls and the locality are each a field and a sentence.
 */
export function ScoreSummary({ match }: { match: Shape }) {
  const t = useTranslations("matchesPage");
  const v = useTranslations("matchViz");
  const near = localityKey(match.locality);
  const percent = coveragePercent(match.coverage);
  return (
    <View style={{ gap: space.sm }}>
      <BadgeRow>
        <Badge tone="brand" label={t("matchScore", { score: match.score })} />
        {near ? <Badge tone="success" label={t(near)} /> : null}
      </BadgeRow>
      <Text tone="muted">{v("coverageWeighted", { percent })}</Text>
      {match.capped_by_mandatory ? (
        <>
          <Badge tone="warning" label={v("cappedBy", { count: match.missing_mandatory ?? 1 })} />
          <Text tone="muted" variant="small">
            {t("capped")}
          </Text>
        </>
      ) : null}
      {match.experience_shortfall != null && match.experience_shortfall > 0 ? (
        <Text tone="muted" variant="small">
          {t("experienceShort", { years: match.experience_shortfall })}
        </Text>
      ) : null}
      {match.job.nsqf_level_min != null && match.level_shortfall != null && match.level_shortfall > 0 ? (
        <Text tone="muted" variant="small">
          {v("levelShort", {
            attained: match.job.nsqf_level_min - match.level_shortfall,
            required: match.job.nsqf_level_min,
          })}
        </Text>
      ) : null}
    </View>
  );
}

/** What the person has and what they still need, **required standards first**. */
export function GapLists({ match }: { match: Shape }) {
  const t = useTranslations("matchesPage");
  const matched = mandatoryFirst(match.matched ?? []);
  const missing = mandatoryFirst(match.missing ?? []);
  return (
    <View style={{ gap: space.lg }}>
      {matched.length > 0 ? (
        <View style={{ gap: space.xs }}>
          <Text tone="muted" variant="small">
            {t("youHave")}
          </Text>
          {matched.map((s) => (
            <Text key={`${s.nos_code ?? ""}${s.name}`}>{`✓ ${s.name}`}</Text>
          ))}
        </View>
      ) : null}
      {missing.length > 0 ? (
        <View style={{ gap: space.xs }}>
          <Text tone="muted" variant="small">
            {t("youNeed")}
          </Text>
          {missing.map((s) => (
            <View key={`${s.nos_code ?? ""}${s.name}`} style={{ gap: 2 }}>
              <Text>{s.name}</Text>
              {s.is_mandatory ? <Badge tone="warning" label={t("mandatory")} /> : null}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
