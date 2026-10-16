import { useState } from "react";
import { Text as NativeText } from "react-native";
import { useTranslations } from "use-intl";

import { daysToClose, experienceLabel, postedText, salaryLabel } from "../core/labels";
import { MAX_FONT_SCALE, useColours } from "../theme";
import { Badge, BadgeRow, Card } from "./list";
import { Text } from "./primitives";

/**
 * One vacancy on a list (Sprint 69, UI-04/05/10): the web's `JobCard`, same words from the same
 * catalogue. **What, who, where, how much, by when**: the title, the employer (with a mark when it
 * is verified), the place, the pay **a month**, how soon it closes, and the employment type only when
 * it is not the ordinary one. The NSQF level lives on the vacancy's own screen.
 *
 * A card never says "not verified": the mark is a credit to an employer that has earned it, and the
 * absence of one in a list is not an accusation. The vacancy's screen is where the fact is stated.
 */

export type JobCardJob = {
  slug: string;
  title: string;
  location_state?: string | null;
  location_district?: string | null;
  employment_type: string;
  experience_min_years: number;
  experience_max_years?: number | null;
  salary_min_inr?: number | null;
  salary_max_inr?: number | null;
  closes_at?: string | null;
  published_at?: string | null;
  tenant: { name: string; is_verified?: boolean };
};

export function JobCard({
  job,
  onPress,
  now,
}: {
  job: JobCardJob;
  onPress: () => void;
  /** The moment "closes in n days" is counted from; a test sets it. */
  now?: number;
}) {
  // Read once when the card appears, never during a later render: a render must give the same answer
  // twice, and a list of cards that each re-read the clock would not.
  const [shownAt] = useState(() => Date.now());
  const t = useTranslations("jobsPage");
  const c = useColours();
  const say = (k: string, v?: Record<string, string | number>) => t(k, v);
  const place = [job.location_district, job.location_state].filter(Boolean).join(", ");
  const days = daysToClose(job.closes_at, now ?? shownAt);
  const posted = postedText(job.published_at, say, now ?? shownAt);
  const ordinary = job.employment_type === "full_time";

  return (
    <Card onPress={onPress} label={job.title}>
      <Text variant="lead">{job.title}</Text>
      <Text tone="muted">{job.tenant.name}</Text>
      {job.tenant.is_verified ? <Badge tone="success" label={t("verifiedEmployer")} /> : null}
      {place ? (
        <NativeText maxFontSizeMultiplier={MAX_FONT_SCALE} style={{ color: c.muted, fontSize: 13 }}>
          {place}
        </NativeText>
      ) : null}
      <Text variant="lead">{salaryLabel(job, say)}</Text>
      <Text tone="muted" variant="small">
        {experienceLabel(job, say)}
      </Text>
      {posted !== null ? (
        <Text tone="muted" variant="small">
          {posted}
        </Text>
      ) : null}
      {!ordinary || days !== null ? (
        <BadgeRow>
          {ordinary ? null : <Badge tone="brand" label={t(`employmentType.${job.employment_type}`)} />}
          {days !== null ? <Badge tone="warning" label={t("closesIn", { days })} /> : null}
        </BadgeRow>
      ) : null}
    </Card>
  );
}
