"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Badge, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { usePublicBatches, type PublicBatch } from "@/lib/batches";

const NO_FILTERS = { stateId: "", districtId: "", startsWithin: "", maxFee: "", mode: "" } as const;
const SHOWN_BATCHES = 3;

/**
 * The nearest batch of each course that would close a gap (Sprint 101, BL-20.2): where and when a
 * person could actually take it. One query for all the courses, the server's own order (how near,
 * how soon, what it costs); this takes the first batch of each course and shows at most three, each
 * a link to the batch's page. **It adds nothing to the score and hides nothing**: a course with no
 * batch simply has no line, and a failed read costs this block and never the screen. The skeleton
 * is the block's room while it loads, so what sits below it does not jump (ADR-065).
 */
export function NearestBatches({ slugs }: { slugs: string[] }) {
  const t = useTranslations("suggestedCourses");
  const tb = useTranslations("publicBatches");
  const format = useFormatter();
  const signedIn = useIsSignedIn();
  const list = usePublicBatches({ ...NO_FILTERS, courses: slugs }, signedIn, 24);
  if (list.isError) return null;
  if (list.isPending) return <Skeleton className="mt-3 h-16 w-full rounded-lg" />;

  const seen = new Set<string>();
  const nearest: PublicBatch[] = [];
  for (const b of list.data.pages.flatMap((p) => p.items)) {
    if (seen.has(b.course.slug)) continue;
    seen.add(b.course.slug);
    nearest.push(b);
    if (nearest.length === SHOWN_BATCHES) break;
  }
  if (nearest.length === 0) return null;

  return (
    <section aria-label={t("batchesHeading")} className="mt-3 space-y-2">
      <h4 className="text-sm font-semibold">{t("batchesHeading")}</h4>
      <ul className="space-y-2">
        {nearest.map((b) => (
          <li key={b.id}>
            <Link
              href={`/batches/${b.id}`}
              className="flex min-h-11 flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border-token px-3 py-2 text-sm hover:border-brand"
            >
              <span className="min-w-0 grow basis-40">
                {t("batchRow", {
                  course: b.course.title,
                  centre: b.centre.name,
                  date: format.dateTime(new Date(`${b.starts_on}T00:00:00Z`), {
                    dateStyle: "medium",
                    timeZone: "UTC",
                  }),
                })}
              </span>
              {b.reach !== "unknown" && (
                <Badge tone={b.reach === "elsewhere" ? "warn" : "good"}>{tb(`reach.${b.reach}`)}</Badge>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
