import { createApi } from "./api";
import { ApiError } from "./errors";
import { DETAIL_MAX, REASONS, reportFailure, reportListing } from "./report";
import { createTokenStore, type SecretBackend } from "./token-store";

const nothing: SecretBackend = { read: async () => null, write: async () => undefined, remove: async () => undefined };

function harness(answer: () => Response) {
  const calls: { path: string; body: unknown }[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    calls.push({ path: new URL(request.url).pathname, body: JSON.parse(await request.clone().text()) });
    return answer();
  }) as typeof fetch;
  return {
    calls,
    api: createApi({
      baseUrl: "https://api.test",
      tokens: createTokenStore(nothing),
      locale: () => "en",
      appVersion: "1.0.0",
      platform: "android",
      onUpgradeRequired: () => undefined,
      fetch: fetcher,
    }),
  };
}
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("reporting a listing", () => {
  it("knows the six reasons the server accepts", () => {
    expect([...REASONS].sort()).toEqual(
      ["asks_for_money", "discriminatory", "fake_or_misleading", "other", "spam_or_duplicate", "unsafe_or_illegal"].sort(),
    );
  });

  it("reports a vacancy and a course to their own routes", async () => {
    const { api, calls } = harness(() => json(201, { received: true }));
    await reportListing(api, "job", "ward-assistant-1", "fake_or_misleading", "  asks for a fee ");
    await reportListing(api, "course", "phlebotomy-1", "other", "");
    expect(calls.map((c) => c.path)).toEqual(["/jobs/ward-assistant-1/report", "/courses/phlebotomy-1/report"]);
    expect(calls[0].body).toEqual({ reason: "fake_or_misleading", detail: "asks for a fee" });
    expect(calls[1].body).toEqual({ reason: "other", detail: null });
  });

  it("cuts a long detail to the limit", async () => {
    const { api, calls } = harness(() => json(201, { received: true }));
    await reportListing(api, "job", "x", "other", "d".repeat(DETAIL_MAX + 50));
    expect((calls[0].body as { detail: string }).detail).toHaveLength(DETAIL_MAX);
  });

  it("keeps the status and the server's sentence of a refusal", async () => {
    const { api } = harness(() => json(409, { detail: "You have already reported this listing." }));
    await expect(reportListing(api, "job", "x", "other", "")).rejects.toMatchObject({
      status: 409,
      detail: "You have already reported this listing.",
    });
  });
});

describe("what to say when it fails", () => {
  it("says too many, signed out, or the server's own sentence", () => {
    expect(reportFailure(new ApiError(429, null))).toEqual({ key: "tooMany", detail: null });
    expect(reportFailure(new ApiError(401, null))).toEqual({ key: "signedOut", detail: null });
    expect(reportFailure(new ApiError(403, "You manage this listing."))).toEqual({ key: "failed", detail: "You manage this listing." });
    expect(reportFailure(new ApiError(409, "You have already reported this listing."))).toEqual({
      key: "failed",
      detail: "You have already reported this listing.",
    });
    expect(reportFailure(new Error("network"))).toEqual({ key: "failed", detail: null });
  });
});
