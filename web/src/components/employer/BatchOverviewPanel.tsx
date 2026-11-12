"use client";

import { useFormatter, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { MetricTile } from "@/components/ui/metric-tile";
import {
  AlertTriangleIcon,
  CalendarIcon,
  ClockIcon,
  InboxIcon,
  InfoIcon,
  UsersIcon,
} from "@/components/ui/icons";
import { Skeleton } from "@/components/ui";
import { useBatchOverview } from "@/lib/batches";

/**
 * What a delivering organisation (or a centre) has to look at today (Sprint 99, BL-18.6, BL-22.7):
 * what waits to be published, what starts this week, what is running, how many seats are still free
 * in classes about to begin, and what needs a look. **Counted where the rows are** (`/batches/overview`),
 * never from the page of batches beside it. The figures are on the page before they arrive (a dash,
 * never a zero), so nothing below them moves; `showNext` adds the next few that start, for the
 * organisation's home, where the full list is not on the page.
 */
export function BatchOverviewPanel({ org, showNext = false }: { org: string; showNext?: boolean }) {
  const t = useTranslations("batches.overview");
  const format = useFormatter();
  const overview = useBatchOverview(org);
  const d = overview.data;
  // A failed read costs this block, never the page it sits on.
  if (overview.isError) return null;
  const date = (value: string) =>
    format.dateTime(new Date(`${value}T00:00:00Z`), { dateStyle: "medium", timeZone: "UTC" });

  return (
    <section aria-labelledby="batch-overview" className="space-y-3">
      <h2 id="batch-overview" className="text-base font-semibold">
        {t("heading")}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricTile
          icon={<CalendarIcon />}
          value={d?.starting_soon ?? null}
          label={t("startingSoon")}
          className="min-w-0"
        />
        <MetricTile
          icon={<InfoIcon />}
          value={d?.drafts ?? null}
          label={t("drafts")}
          className="min-w-0"
        />
        <MetricTile
          icon={<ClockIcon />}
          value={d?.running ?? null}
          label={t("running")}
          className="min-w-0"
        />
        <MetricTile
          icon={<UsersIcon />}
          value={d?.unfilled_seats ?? null}
          label={t("unfilled")}
          secondary={d ? t("unfilledIn", { count: d.unfilled_batches }) : undefined}
          className="min-w-0"
        />
        <MetricTile
          icon={<InboxIcon />}
          value={d?.replies_owed ?? null}
          label={t("repliesOwed")}
          secondary={
            d?.oldest_reply_owed_since
              ? t("oldestWaiting", { date: date(d.oldest_reply_owed_since.slice(0, 10)) })
              : undefined
          }
          className="min-w-0"
        />
        <MetricTile
          icon={<AlertTriangleIcon />}
          value={d?.unavailable ?? null}
          label={t("unavailable")}
          className="min-w-0"
        />
      </div>
      {showNext && (
        // Three rows of a fixed height are reserved whether or not they are filled (Sprint 99): the
        // list arrives after the figures, and what is under it must not move when it does.
        <div className="min-h-[11rem]">
          <h3 className="text-sm font-medium">{t("next")}</h3>
          {overview.isPending ? (
            <Skeleton className="mt-2 h-36 w-full rounded-lg" />
          ) : d && d.upcoming.length > 0 ? (
            <ul className="mt-2 space-y-1 text-sm">
              {d.upcoming.slice(0, 3).map((b) => (
                <li key={b.id} className="h-12 min-w-0">
                  <span className="block truncate font-medium">{b.course.title}</span>
                  <span className="block truncate text-muted">
                    {b.centre.name} · {date(b.starts_on)} · {t("seatsLeft", { count: b.seats_left })}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">{t("nothingNext")}</p>
          )}
        </div>
      )}
      {showNext && (
        <Link
          href={`/employer/${org}/batches`}
          className="inline-flex min-h-11 items-center text-sm font-medium text-brand underline-offset-4 hover:underline"
        >
          {t("all")}
        </Link>
      )}
    </section>
  );
}
