import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import { useTranslations } from "use-intl";

import { BATCH_MODES, type BatchMode, type PublicBatch } from "../../src/core/batches";
import { useBatches } from "../../src/lib/me-queries";
import { BatchCard } from "../../src/ui/BatchCard";
import { Chip, ChipRow, ResultList, Text } from "../../src/ui";

/**
 * Batches near you (Sprint 102, BL-20.5): the classes a person can still join, in the server's
 * order (how near, how soon, what it costs), none hidden by where they are. A visitor can read it;
 * registering is on a batch's own screen. The count is the server's, never the page's length.
 */
export default function Batches() {
  const t = useTranslations("publicBatches");
  const router = useRouter();
  const params = useLocalSearchParams<{ course?: string }>();
  const [mode, setMode] = useState<BatchMode | "">("");
  const query = useBatches({ course: params.course, mode });

  return (
    <>
      <Stack.Screen options={{ title: t("heading") }} />
      <ResultList
        query={query}
        keyOf={(b: PublicBatch) => b.id}
        emptyText={t("empty")}
        countLabel={(total) => t("count", { total })}
        header={
          <>
            <Text variant="title">{t("heading")}</Text>
            <Text tone="muted">{t("subheading")}</Text>
            <ChipRow>
              <Chip label={t("anyMode")} selected={mode === ""} onPress={() => setMode("")} />
              {BATCH_MODES.map((m) => (
                <Chip key={m} label={t(`mode.${m}`)} selected={mode === m} onPress={() => setMode(m)} />
              ))}
            </ChipRow>
          </>
        }
        renderRow={(b) => <BatchCard batch={b} onPress={() => router.push(`/batches/${b.id}`)} />}
      />
    </>
  );
}
