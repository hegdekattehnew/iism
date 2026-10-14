/**
 * The phone sign-in flow as plain functions over the API client, so the rules are testable in Node
 * and the screens stay thin (no business logic in the UI, as on the web).
 *
 * One door for a person, new or returning, as on the web (ADR-032, Sprint 18): ask for a code,
 * verify it. A number with no account answers **428** *after* the code proves the caller holds the
 * phone (never before: asking earlier would say "is this number registered?" to anyone, ADR-038);
 * the screen then asks the person to agree to the privacy notice and verifies again with the
 * version they agreed to.
 */

import type { Api } from "./api";
import { ApiError, readDetail } from "./errors";
import type { TokenStore } from "./token-store";

/** `api/core/config.py`'s `PRIVACY_NOTICE_VERSION`; `tests/test_mobile_foundations.py` compares them. */
export const PRIVACY_NOTICE_VERSION = "2026-09-11";

export type CodeRequested = {
  /** Seconds until another code may be asked for (the server's cooldown). */
  resendAfterSeconds: number;
  /** Development only: the API echoes the code when `OTP_EXPOSE_IN_RESPONSE` is on. */
  debugCode: string | null;
};

export async function requestCode(api: Api, phone: string): Promise<CodeRequested> {
  const { data, error, response } = await api.POST("/auth/otp/request", { body: { phone } });
  if (error || !data) {
    throw new ApiError(response.status, readDetail(error), retryAfter(response));
  }
  return {
    resendAfterSeconds: data.resend_after_seconds ?? 0,
    debugCode: data.debug_code ?? null,
  };
}

export type Verified = { accountCreated: boolean };

/**
 * Verify the code and store the session. Throws `ApiError`; a **428** means "agree to the notice
 * first" and is for the screen to recognise (`needsConsent`), not an error to show.
 */
export async function verifyCode(
  api: Api,
  tokens: TokenStore,
  phone: string,
  code: string,
  agreedTo?: string,
): Promise<Verified> {
  const { data, error, response } = await api.POST("/auth/otp/verify", {
    body: { phone, code, ...(agreedTo ? { consent_version: agreedTo } : {}) },
  });
  if (error || !data) throw new ApiError(response.status, readDetail(error));
  await tokens.set({ access_token: data.access_token, refresh_token: data.refresh_token });
  return { accountCreated: Boolean(data.created) };
}

export const needsConsent = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 428;

export async function signOut(api: Api, tokens: TokenStore): Promise<void> {
  const refresh_token = tokens.refresh();
  try {
    if (refresh_token) await api.POST("/auth/logout", { body: { refresh_token } });
  } finally {
    // Whatever the server said, this phone is signed out.
    await tokens.clear();
  }
}

function retryAfter(response: Response): number {
  const seconds = Number(response.headers.get("retry-after"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : 0;
}
