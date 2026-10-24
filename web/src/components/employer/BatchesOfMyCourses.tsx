"use client";

import { useTranslations } from "next-intl";

import { Card, CardBody, Skeleton } from "@/components/ui";
import { ShieldCheckIcon } from "@/components/ui/icons";
import { useBatchesOfMyCourses } from "@/lib/batches";

/**
 * How other organisations run a seller's courses (Sprint 99, ADR-103): per course and per delivering
 * organisation, how many published batches, in which phase, and how many seats they report taken.
 * **Counts only.** No learner, no contact, no centre and no draft (a draft is the other organisation's
 * own plan), and the seats are the delivering organisation's own report, said so.
 */
export function BatchesOfMyCourses({ org }: { org: string }) {
  const t = useTranslations("delivery.batchesOfMine");
  const rows = useBatchesOfMyCourses(org);
  // A failed read costs this section, never the page it sits on.
  if (rows.isError) return null;

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{t("heading")}</h2>
      <p className="text-sm text-muted">{t("intro")}</p>
      {rows.isPending ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : rows.data.items.length === 0 ? (
        <p className="text-sm text-muted">{t("none")}</p>
      ) : (
        <ul className="space-y-3">
          {rows.data.items.map((r) => (
            <li key={`${r.course.slug}:${r.organisation.slug}`}>
              <Card>
                <CardBody>
                  <h3 className="text-base font-semibold">{r.course.title}</h3>
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
                    <span>
                      {t("noteWho")} {r.organisation.name}
                    </span>
                    {r.organisation.is_verified && (
                      <span className="inline-flex items-center gap-1 text-success-text">
                        <ShieldCheckIcon className="h-4 w-4" />
                        {t("reviewed")}
                      </span>
                    )}
                  </p>
                  <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm">
                    <span className="font-medium">{t("batches", { count: r.batches })}</span>
                    {r.open > 0 && <span>{t("open", { count: r.open })}</span>}
                    {r.full > 0 && <span>{t("full", { count: r.full })}</span>}
                    {r.running > 0 && <span>{t("running", { count: r.running })}</span>}
                    {r.finished > 0 && <span>{t("finished", { count: r.finished })}</span>}
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {t("seats", { enrolled: r.enrolled, seats: r.seats })}
                  </p>
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
