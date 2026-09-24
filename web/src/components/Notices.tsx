"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { Alert, Button } from "@/components/ui";
import { api } from "@/lib/api";
import { ApiError, detailOf, readDetail } from "@/lib/http";

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
  const format = useFormatter();
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
      if (error) throw new ApiError(status, readDetail(error));
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
        {unread.map((notice) => (
          <li key={notice.id} className="text-sm">
            <span>
              {t("statusChanged", {
                vacancy: String(notice.payload.vacancy ?? ""),
                organisation: String(notice.payload.organisation ?? ""),
                status: t(`status.${String(notice.payload.status ?? "applied")}`),
              })}
            </span>{" "}
            <span className="text-xs text-muted">
              {format.relativeTime(new Date(notice.created_at))}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
