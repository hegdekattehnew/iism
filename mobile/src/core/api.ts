/**
 * The typed API client. A port of `web/src/lib/api.ts`, with the same behaviour and the same
 * lessons, and four differences that are the whole reason this is a second file:
 *
 * 1. **Tokens are injected** (`TokenStore`, async-backed), not read from `localStorage`.
 * 2. **The language is injected** (`locale()`), not read from `document.documentElement.lang`. The
 *    API resolves the text from `Accept-Language` (ADR-041), so the client never picks.
 * 3. **Every request says which build it is** (`X-App-Version`, `X-App-Platform`), and a **426**
 *    from the API (`AppVersionMiddleware`, ADR-072) reaches `onUpgradeRequired`. An installed app
 *    cannot be updated on demand, so the server must be able to say "update" and the app must be
 *    able to hear it.
 * 4. **A refresh that fails ends the session** through `tokens.clear()`, and the app learns of it
 *    through the store's subscription, not a window event.
 *
 * The two rules that cost the web app a day each are kept: one refresh at a time (the server rotates
 * refresh tokens, so parallel refreshes invalidate each other), and **auth endpoints are matched by
 * exact pathname, never by substring** (`/auth/me` is *not* terminal and must refresh).
 *
 * No React Native import: this file is tested in Node.
 */

import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "../api/schema";
import type { TokenStore } from "./token-store";

export type ApiOptions = {
  baseUrl: string;
  tokens: TokenStore;
  /** The language the app is showing, e.g. "en" or "hi". */
  locale: () => string;
  /** This build's version, e.g. "1.0.0". */
  appVersion: string;
  platform: "android" | "ios";
  /** The API said this build is too old. `minVersion` is what it asked for, when it said. */
  onUpgradeRequired: (minVersion: string | null) => void;
  fetch?: typeof fetch;
};

/** A 401 from these is the final answer, not a stale token. Exact pathnames only. */
export const TERMINAL_401 = [
  "/auth/refresh",
  "/auth/otp/verify",
  "/auth/email/otp/verify",
  "/auth/logout",
  "/auth/logout-all",
] as const;

export function shouldTryRefresh(url: string, baseUrl: string): boolean {
  let pathname: string;
  try {
    pathname = new URL(url, baseUrl).pathname;
  } catch {
    return false;
  }
  return !(TERMINAL_401 as readonly string[]).includes(pathname);
}

export function createApi(options: ApiOptions) {
  const { baseUrl, tokens } = options;
  const doFetch = options.fetch ?? fetch;
  const api = createClient<paths>({ baseUrl, fetch: (request) => doFetch(request) });

  let refreshing: Promise<boolean> | null = null;

  async function tryRefresh(): Promise<boolean> {
    const refresh_token = tokens.refresh();
    if (!refresh_token) return false;
    // Collapse concurrent 401s into one refresh: the server rotates the token.
    refreshing ??= (async () => {
      try {
        const res = await doFetch(`${baseUrl}/auth/refresh`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            ...identity(),
          },
          body: JSON.stringify({ refresh_token }),
        });
        if (!res.ok) {
          await tokens.clear();
          return false;
        }
        await tokens.set(await res.json());
        return true;
      } catch {
        // No network is not a reason to end somebody's session.
        return false;
      } finally {
        refreshing = null;
      }
    })();
    return refreshing;
  }

  function identity(): Record<string, string> {
    return {
      "x-app-version": options.appVersion,
      "x-app-platform": options.platform,
    };
  }

  // An unsent copy of each request, keyed by openapi-fetch's per-request id: by the time
  // `onResponse` runs `fetch()` has consumed the original's body, so cloning it then throws for
  // every POST, PUT and PATCH (the web app's first save after a token expired failed every time).
  const pending = new Map<string, Request>();

  const middleware: Middleware = {
    async onRequest({ request, id }) {
      for (const [name, value] of Object.entries(identity())) request.headers.set(name, value);
      const locale = options.locale();
      if (locale) request.headers.set("accept-language", locale);
      const token = tokens.access();
      if (token) request.headers.set("authorization", `Bearer ${token}`);
      if (shouldTryRefresh(request.url, baseUrl)) pending.set(id, request.clone());
      return request;
    },
    async onResponse({ request, response, id }) {
      const unsent = pending.get(id);
      pending.delete(id);

      if (response.status === 426) {
        options.onUpgradeRequired(response.headers.get("x-min-app-version"));
        return response;
      }
      if (response.status !== 401 || !unsent) return response;
      if (!shouldTryRefresh(request.url, baseUrl)) return response;
      if (!(await tryRefresh())) return response;

      unsent.headers.set("authorization", `Bearer ${tokens.access()}`);
      return doFetch(unsent);
    },
    onError({ id }) {
      pending.delete(id);
    },
  };

  api.use(middleware);
  return api;
}

export type Api = ReturnType<typeof createApi>;
