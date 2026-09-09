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
    const token = getAccessToken();
    if (token) request.headers.set("authorization", `Bearer ${token}`);
    return request;
  },
  async onResponse({ request, response }) {
    if (typeof window === "undefined") return response;
    if (response.status !== 401) return response;
    if (request.url.includes("/auth/")) return response;

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
