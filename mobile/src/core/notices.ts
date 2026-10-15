/**
 * Putting a notice into words, and finding where it points. The web's `lib/notice-text.ts`, ported
 * with the same templates and the same catalogue keys (`notices.*`), so the two cannot disagree
 * about what a notice says.
 *
 * **The words are rendered here, not stored**: the API returns a template name and a payload, so a
 * notice queued while somebody was reading Hindi still reads correctly in English (ADR-041). A
 * template this does not know says the generic line rather than nothing.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";
import { resolveLink } from "./links";
import type { Translate } from "./labels";

export type Notice = components["schemas"]["NotificationOut"];
export type NoticeData = Pick<Notice, "template" | "payload">;

/** The page size the web uses too. */
export const NOTICE_PAGE_SIZE = 30;

const text = (value: unknown): string => String(value ?? "");

export function noticeText(notice: NoticeData, t: Translate): string {
  const p = notice.payload ?? {};
  const vacancy = text(p.vacancy);
  const organisation = text(p.organisation);
  switch (notice.template) {
    case "application_status_changed":
      return t("statusChanged", { vacancy, organisation, status: t(`status.${text(p.status ?? "applied")}`) });
    case "application_status_message":
      // The words of the message are on the application, never in the notice (ADR-070).
      return t("statusMessage", { vacancy, organisation, status: t(`status.${text(p.status ?? "applied")}`) });
    case "job_alert":
      return t("jobAlert", { vacancy, organisation });
    case "vacancy_closed":
      return t("vacancyClosed", { vacancy });
    case "course_interest_status_changed":
      return t("interestStatusChanged", {
        course: text(p.course),
        organisation,
        status: t(`interestStatus.${text(p.status ?? "contacted")}`),
      });
    case "sponsor_offer":
      // Names the organisation, the standard and the course, and nothing about the person.
      return t("sponsorOffer", { organisation, vacancy, standard: text(p.standard), course: text(p.course) });
    case "grievance_update":
      // Where a message the person sent us stands. Never the operator's note.
      return t("grievanceUpdate", {
        reference: text(p.reference),
        status: t(`grievanceStatus.${text(p.status ?? "acknowledged")}`),
      });
    default:
      return t("generic");
  }
}

/** Where a notice points inside the app, or `null`. A notice never links off-site. */
export function noticePath(notice: NoticeData): string | null {
  if (notice.template === "grievance_update") return "/contact";
  return resolveLink(notice.payload?.path);
}

/** The cursor for the next (older) page: the last notice's time **and** id, or `undefined` at the end. */
export function nextCursor(
  last: readonly Pick<Notice, "created_at" | "id">[],
): { before: string; before_id: string } | undefined {
  if (last.length < NOTICE_PAGE_SIZE) return undefined;
  const oldest = last[last.length - 1];
  return { before: oldest.created_at, before_id: oldest.id };
}
