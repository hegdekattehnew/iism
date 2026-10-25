"use client";

import { useTranslations } from "next-intl";

import { BatchInterestCard } from "@/components/cards/BatchInterestCard";
import { Button, Skeleton } from "@/components/ui";
import { useBatchInterestMutations, useMyBatchInterests } from "@/lib/batches";
import { detailOf } from "@/lib/http";
import { Alert } from "@/components/ui";

/**
 * The batches the learner has registered for (Sprint 100), beneath their course interests. Shown
 * only when there is one: a learner who never looked at a batch is not told about a list that does
 * not concern them, and the block holds nothing back while it loads (`Skeleton`, then it is either
 * a list or absent).
 */
export function BatchInterestList() {
  const t = useTranslations("batchInterest");
  const mine = useMyBatchInterests(true);
  const { withdraw } = useBatchInterestMutations();
  if (mine.isError) return null;
  if (mine.isPending) return <Skeleton className="mt-8 h-24 w-full" />;
  if (mine.data.length === 0) return null;

  return (
    <section aria-labelledby="my-batches" className="mt-10">
      <h2 id="my-batches" className="text-xl font-semibold">
        {t("heading")}
      </h2>
      <p className="mt-1 text-sm text-muted">{t("subheading")}</p>
      {withdraw.error != null && (
        <Alert role="alert" className="mt-3">
          {detailOf(withdraw.error) ?? t("failed")}
        </Alert>
      )}
      <ul className="mt-4 space-y-4">
        {mine.data.map((i) => (
          <li key={i.id}>
            <BatchInterestCard
              interest={i}
              footer={
                i.status !== "withdrawn" && i.batch.phase !== "cancelled" ? (
                  <div className="mt-3">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={withdraw.isPending}
                      aria-label={t("withdrawNamed", { name: i.batch.course.title })}
                      onClick={() => withdraw.mutate(i.id)}
                    >
                      {t("withdraw")}
                    </Button>
                  </div>
                ) : null
              }
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
