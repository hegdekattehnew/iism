import { useRouter } from "expo-router";
import { View } from "react-native";
import { useTranslations } from "use-intl";

import { useBatches } from "../lib/me-queries";
import { space } from "../theme";
import { BatchCard } from "./BatchCard";
import { Button } from "./primitives";
import { Section } from "./detail";

const SHOWN = 3;

/**
 * A course's next batches (Sprint 102): where it is taught, who teaches it, when it starts and what
 * is left, nearest first, in place of one intake line. A course nobody has planned a batch of shows
 * nothing at all, and a failed read costs this block and never the screen.
 */
export function NextBatches({ course }: { course: string }) {
  const t = useTranslations("publicBatches");
  const router = useRouter();
  const query = useBatches({ course });
  const first = query.data?.pages[0];
  if (query.isError || !first || first.items.length === 0) return null;
  const rows = first.items.slice(0, SHOWN);
  return (
    <Section title={t("nextHeading")}>
      <View style={{ gap: space.sm }}>
        {rows.map((b) => (
          <BatchCard key={b.id} batch={b} onPress={() => router.push(`/batches/${b.id}`)} />
        ))}
        {first.total > rows.length ? (
          <Button
            variant="secondary"
            label={t("seeAll", { count: first.total })}
            onPress={() => router.push(`/batches?course=${encodeURIComponent(course)}`)}
          />
        ) : null}
      </View>
    </Section>
  );
}
