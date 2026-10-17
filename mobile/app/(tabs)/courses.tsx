import { useLocalSearchParams, useRouter } from "expo-router";
import { useDeferredValue, useState } from "react";
import { useTranslations } from "use-intl";

import { creditsText, feeLabel, intakeLabel, whereLabel } from "../../src/core/labels";
import { useCourses } from "../../src/lib/queries";
import { useSeededTerm } from "../../src/lib/term";
import { useMonthName } from "../../src/lib/months";
import { Badge, BadgeRow, Card, Chip, ChipRow, ResultList, SearchBox, Text } from "../../src/ui";

const MODES = ["online", "offline", "hybrid"] as const;

type Course = NonNullable<ReturnType<typeof useCourses>["data"]>["pages"][number]["items"][number];

export default function Courses() {
  const t = useTranslations("coursesPage");
  const router = useRouter();
  const monthName = useMonthName();
  const params = useLocalSearchParams<{ q?: string }>();
  const [q, setQ] = useSeededTerm(params.q);
  const [mode, setMode] = useState("");
  const deferred = useDeferredValue(q.trim());
  const query = useCourses({ q: deferred, mode });

  return (
    <ResultList
      query={query}
      keyOf={(course: Course) => course.slug}
      emptyText={t("noResults")}
      countLabel={(total) => t("resultsCount", { count: total })}
      header={
        <>
          <SearchBox value={q} onChangeText={setQ} placeholder={t("searchPlaceholder")} />
          <ChipRow>
            <Chip label={t("allModes")} selected={mode === ""} onPress={() => setMode("")} />
            {MODES.map((m) => (
              <Chip key={m} label={t(`mode.${m}`)} selected={mode === m} onPress={() => setMode(m)} />
            ))}
          </ChipRow>
        </>
      }
      renderRow={(course) => {
        const place = whereLabel(course, (k, v) => t(k, v));
        const intake = intakeLabel(course, (k, v) => t(k, v), monthName);
        const where = [place, intake].filter(Boolean).join(" · ");
        return (
          <Card onPress={() => router.push(`/course/${course.slug}`)} label={course.title}>
            <BadgeRow>
              <Badge tone="brand" label={t(`mode.${course.mode}`)} />
              <Badge label={t(`language.${course.language}`)} />
              {course.nsqf_level != null ? <Badge label={t("level", { level: course.nsqf_level })} /> : null}
              {creditsText(course.qualification_credits, (k, v) => t(k, v)) ? (
                <Badge label={creditsText(course.qualification_credits, (k, v) => t(k, v)) ?? ""} />
              ) : null}
            </BadgeRow>
            <Text variant="lead">{course.title}</Text>
            <Text tone="muted">{course.tenant.name}</Text>
            {where ? <Text tone="muted">{where}</Text> : null}
            <Text>
              {feeLabel(course, (k, v) => t(k, v))}
              {course.duration_hours != null
                ? ` · ${t("duration", { hours: course.duration_hours })}`
                : ""}
            </Text>
          </Card>
        );
      }}
    />
  );
}
