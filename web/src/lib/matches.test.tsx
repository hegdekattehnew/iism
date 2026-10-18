import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MATCHES_FETCH, useMyScores } from "@/lib/matches";
import { resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

let qc: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  world.memberships = [{ role: "owner", tenant: { slug: "me", name: "Me", tenant_type: "personal" } }];
  GET.mockResolvedValue({ data: { items: [{ job: { slug: "a" }, score: 80 }, { job: { slug: "b" }, score: 0 }], total: 2 } });
});

/** Sprint 84, BL-19.15: the score a job card shows is the matches page's own query. */
describe("the scores a seeker has", () => {
  it("maps each vacancy slug to its score, a score of zero included", async () => {
    const { result } = renderHook(() => useMyScores(), { wrapper });
    await waitFor(() => expect(result.current.scores.size).toBe(2));
    expect(result.current.scores.get("a")).toBe(80);
    expect(result.current.scores.get("b")).toBe(0);
    expect(result.current.scores.has("c")).toBe(false);
    expect(result.current.isSeeker).toBe(true);
  });

  it("is the query the matches page runs: one key, so one request and one invalidation reach both", async () => {
    const { result } = renderHook(() => useMyScores(), { wrapper });
    await waitFor(() => expect(result.current.scores.size).toBe(2));
    expect(qc.getQueryData(["matches"])).toBeTruthy();
    await qc.invalidateQueries({ queryKey: ["matches"] });
    await waitFor(() => expect(GET).toHaveBeenCalledTimes(2));
  });

  it("asks for the route's own page size", async () => {
    const { result } = renderHook(() => useMyScores(), { wrapper });
    await waitFor(() => expect(result.current.scores.size).toBe(2));
    expect(GET.mock.calls[0][1]).toEqual({ params: { query: { limit: MATCHES_FETCH } } });
    expect(MATCHES_FETCH).toBe(50);
  });

  it("asks nothing, and has nothing, for a visitor", async () => {
    world.signedIn = false;
    world.memberships = [];
    const { result } = renderHook(() => useMyScores(), { wrapper });
    expect(result.current.isSeeker).toBe(false);
    expect(result.current.scores.size).toBe(0);
    expect(GET).not.toHaveBeenCalled();
  });

  it("has no scores, and no thrown error, when the request is refused", async () => {
    GET.mockResolvedValue({ error: {}, response: { status: 403 } });
    const { result } = renderHook(() => useMyScores(), { wrapper });
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(result.current.scores.size).toBe(0);
  });
});
