import { afterEach, describe, expect, it, vi } from "vitest";

import { api, shouldTryRefresh } from "@/lib/api";

/**
 * The first save after the access token expired.
 *
 * `fetch()` consumes a request's body, and openapi-fetch hands that same
 * consumed request to `onResponse`, so retrying with `request.clone()` threw
 * for every write with a body: the person pressed save, got a generic error,
 * pressed it again and it worked. The mock below reads each body exactly as a
 * real `fetch` would, which is what reproduces it.
 */
describe("a write after the access token expired", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("is retried once, with its body intact, after a refresh", async () => {
    localStorage.setItem("iism.access_token", "expired");
    localStorage.setItem("iism.refresh_token", "still-valid");
    const received: { auth: string | null; body: string }[] = [];

    const mock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (new URL(url).pathname === "/auth/refresh") {
        return new Response(JSON.stringify({ access_token: "fresh", refresh_token: "next" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      const request = input as Request;
      const auth = request.headers.get("authorization");
      received.push({ auth, body: await request.text() });
      return auth === "Bearer expired"
        ? new Response(null, { status: 401 })
        : new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    });
    vi.stubGlobal("fetch", mock);

    const body = { headline: "Ward attendant, three years" };
    const { response } = await api.PUT("/me/profile", { body: body as never, fetch: mock });

    expect(response.status).toBe(200);
    expect(received).toEqual([
      { auth: "Bearer expired", body: JSON.stringify(body) },
      { auth: "Bearer fresh", body: JSON.stringify(body) },
    ]);
  });
});

/**
 * Which 401s are worth a refresh.
 *
 * The guard here was `request.url.includes("/auth/")`, written to stop a
 * refresh loop on `/auth/refresh`. `/auth/me` matches that substring too, so
 * the one call every signed-in screen depends on could never trigger a
 * refresh: fifteen minutes after signing in the app decided the person was
 * signed out, with a thirty-day refresh token sitting unused. A whole day of
 * API logs contained zero calls to `/auth/refresh`.
 */

const abs = (p: string) => `http://localhost:8000${p}`;

describe("shouldTryRefresh", () => {
  it("refreshes for /auth/me — the regression this exists to stop", () => {
    expect(shouldTryRefresh(abs("/auth/me"))).toBe(true);
  });

  it("never refreshes in response to a failed refresh", () => {
    // That is the loop the original guard was reaching for.
    expect(shouldTryRefresh(abs("/auth/refresh"))).toBe(false);
  });

  it("does not refresh when a sign-in code was simply wrong", () => {
    expect(shouldTryRefresh(abs("/auth/otp/verify"))).toBe(false);
    expect(shouldTryRefresh(abs("/auth/email/otp/verify"))).toBe(false);
  });

  it("does not refresh a session being ended on purpose", () => {
    expect(shouldTryRefresh(abs("/auth/logout"))).toBe(false);
    expect(shouldTryRefresh(abs("/auth/logout-all"))).toBe(false);
  });

  it("refreshes for every ordinary signed-in call", () => {
    for (const path of [
      "/me/profile",
      "/me/matches",
      "/me/organisations",
      "/org/acme/jobs",
      "/org/acme/deletion",
      "/me/applications",
    ]) {
      expect(shouldTryRefresh(abs(path)), path).toBe(true);
    }
  });

  it("matches the pathname, not a substring", () => {
    // The whole reason the original was wrong. A query string or a path that
    // merely contains a terminal route's name must not disable refreshing.
    expect(shouldTryRefresh(abs("/auth/me?x=1"))).toBe(true);
    expect(shouldTryRefresh(abs("/org/auth-refresh-co/jobs"))).toBe(true);
    expect(shouldTryRefresh(abs("/jobs?next=/auth/refresh"))).toBe(true);
  });

  it("does not throw on a URL it cannot parse", () => {
    // A middleware that throws takes every request with it.
    expect(() => shouldTryRefresh("::::")).not.toThrow();
  });
});
