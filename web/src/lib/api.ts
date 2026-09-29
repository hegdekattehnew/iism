import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./api-schema";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./auth";

/**
 * Typed API client. `api-schema.d.ts` is generated from the FastAPI OpenAPI
 * document (`npm run gen:api`), so a breaking backend change becomes a
 * TypeScript error here rather than a runtime surprise (ADR-016).
 */
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl });

/**
 * Attaches the access token, and on a 401 tries exactly one refresh before
 * giving up. One attempt, not a loop: a refresh that fails means the session is
 * genuinely over, and retrying would spin.
 */
let refreshing: Promise<boolean> | null = null;

/**
 * Auth endpoints where a 401 is the final answer, not a stale token.
 *
 * **`/auth/me` is deliberately absent, and its absence is the point.** The
 * guard here used to be `request.url.includes("/auth/")`, written to stop a
 * refresh loop on `/auth/refresh` -- and `/auth/me` matches that substring
 * too. So the one call every signed-in screen depends on could never trigger
 * a refresh: fifteen minutes after signing in, `useMemberships` got a 401, the
 * middleware handed it straight back, and the whole app decided the person was
 * signed out while a perfectly good thirty-day refresh token sat in
 * localStorage unused. The API log for a whole day of use contained **zero**
 * calls to `/auth/refresh`.
 *
 * Matched on the exact pathname rather than a substring, because that is the
 * mistake this list exists to stop repeating.
 */
const TERMINAL_401 = [
  // Refreshing in response to a failed refresh is the loop.
  "/auth/refresh",
  // A 401 here means "incorrect or expired code", which no token fixes.
  "/auth/otp/verify",
  "/auth/email/otp/verify",
  // Nothing to retry: the session is being ended on purpose.
  "/auth/logout",
  "/auth/logout-all",
];

/** Whether a 401 from this URL is worth one refresh attempt. */
export function shouldTryRefresh(url: string): boolean {
  let pathname: string;
  try {
    pathname = new URL(url, baseUrl).pathname;
  } catch {
    return false;
  }
  return !TERMINAL_401.includes(pathname);
}

async function tryRefresh(): Promise<boolean> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;

  // Collapse concurrent 401s into a single refresh; the server rotates tokens,
  // so parallel refreshes would invalidate each other.
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
      if (!res.ok) {
        clearTokens();
        return false;
      }
      setTokens(await res.json());
      return true;
    } finally {
      refreshing = null;
    }
  })();

  return refreshing;
}

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    if (typeof window === "undefined") return request;
    // The language this page is in, on every call -- one middleware rather
    // than a parameter at forty call sites. The API resolves the text from it
    // (ADR-041); the client no longer picks between two fields.
    const locale = document.documentElement.lang;
    if (locale) request.headers.set("accept-language", locale);
    const token = getAccessToken();
    if (token) request.headers.set("authorization", `Bearer ${token}`);
    return request;
  },
  async onResponse({ request, response }) {
    if (typeof window === "undefined") return response;
    if (response.status !== 401) return response;
    if (!shouldTryRefresh(request.url)) return response;

    if (!(await tryRefresh())) return response;

    const retry = request.clone();
    retry.headers.set("authorization", `Bearer ${getAccessToken()}`);
    return fetch(retry);
  },
};

api.use(authMiddleware);

export type DeepHealth =
  paths["/health/deep"]["get"]["responses"][200]["content"]["application/json"];
export type ComponentHealth = DeepHealth["components"][number];
