import { createApi, shouldTryRefresh, TERMINAL_401 } from "./api";
import { createTokenStore, type SecretBackend } from "./token-store";

const BASE = "https://api.test";

const nothing: SecretBackend = {
  read: async () => null,
  write: async () => undefined,
  remove: async () => undefined,
};

type Seen = { url: string; method: string; headers: Headers; body: string };

/** A fake network: answers by a script, and records what it was asked. */
function network(script: (seen: Seen, count: number) => Response | Promise<Response>) {
  const seen: Seen[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    const record: Seen = {
      url: new URL(request.url).pathname,
      method: request.method,
      headers: request.headers,
      body: request.method === "GET" ? "" : await request.clone().text(),
    };
    seen.push(record);
    return script(record, seen.length);
  }) as typeof fetch;
  return { seen, fetcher };
}

// A 204 may not carry a body, and `Response` refuses to be built with one.
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  status === 204
    ? new Response(null, { status, headers })
    : new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json", ...headers },
      });

async function client(
  script: Parameters<typeof network>[0],
  options: { locale?: string; upgrade?: (min: string | null) => void } = {},
) {
  const net = network(script);
  const tokens = createTokenStore(nothing);
  await tokens.set({ access_token: "old", refresh_token: "r-old" });
  const api = createApi({
    baseUrl: BASE,
    tokens,
    locale: () => options.locale ?? "hi",
    appVersion: "1.2.3",
    platform: "android",
    onUpgradeRequired: options.upgrade ?? (() => undefined),
    fetch: net.fetcher,
  });
  return { api, tokens, ...net };
}

describe("what every request says", () => {
  it("names the build, the platform and the language, and carries the token", async () => {
    const { api, seen } = await client(() => json(200, { status: "ok" }));
    await api.GET("/health");
    const headers = seen[0].headers;
    expect(headers.get("x-app-version")).toBe("1.2.3");
    expect(headers.get("x-app-platform")).toBe("android");
    expect(headers.get("accept-language")).toBe("hi");
    expect(headers.get("authorization")).toBe("Bearer old");
  });

  it("sends no authorization when signed out", async () => {
    const net = network(() => json(200, {}));
    const api = createApi({
      baseUrl: BASE,
      tokens: createTokenStore(nothing),
      locale: () => "en",
      appVersion: "1.0.0",
      platform: "ios",
      onUpgradeRequired: () => undefined,
      fetch: net.fetcher,
    });
    await api.GET("/health");
    expect(net.seen[0].headers.get("authorization")).toBeNull();
  });
});

describe("a stale access token", () => {
  const refreshed = { access_token: "new", refresh_token: "r-new", token_type: "bearer" };

  it("is refreshed once and the original request is retried with the new token, body intact", async () => {
    const { api, seen, tokens } = await client((req) => {
      if (req.url === "/auth/refresh") return json(200, refreshed);
      return req.headers.get("authorization") === "Bearer new"
        ? json(200, {})
        : json(401, { detail: "expired" });
    });
    await api.GET("/me/profile");
    const sent = seen.map((s) => `${s.method} ${s.url} ${s.headers.get("authorization")}`);
    expect(sent).toEqual([
      "GET /me/profile Bearer old",
      "POST /auth/refresh null",
      "GET /me/profile Bearer new",
    ]);
    expect(tokens.access()).toBe("new");
    expect(tokens.refresh()).toBe("r-new");
  });

  it("keeps a POST body across the retry (the web app's first save used to fail)", async () => {
    const { api, seen } = await client((req) => {
      if (req.url === "/auth/refresh") return json(200, refreshed);
      return req.headers.get("authorization") === "Bearer new"
        ? json(201, {})
        : json(401, { detail: "expired" });
    });
    await api.POST("/me/applications", { body: { job_slug: "ward-assistant" } });
    const sent = seen.filter((s) => s.url === "/me/applications");
    expect(sent).toHaveLength(2);
    expect(JSON.parse(sent[1].body)).toEqual({ job_slug: "ward-assistant" });
  });

  it("is refreshed for /auth/me too, which a substring check once exempted", async () => {
    const { api, seen } = await client((req) => {
      if (req.url === "/auth/refresh") return json(200, refreshed);
      return req.headers.get("authorization") === "Bearer new"
        ? json(200, { id: "u" })
        : json(401, {});
    });
    const { response } = await api.GET("/auth/me");
    expect(response.status).toBe(200);
    expect(seen.some((s) => s.url === "/auth/refresh")).toBe(true);
  });

  it("collapses concurrent 401s into one refresh", async () => {
    const { api, seen } = await client(async (req) => {
      if (req.url === "/auth/refresh") {
        await new Promise((resolve) => setTimeout(resolve, 20));
        return json(200, refreshed);
      }
      return req.headers.get("authorization") === "Bearer new" ? json(200, {}) : json(401, {});
    });
    await Promise.all([api.GET("/auth/me"), api.GET("/auth/me"), api.GET("/auth/me")]);
    expect(seen.filter((s) => s.url === "/auth/refresh")).toHaveLength(1);
  });

  it("ends the session when the refresh is refused, and hands back the 401", async () => {
    const { api, tokens } = await client((req) =>
      req.url === "/auth/refresh" ? json(401, { detail: "revoked" }) : json(401, {}),
    );
    const { response } = await api.GET("/auth/me");
    expect(response.status).toBe(401);
    expect(tokens.access()).toBeNull();
  });

  it("keeps the session when the refresh could not reach the network", async () => {
    const net = network((req) => {
      if (req.url === "/auth/refresh") throw new TypeError("Network request failed");
      return json(401, {});
    });
    const tokens = createTokenStore(nothing);
    await tokens.set({ access_token: "old", refresh_token: "r-old" });
    const api = createApi({
      baseUrl: BASE,
      tokens,
      locale: () => "en",
      appVersion: "1.0.0",
      platform: "android",
      onUpgradeRequired: () => undefined,
      fetch: net.fetcher,
    });
    await api.GET("/auth/me");
    expect(tokens.refresh()).toBe("r-old");
  });

  it("is never refreshed on the endpoints where a 401 is the answer", async () => {
    const { api, seen } = await client(() => json(401, { detail: "Incorrect or expired code" }));
    await api.POST("/auth/otp/verify", { body: { phone: "9810000001", code: "000000" } });
    expect(seen.some((s) => s.url === "/auth/refresh")).toBe(false);
  });
});

describe("which 401s are worth a refresh", () => {
  it("is decided on the exact pathname, never a substring", () => {
    expect(shouldTryRefresh(`${BASE}/auth/me`, BASE)).toBe(true);
    expect(shouldTryRefresh(`${BASE}/me/profile`, BASE)).toBe(true);
    for (const path of TERMINAL_401) expect(shouldTryRefresh(`${BASE}${path}`, BASE)).toBe(false);
  });

  it("treats an unreadable URL as not worth it", () => {
    expect(shouldTryRefresh("http://", BASE)).toBe(false);
  });
});

describe("an app the server no longer supports", () => {
  it("is told, with the minimum when the server gave one", async () => {
    const heard: (string | null)[] = [];
    const { api } = await client(() => json(426, { detail: "Update" }, { "x-min-app-version": "2.0.0" }), {
      upgrade: (min) => heard.push(min),
    });
    const { response } = await api.GET("/auth/me");
    expect(response.status).toBe(426);
    expect(heard).toEqual(["2.0.0"]);
  });

  it("is not sent round the refresh loop", async () => {
    const { api, seen } = await client(() => json(426, {}));
    await api.GET("/auth/me");
    expect(seen).toHaveLength(1);
  });
});
