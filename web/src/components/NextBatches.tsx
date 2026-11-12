"use client";

import { useTranslations } from "next-intl";

import { PublicBatchCard } from "@/components/cards/PublicBatchCard";
import { RegisterBatch } from "@/components/RegisterBatch";
import { Skeleton } from "@/components/ui";
import { useIsSignedIn } from "@/lib/auth";
import { usePublicBatches } from "@/lib/batches";
import { Link } from "@/i18n/navigation";

const NONE = { stateId: "", districtId: "", startsWithin: "", maxFee: "", mode: "" } as const;
const SHOWN = 3;

/**
 * A course's next batches (Sprint 100, BL-20.2), in place of one intake line: where it is taught,
 * who teaches it, when it starts and what is left, nearest first. A course nobody has planned a
 * batch of shows nothing at all (the course's own place and intake, which the page already has, are
 * all there is to say), and a failed read costs this block and never the page.
 */
export function NextBatches({ course }: { course: string }) {
  const t = useTranslations("publicBatches");
  const signedIn = useIsSignedIn();
  const list = usePublicBatches({ ...NONE, course }, signedIn, SHOWN);
  if (list.isError) return null;
  if (list.isPending) return <Skeleton className="mt-6 h-40 w-full rounded-xl" />;
  const rows = list.data.pages[0]?.items ?? [];
  const total = list.data.pages[0]?.total ?? 0;
  if (rows.length === 0) return null;

  return (
    <section aria-labelledby="next-batches" className="mt-8 space-y-3">
      <h2 id="next-batches" className="text-lg font-semibold">
        {t("nextHeading")}
      </h2>
      <ul className="space-y-3">
        {rows.map((b) => (
          <li key={b.id}>
            <PublicBatchCard batch={b} footer={<RegisterBatch batch={b} />} />
          </li>
        ))}
      </ul>
      {total > rows.length && (
        <Link
          href={`/batches?course=${encodeURIComponent(course)}`}
          className="inline-flex min-h-11 items-center text-sm font-medium text-brand underline-offset-4 hover:underline"
        >
          {t("seeAll", { count: total })}
        </Link>
      )}
    </section>
  );
}
