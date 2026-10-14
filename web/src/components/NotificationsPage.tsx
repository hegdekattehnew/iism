"use client";

import { useFormatter, useNow, useTranslations } from "next-intl";

import { SessionExpired } from "@/components/SessionExpired";
import { Alert, Badge, Button, Skeleton } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { detailOf, isSignedOut } from "@/lib/http";
import { noticePath, useNoticeText } from "@/lib/notice-text";
import { useNoticePages, useReadAll, useReadOne } from "@/lib/notifications";

/**
 * Every notice, not only the newest fifty (Sprint 60, BL-14.9).
 *
 * The panel on the applications page kept the latest fifty and showed what was unread; a person
 * with an old unread notice under a screenful of newer ones could not reach it. This lists them
 * all, a page at a time, says which are new, opens one, and reads one or all. The words come from
 * `lib/notice-text`, the same switch the panel uses, so the two cannot disagree about a notice.
 */
export function NotificationsPage() {
  const t = useTranslations("notificationsPage");
  const format = useFormatter();
  const now = useNow();
  const describe = useNoticeText();
  const signedIn = useIsSignedIn();
  const pages = useNoticePages(signedIn);
  const readOne = useReadOne();
  const readAll = useReadAll();

  if (!signedIn) {
    return <p className="text-sm text-muted">{t("signedOut")}</p>;
  }
  if (pages.isPending) return <Skeleton className="h-48 w-full rounded-xl" />;
  if (isSignedOut(pages.error)) return <SessionExpired />;
  if (pages.isError)
    return <Alert role="alert">{detailOf(pages.error) ?? t("failed")}</Alert>;

  const notices = pages.data.pages.flat();
  const unread = notices.filter((n) => !n.read_at).length;
  const failure = readOne.error ?? readAll.error;

  if (notices.length === 0) {
    return <p className="mt-6 text-muted">{t("empty")}</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">{t("summary", { unread })}</p>
        {unread > 0 && (
          <Button
            variant="secondary"
            size="sm"
            disabled={readAll.isPending}
            onClick={() => readAll.mutate()}
          >
            {t("markAll")}
          </Button>
        )}
      </div>

      {failure && (
        <Alert role="alert" className="mt-3">
          {detailOf(failure) ?? t("actionFailed")}
        </Alert>
      )}

      <ul className="mt-4">
        {notices.map((notice) => {
          const path = noticePath(notice);
          return (
            <li
              key={notice.id}
              className="border-t border-border-token py-3 first:border-t-0"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                {!notice.read_at && <Badge tone="brand">{t("new")}</Badge>}
                <span className="text-sm">{describe(notice)}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted">
                <span>
                  {format.relativeTime(new Date(notice.created_at), now)}
                </span>
                {path && (
                  <Link
                    href={path}
                    className="text-brand underline underline-offset-2"
                  >
                    {t("open")}
                  </Link>
                )}
                {!notice.read_at && (
                  <button
                    type="button"
                    disabled={readOne.isPending}
                    onClick={() => readOne.mutate(notice.id)}
                    className="rounded-sm text-brand underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    {t("markOne")}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {pages.hasNextPage && (
        <div className="mt-4">
          <Button
            variant="secondary"
            disabled={pages.isFetchingNextPage}
            onClick={() => void pages.fetchNextPage()}
          >
            {pages.isFetchingNextPage ? t("loading") : t("older")}
          </Button>
        </div>
      )}
    </div>
  );
}
