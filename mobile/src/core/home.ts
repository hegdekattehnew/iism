/**
 * What a signed-in job seeker's home says (Sprint 70, UI-19), as rules free of React Native so each is
 * tested in Node.
 *
 * **Applications with news** are the ones an employer has acted on lately: a status other than
 * "applied" (shortlisted, rejected, hired, completed, no show) or a message, changed in the last
 * `NEWS_DAYS`. There is no "read" state to consult, so without a window a rejection from last spring
 * would be news for ever; with one, the home says what moved this fortnight and the applications
 * screen says everything. A withdrawn application is the person's own act, never news.
 */

import type { ApplicationStatus } from "./applying";

export const NEWS_DAYS = 14;

const DAY_MS = 86_400_000;

type Row = {
  status: ApplicationStatus;
  status_message?: string | null;
  status_message_at?: string | null;
  updated_at: string;
};

export function hasNews(application: Row, now: number): boolean {
  if (application.status === "withdrawn") return false;
  const employerActed =
    application.status !== "applied" || Boolean(application.status_message?.trim());
  if (!employerActed) return false;
  const changed = Date.parse(application.status_message_at ?? application.updated_at);
  if (Number.isNaN(changed)) return false;
  return now - changed <= NEWS_DAYS * DAY_MS;
}

export const applicationsWithNews = (applications: readonly Row[], now: number): number =>
  applications.filter((a) => hasNews(a, now)).length;
