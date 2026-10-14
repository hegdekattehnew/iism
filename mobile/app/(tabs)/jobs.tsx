import { useLocalSearchParams, useRouter } from "expo-router";
import { useDeferredValue, useState } from "react";
import { Text as NativeText } from "react-native";
import { useTranslations } from "use-intl";

import { experienceLabel, salaryLabel } from "../../src/core/labels";
import { useJobs } from "../../src/lib/queries";
import { useSeededTerm } from "../../src/lib/term";
import { useColours } from "../../src/theme";
import { Badge, BadgeRow, Card, Chip, ChipRow, ResultList, SearchBox, Text } from "../../src/ui";

// The set the API accepts; the web derives the same list from its schema.
const TYPES = ["full_time", "part_time", "contract", "apprenticeship", "gig"] as const;

type Job = NonNullable<ReturnType<typeof useJobs>["data"]>["pages"][number]["items"][number];

export default function Jobs() {
  const t = useTranslations("jobsPage");
  const router = useRouter();
  const params = useLocalSearchParams<{ q?: string }>();
  const [q, setQ] = useSeededTerm(params.q);
  const [type, setType] = useState("");
  const deferred = useDeferredValue(q.trim());
  const query = useJobs({ q: deferred, employmentType: type });

  return (
    <ResultList
      query={query}
      keyOf={(job: Job) => job.slug}
      emptyText={t("noResults")}
      countLabel={(total) => t("resultsCount", { count: total })}
      header={
        <>
          <SearchBox value={q} onChangeText={setQ} placeholder={t("searchPlaceholder")} />
          <ChipRow>
            <Chip label={t("allTypes")} selected={type === ""} onPress={() => setType("")} />
            {TYPES.map((ty) => (
              <Chip key={ty} label={t(`employmentType.${ty}`)} selected={type === ty} onPress={() => setType(ty)} />
            ))}
          </ChipRow>
        </>
      }
      renderRow={(job) => (
        <Card onPress={() => router.push(`/job/${job.slug}`)} label={job.title}>
          <BadgeRow>
            <Badge tone="brand" label={t(`employmentType.${job.employment_type}`)} />
            {job.nsqf_level_min != null ? (
              <Badge label={t("minLevel", { level: job.nsqf_level_min })} />
            ) : null}
          </BadgeRow>
          <Text variant="lead">{job.title}</Text>
          <Text tone="muted">{job.tenant.name}</Text>
          <Place district={job.location_district} state={job.location_state} />
          <Text tone="muted">
            {experienceLabel(job, (k, v) => t(k, v))}
            {" · "}
            {salaryLabel(job, (k, v) => t(k, v))}
          </Text>
        </Card>
      )}
    />
  );
}

function Place({ district, state }: { district?: string | null; state?: string | null }) {
  const c = useColours();
  const place = [district, state].filter(Boolean).join(", ");
  return place ? <NativeText style={{ color: c.muted, fontSize: 13 }}>{place}</NativeText> : null;
}
