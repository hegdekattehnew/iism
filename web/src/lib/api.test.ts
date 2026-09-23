import { describe, expect, it } from "vitest";

import { shouldTryRefresh } from "@/lib/api";

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
