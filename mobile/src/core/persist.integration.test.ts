import { MutationObserver, QueryClient, dehydrate, hydrate } from "@tanstack/react-query";

import { dehydrateOptions } from "./persist";

/**
 * The rule, run through the real library: what `dehydrate` would write to the phone's storage.
 * (`persist.test.ts` holds the predicates; this proves they are what the library actually asks.)
 */
describe("what would be written to the phone", () => {
  const client = () => new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });

  it("contains the public queries and nothing about a person", async () => {
    const qc = client();
    qc.setQueryData(["public", "en", "jobs", { q: "nurse" }], { pages: [{ items: ["a"] }], pageParams: [0] });
    qc.setQueryData(["public", "hi", "course", "phlebotomy"], { title: "x" });
    qc.setQueryData(["me"], { id: "u1", phone: "+919810000001" });
    qc.setQueryData(["profile"], { headline: "private" });
    qc.setQueryData(["matches"], [{ score: 90 }]);

    const saved = dehydrate(qc, dehydrateOptions);
    const keys = saved.queries.map((q) => q.queryKey[0]);
    expect(keys).toEqual(["public", "public"]);
    expect(JSON.stringify(saved)).not.toContain("919810000001");
    expect(JSON.stringify(saved)).not.toContain("private");
  });

  it("never contains a mutation, whose variables are what somebody typed", async () => {
    const qc = client();
    const observer = new MutationObserver(qc, {
      mutationKey: ["sign-in"],
      mutationFn: async (_credentials: { phone: string; code: string }) => "ok",
    });
    await observer.mutate({ phone: "9810000001", code: "123456" });
    expect(qc.getMutationCache().getAll().length).toBe(1);
    const saved = dehydrate(qc, dehydrateOptions);
    expect(saved.mutations).toEqual([]);
    expect(JSON.stringify(saved)).not.toContain("123456");
  });

  it("does not keep a query that never had data", async () => {
    const qc = client();
    await qc.prefetchQuery({
      queryKey: ["public", "en", "jobs"],
      queryFn: async () => Promise.reject(new Error("503")),
      retry: false,
    });
    expect(dehydrate(qc, dehydrateOptions).queries).toEqual([]);
  });

  it("keeps a query whose refresh failed, because its data is what an offline reader came for", async () => {
    const qc = client();
    const key = ["public", "en", "jobs"];
    await qc.fetchQuery({ queryKey: key, queryFn: async () => ({ items: ["still here"] }) });
    await qc
      .fetchQuery({ queryKey: key, queryFn: async () => Promise.reject(new Error("offline")), staleTime: 0, retry: false })
      .catch(() => undefined);
    expect(qc.getQueryState(key)?.status).toBe("error");
    const saved = dehydrate(qc, dehydrateOptions);
    expect(saved.queries).toHaveLength(1);
    expect(JSON.stringify(saved)).toContain("still here");
  });

  it("restores what it kept, for reading offline", () => {
    const source = client();
    source.setQueryData(["public", "en", "job", "ward"], { title: "Ward assistant" });
    const saved = JSON.parse(JSON.stringify(dehydrate(source, dehydrateOptions)));

    const restored = client();
    hydrate(restored, saved);
    expect(restored.getQueryData(["public", "en", "job", "ward"])).toEqual({ title: "Ward assistant" });
  });

  it("keeps each language apart, because the key carries it", () => {
    const qc = client();
    qc.setQueryData(["public", "en", "jobs", {}], "english");
    qc.setQueryData(["public", "hi", "jobs", {}], "hindi");
    expect(qc.getQueryData(["public", "en", "jobs", {}])).toBe("english");
    expect(qc.getQueryData(["public", "hi", "jobs", {}])).toBe("hindi");
  });
});
