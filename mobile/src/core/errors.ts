/**
 * Failures that keep what the server said. Ported from `web/src/lib/http.ts`, with the same two
 * rules and for the same reasons:
 *
 * - **Never throw away the server's sentence.** A fixed "something went wrong" is wrong about *why*
 *   whenever the server knew.
 * - **401 and 403 are opposite answers.** 401 is "you are signed out"; 403 is "this is not yours".
 *   A screen must not collapse them.
 *
 * No React Native import: this file is tested in Node.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string | null,
    /** Seconds the server asked the caller to wait (`Retry-After`), or 0. */
    readonly retryAfter = 0,
  ) {
    super(detail ?? String(status));
    this.name = "ApiError";
  }
}

/** FastAPI's `detail`: a string, or a list of `{loc, msg}` for a 422. */
export function readDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) =>
        item && typeof item === "object" && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter((part): part is string => Boolean(part));
    return parts.length ? parts.join(". ") : null;
  }
  return null;
}

export function statusOf(error: unknown): number | null {
  if (error instanceof ApiError) return error.status;
  if (!(error instanceof Error)) return null;
  const code = Number(error.message);
  return Number.isInteger(code) && code >= 100 && code <= 599 ? code : null;
}

export const isSignedOut = (error: unknown): boolean => statusOf(error) === 401;

/** The server asked the client to update: see `core/api.ts` and ADR-072. */
export const isUpgradeRequired = (error: unknown): boolean => statusOf(error) === 426;

/** Seconds the server asked the caller to wait (`Retry-After`), or 0. */
export function retryAfterSeconds(response: { headers: Headers }): number {
  const seconds = Number(response.headers.get("retry-after"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : 0;
}
