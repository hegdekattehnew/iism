import { createApi } from "./api";
import { createTokenStore, type SecretBackend } from "./token-store";
import { ApiError } from "./errors";
import { needsConsent, requestCode, signOut, verifyCode } from "./sign-in";

const nothing: SecretBackend = {
  read: async () => null,
  write: async () => undefined,
  remove: async () => undefined,
};

// A 204 may not carry a body, and `Response` refuses to be built with one.
const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  status === 204
    ? new Response(null, { status, headers })
    : new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json", ...headers },
      });

function harness(answer: (path: string, body: unknown) => Response) {
  const calls: { path: string; body: unknown }[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    const text = request.method === "GET" ? "" : await request.clone().text();
    const body = text ? JSON.parse(text) : null;
    const path = new URL(request.url).pathname;
    calls.push({ path, body });
    return answer(path, body);
  }) as typeof fetch;
  const tokens = createTokenStore(nothing);
  const api = createApi({
    baseUrl: "https://api.test",
    tokens,
    locale: () => "en",
    appVersion: "1.0.0",
    platform: "android",
    onUpgradeRequired: () => undefined,
    fetch: fetcher,
  });
  return { api, tokens, calls };
}

const SIGNED_IN = {
  access_token: "a",
  refresh_token: "r",
  token_type: "bearer",
  expires_in: 900,
  created: false,
};

describe("asking for a code", () => {
  it("returns the cooldown the server set", async () => {
    const { api } = harness(() => json(200, { sent: true, expires_in_seconds: 300, resend_after_seconds: 30 }));
    expect(await requestCode(api, "9810000001")).toEqual({ resendAfterSeconds: 30, debugCode: null });
  });

  it("carries Retry-After on a refusal, so the screen can count down", async () => {
    const { api } = harness(() => json(429, { detail: "Slow down" }, { "retry-after": "17" }));
    const error = await requestCode(api, "9810000001").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(429);
    expect((error as ApiError).retryAfter).toBe(17);
  });
});

describe("verifying it", () => {
  it("stores the session and says whether an account was made", async () => {
    const { api, tokens } = harness(() => json(200, { ...SIGNED_IN, created: true }));
    expect(await verifyCode(api, tokens, "9810000001", "123456")).toEqual({ accountCreated: true });
    expect(tokens.access()).toBe("a");
  });

  it("sends no consent unless the person has agreed to a notice", async () => {
    const { api, tokens, calls } = harness(() => json(200, SIGNED_IN));
    await verifyCode(api, tokens, "9810000001", "123456");
    await verifyCode(api, tokens, "9810000001", "123456", "2026-09-11");
    expect(calls[0].body).toEqual({ phone: "9810000001", code: "123456" });
    expect(calls[1].body).toEqual({ phone: "9810000001", code: "123456", consent_version: "2026-09-11" });
  });

  it("recognises 'agree to the notice first' and stores nothing", async () => {
    const { api, tokens } = harness(() => json(428, { detail: "consent_required" }));
    const error = await verifyCode(api, tokens, "9810000001", "123456").catch((e: unknown) => e);
    expect(needsConsent(error)).toBe(true);
    expect(tokens.access()).toBeNull();
  });

  it("does not mistake a wrong code for a consent prompt", async () => {
    const { api, tokens } = harness(() => json(401, { detail: "Incorrect or expired code" }));
    const error = await verifyCode(api, tokens, "9810000001", "000000").catch((e: unknown) => e);
    expect(needsConsent(error)).toBe(false);
    expect((error as ApiError).detail).toBe("Incorrect or expired code");
  });
});

describe("signing out", () => {
  it("tells the server and clears the phone", async () => {
    const { api, tokens, calls } = harness(() => json(204, {}));
    await tokens.set({ access_token: "a", refresh_token: "r" });
    await signOut(api, tokens);
    expect(calls[0]).toEqual({ path: "/auth/logout", body: { refresh_token: "r" } });
    expect(tokens.access()).toBeNull();
  });

  it("clears the phone even when the server cannot be reached", async () => {
    const { api, tokens } = harness(() => {
      throw new TypeError("Network request failed");
    });
    await tokens.set({ access_token: "a", refresh_token: "r" });
    await signOut(api, tokens).catch(() => undefined);
    expect(tokens.access()).toBeNull();
  });
});
