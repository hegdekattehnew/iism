/**
 * What a person can do about their own account from the phone: see what they agreed to, take their
 * data with them, and delete it all. The stores require the last, and the DPDP Act the first two.
 *
 * - **The export is text for the share sheet**, built from the server's own document. The server
 *   never puts a device token in it (ADR-075); this adds nothing and removes nothing.
 * - **Deleting is two steps**: the server's preview of what would go with the account (or what
 *   blocks it), then the act. A person who is the only owner of an organisation others belong to is
 *   told so and cannot proceed: the server refuses with a 409 either way.
 *
 * No React Native import: this file is tested in Node.
 */

import type { Api } from "./api";
import { unwrap } from "./public";
import { ApiError, readDetail } from "./errors";

export type AccountExport = Record<string, unknown>;

export type DeletionPreview = {
  organisations_deleted: { slug: string; name: string; listings: number }[];
  blocked_by: { slug: string; name: string; listings: number }[];
};

export async function fetchExport(api: Api): Promise<AccountExport> {
  return unwrap(await api.GET("/me/account/export")) as AccountExport;
}

/** The file a person saves or sends: a name that says what it is and when, and the document. */
export function exportFile(data: AccountExport, today: string): { filename: string; text: string } {
  return { filename: `iism-my-data-${today}.json`, text: JSON.stringify(data, null, 2) };
}

export async function fetchDeletionPreview(api: Api): Promise<DeletionPreview> {
  return unwrap(await api.GET("/me/account/deletion")) as DeletionPreview;
}

/** Nothing blocks it: the account may be deleted. */
export const canDelete = (preview: DeletionPreview): boolean => preview.blocked_by.length === 0;

export async function deleteAccount(api: Api): Promise<void> {
  const result = await api.DELETE("/me/account");
  const failure: unknown = result.error;
  if (failure !== undefined && failure !== null) {
    throw new ApiError(result.response.status, readDetail(failure));
  }
}

/** "You agreed to the notice of <version> on <date>", or `null` when no consent is recorded. */
export function consentOf(me: { consent_version?: string | null; consented_at?: string | null }): {
  version: string;
  at: string;
} | null {
  return me.consent_version && me.consented_at ? { version: me.consent_version, at: me.consented_at } : null;
}

// ----------------------------------------------------------------------------- consent (Sprint 72)

/** Where the person stands on consent, and what withdrawing would take back (ADR-082). */
export type ConsentState = {
  consent_version: string | null;
  consented_at: string | null;
  notice_version: string;
  current: boolean;
  withdrawn: boolean;
  consent_withdrawn_at: string | null;
  live_applications: number;
  live_interests: number;
};

export async function fetchConsent(api: Api): Promise<ConsentState> {
  return unwrap(await api.GET("/me/account/consent")) as ConsentState;
}

/** Pause the account, keeping it. The server ends every disclosure that exists and stops new ones. */
export async function withdrawConsent(api: Api): Promise<ConsentState> {
  return unwrap(await api.POST("/me/account/consent/withdraw")) as ConsentState;
}

/**
 * Confirm the notice in force: re-consent for a stale version, restore after a withdrawal. The
 * version sent is this build's own, and the server refuses any other (a test holds the two equal).
 */
export async function confirmConsent(api: Api, version: string): Promise<ConsentState> {
  return unwrap(
    await api.POST("/me/account/consent", { body: { consent_version: version } }),
  ) as ConsentState;
}

/**
 * What the Me tab and the account screen say about consent, from `/auth/me`. A stale notice **asks**
 * and never blocks; a withdrawal says the account is paused. An account created before consent was
 * recorded has no version at all, and that is the account screen's own sentence, not a prompt.
 */
export function consentPrompt(me: {
  consent_version?: string | null;
  consent_current?: boolean;
  consent_withdrawn?: boolean;
}): "paused" | "stale" | null {
  if (me.consent_withdrawn) return "paused";
  if (me.consent_current === false && me.consent_version) return "stale";
  return null;
}
