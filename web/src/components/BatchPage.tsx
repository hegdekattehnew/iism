"use client";

import { useTranslations } from "next-intl";

import { PublicBatchCard } from "@/components/cards/PublicBatchCard";
import { RegisterBatch } from "@/components/RegisterBatch";
import { ButtonLink, Skeleton } from "@/components/ui";
import { EmptyState } from "@/components/ui/empty-state";
import { CalendarIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { useBatch } from "@/lib/batches";

/**
 * One batch on its own page (Sprint 101): where a notice, a bookmark or a shared link lands. The
 * same card and the same register control the list uses, with the link to itself left out. A batch
 * that is gone (a draft, a taken-down course, a wrong id) is one sentence and a way back, never a
 * blank page. The skeleton holds the card's room so nothing moves when it arrives (ADR-065).
 */
export function BatchPage({ id }: { id: string }) {
  const t = useTranslations("batchPage");
  const signedIn = useIsSignedIn();
  const one = useBatch(id, signedIn);

  return (
    <div className="mt-6 space-y-4">
      <Link
        href="/batches"
        className="inline-flex min-h-11 items-center text-sm font-medium text-brand underline-offset-4 hover:underline"
      >
        {t("back")}
      </Link>
      {one.isPending ? (
        <Skeleton className="h-72 w-full rounded-xl" />
      ) : one.isError ? (
        <EmptyState
          icon={CalendarIcon}
          title={t("notAvailable")}
          action={<ButtonLink href="/batches">{t("seeBatches")}</ButtonLink>}
        >
          {t("notAvailableHint")}
        </EmptyState>
      ) : (
        <PublicBatchCard
          batch={one.data}
          detailsLink={false}
          footer={<RegisterBatch batch={one.data} />}
        />
      )}
    </div>
  );
}
