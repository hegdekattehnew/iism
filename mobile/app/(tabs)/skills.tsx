import { useLocalSearchParams, useRouter } from "expo-router";
import { useDeferredValue, useState } from "react";
import { useTranslations } from "use-intl";

import { lookalikeNames } from "../../src/core/labels";
import { useSkills } from "../../src/lib/queries";
import { useSeededTerm } from "../../src/lib/term";
import { Badge, BadgeRow, Card, Chip, ChipRow, ResultList, SearchBox, Text } from "../../src/ui";

const TYPES = ["technical", "core", "generic"] as const;

type Skill = NonNullable<ReturnType<typeof useSkills>["data"]>["pages"][number]["items"][number];

/**
 * The national occupational standards. 1,778 names are shared by 4,838 standards, so a card names
 * the qualification and the code it comes from, and names that appear twice on the screen are
 * flagged "compare the codes" (the web's rule, Sprint 23).
 */
export default function Skills() {
  const t = useTranslations("skillsPage");
  const router = useRouter();
  const params = useLocalSearchParams<{ q?: string }>();
  const [q, setQ] = useSeededTerm(params.q);
  const [type, setType] = useState("");
  const deferred = useDeferredValue(q.trim());
  const query = useSkills({ q: deferred, skillType: type });
  const shown = query.data?.pages.flatMap((page) => page.items) ?? [];
  const twins = lookalikeNames(shown);

  return (
    <ResultList
      query={query}
      keyOf={(skill: Skill) => skill.slug}
      emptyText={t("noResults")}
      countLabel={(total) => t("resultsCount", { count: total })}
      header={
        <>
          <SearchBox value={q} onChangeText={setQ} placeholder={t("searchPlaceholder")} />
          {/* A search is not filtered by type (the server ranks across all of them). */}
          {deferred ? null : (
            <ChipRow>
              <Chip label={t("allTypes")} selected={type === ""} onPress={() => setType("")} />
              {TYPES.map((ty) => (
                <Chip key={ty} label={t(`type.${ty}`)} selected={type === ty} onPress={() => setType(ty)} />
              ))}
            </ChipRow>
          )}
        </>
      }
      renderRow={(skill) => (
        <Card onPress={() => router.push(`/skill/${skill.slug}`)} label={skill.name}>
          <BadgeRow>
            <Badge tone="brand" label={t(`type.${skill.skill_type}`)} />
            {skill.nsqf_level != null ? <Badge label={t("levelShort", { level: skill.nsqf_level })} /> : null}
          </BadgeRow>
          <Text variant="lead">{skill.name}</Text>
          {skill.nos_code ? <Text tone="muted">{skill.nos_code}</Text> : null}
          {skill.context?.qualification_name ? (
            <Text tone="muted">
              {[skill.context.qualification_name, skill.context.sector].filter(Boolean).join(" · ")}
            </Text>
          ) : null}
          {twins.has(skill.name.trim().toLowerCase()) ? <Text tone="muted">{t("lookalike")}</Text> : null}
        </Card>
      )}
    />
  );
}
