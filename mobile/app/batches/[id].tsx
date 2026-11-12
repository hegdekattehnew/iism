import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useTranslations } from "use-intl";

import { useBatch } from "../../src/lib/me-queries";
import { BatchCard } from "../../src/ui/BatchCard";
import { BatchPanel } from "../../src/ui/BatchPanel";
import { Button, Screen } from "../../src/ui";
import { RecordState } from "../../src/ui/detail";

/**
 * One batch on its own screen (Sprint 102): where a notice, a push or a shared link lands. The same
 * card and register control the list leads to; a batch that is gone is a sentence and a way back.
 */
export default function BatchDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const t = useTranslations("publicBatches");
  const tm = useTranslations("mobile.me");
  const router = useRouter();
  const query = useBatch(id);
  const batch = query.data;

  return (
    <Screen>
      <Stack.Screen options={{ title: batch?.course.title ?? t("details") }} />
      <RecordState query={query}>
        {batch ? (
          <>
            <BatchCard batch={batch} footer={<BatchPanel batch={batch} />} />
            <Button
              variant="secondary"
              label={tm("viewCourse")}
              onPress={() => router.push(`/course/${batch.course.slug}`)}
            />
          </>
        ) : null}
      </RecordState>
    </Screen>
  );
}
