import { useLocalSearchParams, useRouter } from "expo-router";
import { useDeferredValue, useState } from "react";
import { useTranslations } from "use-intl";

import { useJobs } from "../../src/lib/queries";
import { useSeededTerm } from "../../src/lib/term";
import { Chip, ChipRow, ResultList, SearchBox } from "../../src/ui";
import { JobCard } from "../../src/ui/JobCard";

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
      renderRow={(job) => <JobCard job={job} onPress={() => router.push(`/job/${job.slug}`)} />}
    />
  );
}
