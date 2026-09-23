/**
 * The homepage counts are invalidated by the things that change them.
 *
 * The reported symptom was "I added a job and the number on the homepage did
 * not move". The count itself was right -- it is computed live -- but nothing
 * in the workspace told the cache, so a client-side navigation back to the
 * front page painted the figure fetched before the publish.
 *
 * Asserted per mutation rather than once, because the miss is always a single
 * forgotten call site: `close` and `reopen` change the count exactly as much
 * as `create` does, since `open_job()` excludes a closed vacancy, and nothing
 * about either of those reads like a catalogue write.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CORPUS_STATS, MARKETPLACE_COUNTS } from "@/lib/counts";
import { useOrgCourseMutations, useOrgJobMutations } from "@/lib/org";

const ok = { data: { slug: "a-vacancy" }, error: null, response: { status: 200 } };

vi.mock("@/lib/api", () => ({
  api: {
    GET: vi.fn(async () => ok),
    POST: vi.fn(async () => ok),
    PUT: vi.fn(async () => ok),
    DELETE: vi.fn(async () => ({ data: null, error: null, response: { status: 204 } })),
  },
}));

let qc: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // A cached answer is the precondition: with nothing cached the next mount
  // fetches anyway and the bug cannot occur.
  qc.setQueryData(MARKETPLACE_COUNTS, { jobs: 19, courses: 50 });
  qc.setQueryData(CORPUS_STATS, { jobs: 19, courses: 50 });
});

const stale = (key: readonly unknown[]) =>
  qc.getQueryState(key)?.isInvalidated === true;

describe("a vacancy that changes the catalogue", () => {
  const run = async (act_: (m: ReturnType<typeof useOrgJobMutations>) => Promise<unknown>) => {
    const { result } = renderHook(() => useOrgJobMutations("acme"), { wrapper });
    await act(async () => {
      await act_(result.current);
    });
  };

  it("marks the counts stale when one is created", async () => {
    expect(stale(MARKETPLACE_COUNTS)).toBe(false);
    await run((m) => m.create.mutateAsync({ title: "A vacancy" } as never));
    expect(stale(MARKETPLACE_COUNTS)).toBe(true);
    expect(stale(CORPUS_STATS)).toBe(true);
  });

  it("marks the counts stale when one is published", async () => {
    await run((m) => m.setPublished.mutateAsync({ slug: "a", published: true }));
    expect(stale(MARKETPLACE_COUNTS)).toBe(true);
  });

  it("marks the counts stale when one is closed", async () => {
    // `open_job()` excludes it from the moment it closes, so the public
    // number drops -- the case least likely to be remembered.
    await run((m) => m.setOpen.mutateAsync({ slug: "a", open: false, reason: "filled" }));
    expect(stale(MARKETPLACE_COUNTS)).toBe(true);
  });

  it("marks the counts stale when one is deleted", async () => {
    await run((m) => m.remove.mutateAsync("a"));
    expect(stale(MARKETPLACE_COUNTS)).toBe(true);
  });
});

describe("a course that changes the catalogue", () => {
  it("marks the counts stale when one is created", async () => {
    const { result } = renderHook(() => useOrgCourseMutations("acme"), { wrapper });
    await act(async () => {
      await result.current.create.mutateAsync({ title: "A course" } as never);
    });
    expect(stale(MARKETPLACE_COUNTS)).toBe(true);
    expect(stale(CORPUS_STATS)).toBe(true);
  });
});
