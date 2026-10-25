"use client";

import { useTranslations } from "next-intl";

/**
 * The one place a notice is put into words (Sprint 60, BL-14.9).
 *
 * It lived inside `Notices.tsx` until the notification page needed it too: two switches over the
 * same templates are how one of them ends up saying "You have an update." for a notice the other
 * words correctly. **The words are rendered here, not stored**: the API returns a template name and
 * a payload, so a notice queued while someone was reading Hindi still reads correctly in English.
 */
export type NoticeData = { template: string; payload: Record<string, unknown> };

/** An in-app path from a payload, and nothing else: a notice never links off-site. */
export function linkOf(value: unknown): string | null {
  return typeof value === "string" &&
    value.startsWith("/") &&
    !value.startsWith("//")
    ? value
    : null;
}

/** Where a notice points. A grievance update carries no path of its own: its page is fixed. */
export function noticePath(notice: NoticeData): string | null {
  return notice.template === "grievance_update"
    ? "/grievance"
    : linkOf(notice.payload.path);
}

export function useNoticeText(): (notice: NoticeData) => string {
  const t = useTranslations("notices");
  return (notice) => {
    const vacancy = String(notice.payload.vacancy ?? "");
    const organisation = String(notice.payload.organisation ?? "");
    switch (notice.template) {
      case "application_status_changed":
        return t("statusChanged", {
          vacancy,
          organisation,
          status: t(`status.${String(notice.payload.status ?? "applied")}`),
        });
      case "application_status_message":
        // The words of the message are on the application, never in the notice (ADR-070).
        return t("statusMessage", {
          vacancy,
          organisation,
          status: t(`status.${String(notice.payload.status ?? "applied")}`),
        });
      case "job_alert":
        return t("jobAlert", { vacancy, organisation });
      case "vacancy_closed":
        return t("vacancyClosed", { vacancy });
      case "course_interest_status_changed":
        return t("interestStatusChanged", {
          course: String(notice.payload.course ?? ""),
          organisation,
          status: t(
            `interestStatus.${String(notice.payload.status ?? "contacted")}`,
          ),
        });
      case "batch_cancelled":
        // Fixed words and a reason *code*: nothing about the centre's address or any free text.
        return t("batchCancelled", {
          course: String(notice.payload.course ?? ""),
          reason: t(`batchReason.${String(notice.payload.reason ?? "by_organisation")}`),
        });
      case "batch_interest_status_changed":
        return t("batchInterestStatusChanged", {
          course: String(notice.payload.course ?? ""),
          organisation,
          status: t(`batchInterestStatus.${String(notice.payload.status ?? "contacted")}`),
        });
      case "sponsor_offer":
        // Names the organisation, the standard and the course, and nothing about the person: the
        // employer does not know who they are.
        return t("sponsorOffer", {
          organisation,
          vacancy,
          standard: String(notice.payload.standard ?? ""),
          course: String(notice.payload.course ?? ""),
        });
      case "grievance_update":
        // Where a message the person sent us stands. Never the operator's note.
        return t("grievanceUpdate", {
          reference: String(notice.payload.reference ?? ""),
          status: t(
            `grievanceStatus.${String(notice.payload.status ?? "acknowledged")}`,
          ),
        });
      default:
        return t("generic");
    }
  };
}
