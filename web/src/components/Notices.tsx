"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useNow, useTranslations } from "next-intl";

import { Alert, Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { apiErrorFrom, detailOf } from "@/lib/http";
import { noticePath, useNoticeText } from "@/lib/notice-text";

// A notice about an application points at `/applications`, which is where this panel already is.
const ON_THIS_PAGE = ["application_status_changed", "application_status_message"];

/**
 * What changed since you last looked.
 *
 * In-app rather than email because most candidates signed up with a phone and
 * have no address, and SMS waits on DLT registration — so this is the channel
 * that actually reaches them.
 *
 * **The words are rendered here, not stored.** The API returns a template name
 * and a payload, so a notice queued while someone was reading Hindi still
 * reads correctly when they come back in English.
 */
export function Notices() {
  const t = useTranslations("notices");
  const describe = useNoticeText();
  const format = useFormatter();
  // Passed explicitly: with no `now`, next-intl logs an ENVIRONMENT_FALLBACK error per notice.
  const now = useNow();
  const qc = useQueryClient();

  const { data } = useQuery({
    queryKey: ["me", "notifications"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/notifications");
      if (error || !data) throw new Error("notifications failed");
      return data;
    },
  });

  const markRead = useMutation({
    mutationFn: async () => {
      // `error` was not read at all here. openapi-fetch **resolves** on a
      // non-2xx, so a 401 or a 500 ran `onSuccess`, the query refetched, the
      // notices came back still unread -- and the button did nothing, for
      // ever, with nothing anywhere saying why.
      const { error, response } = await api.POST("/me/notifications/read");
      // Read before the check: `if (error)` narrows the destructured group,
      // and this endpoint declares no error body, so `response` would be
      // `never` inside the branch.
      const status = response.status;
      if (error) throw apiErrorFrom(status, error);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["me", "notifications"] });
    },
  });

  const notices = data ?? [];
  const unread = notices.filter((n) => !n.read_at);
  if (unread.length === 0) return null;

  return (
    <section
      aria-labelledby="notices-heading"
      className="mt-8 rounded-xl border border-border-token bg-surface p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="notices-heading" className="text-base font-semibold">
          {t("title", { count: unread.length })}
        </h2>
        <Button
          variant="ghost"
          size="sm"
          disabled={markRead.isPending}
          onClick={() => markRead.mutate()}
        >
          {t("markRead")}
        </Button>
      </div>
      {markRead.isError && (
        <Alert role="alert" className="mt-3">
          {detailOf(markRead.error) ?? t("markReadFailed")}
        </Alert>
      )}
      <ul className="mt-3 space-y-2">
        {unread.map((notice) => {
          // A status notice is shown on the page its link would open.
          const path = ON_THIS_PAGE.includes(notice.template) ? null : noticePath(notice);
          return (
            <li key={notice.id} className="text-sm">
              <span>{describe(notice)}</span>{" "}
              {path && (
                <Link href={path} className="text-brand underline underline-offset-2 hover:text-brand-strong">
                  {t("open")}
                </Link>
              )}{" "}
              <span className="text-xs text-muted">
                {format.relativeTime(new Date(notice.created_at), now)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
