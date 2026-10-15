/**
 * Reporting a vacancy or a course (ADR-069). A report is accountable, so it needs an account: signed
 * out, the control says to sign in rather than offering a form that cannot succeed. The server's own
 * sentences are shown for the refusals a person can act on ("you manage this listing", "you have
 * already reported it"), and the person is told only that it was received: what an operator decides,
 * and who reported, are for nobody else to be told.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";
import type { Api } from "./api";
import { ApiError, readDetail } from "./errors";

export type Reason = components["schemas"]["ReportIn"]["reason"];
export type Target = "job" | "course";

/** Every reason, as a record keyed by the schema's own union: the server adding one fails to compile. */
const ALL: Record<Reason, true> = {
  asks_for_money: true,
  fake_or_misleading: true,
  discriminatory: true,
  unsafe_or_illegal: true,
  spam_or_duplicate: true,
  other: true,
};
export const REASONS = Object.keys(ALL) as Reason[];

export const DETAIL_MAX = 1000;

export async function reportListing(
  api: Api,
  target: Target,
  slug: string,
  reason: Reason,
  detail: string,
): Promise<void> {
  const body = { reason, detail: detail.trim() ? detail.trim().slice(0, DETAIL_MAX) : null };
  const result =
    target === "job"
      ? await api.POST("/jobs/{slug}/report", { params: { path: { slug } }, body })
      : await api.POST("/courses/{slug}/report", { params: { path: { slug } }, body });
  const failure: unknown = result.error;
  if (failure !== undefined && failure !== null) {
    throw new ApiError(result.response.status, readDetail(failure));
  }
}

export type ReportFailure = { key: "tooMany" | "signedOut" | "failed"; detail: string | null };

/** What to say: too many today, signed out, or the server's own sentence (409, 403), else generic. */
export function reportFailure(error: unknown): ReportFailure {
  if (error instanceof ApiError) {
    if (error.status === 429) return { key: "tooMany", detail: null };
    if (error.status === 401) return { key: "signedOut", detail: null };
    return { key: "failed", detail: error.detail };
  }
  return { key: "failed", detail: null };
}
