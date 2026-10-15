/**
 * The rules about applying, withdrawing and registering interest, in one place and free of React
 * Native, so each is tested in Node. Ported from the web's `ApplyPanel`.
 *
 * - **What a candidate may take back** is the server's `WITHDRAWABLE_STATUSES`, typed against the
 *   schema's own status union: once an employer has decided, withdrawing would rewrite their record
 *   rather than end the candidate's own interest. A renamed status is a compile error here, not a
 *   button that silently never appears.
 * - **A failure is named by its status**, one table, so the screens cannot disagree about what a 409
 *   or a 429 means. The generic line is the fallback for a status nobody planned for.
 */

import type { components } from "../api/schema";

export type ApplicationStatus = components["schemas"]["ApplicationOut"]["status"];
export type InterestStatus = components["schemas"]["InterestOut"]["status"];

export const WITHDRAWABLE: readonly ApplicationStatus[] = ["applied", "shortlisted"];

export const canWithdraw = (status: ApplicationStatus): boolean => WITHDRAWABLE.includes(status);

/** A withdrawn application is over; every other status is still a live row the candidate holds. */
export const isLive = (application: { status: ApplicationStatus }): boolean =>
  application.status !== "withdrawn";

export type ApplyFailure = "errorDuplicate" | "errorCap" | "errorSeeker" | "errorGeneric";

/** Applying, and registering interest in a course, fail the same way for the same reasons. */
export function applyFailureKey(status: number | null): ApplyFailure {
  if (status === 409) return "errorDuplicate";
  if (status === 429) return "errorCap";
  if (status === 403) return "errorSeeker";
  return "errorGeneric";
}

/** Withdrawing: a 409 means a decision was made in the meantime. */
export function withdrawFailureKey(status: number | null): "errorWithdrawDecided" | "errorGeneric" {
  return status === 409 ? "errorWithdrawDecided" : "errorGeneric";
}

export const MESSAGE_MAX = 1000;
