import {
  CACHE_STORAGE_KEY,
  MAX_AGE_MS,
  dehydrateOptions,
  isPublicKey,
  wipePersistedCache,
} from "./persist";

const withData = (queryKey: unknown[]) => ({ queryKey, state: { data: { items: [] } as unknown } });
const withoutData = (queryKey: unknown[]) => ({ queryKey, state: { data: undefined as unknown } });

describe("what the phone remembers", () => {
  it("keeps only queries keyed as public", () => {
    expect(dehydrateOptions.shouldDehydrateQuery(withData(["public", "jobs", { q: "nurse" }]))).toBe(true);
    expect(dehydrateOptions.shouldDehydrateQuery(withData(["public", "course", "x"]))).toBe(true);
  });

  it("refuses everything about a person, by default and not by a list of names", () => {
    for (const key of [["me"], ["profile"], ["matches"], ["applications"], ["notifications"], ["org", "x"], [], ["publicish"]]) {
      expect(dehydrateOptions.shouldDehydrateQuery(withData(key))).toBe(false);
    }
  });

  it("keeps what has data, and nothing that never had any", () => {
    expect(dehydrateOptions.shouldDehydrateQuery(withoutData(["public", "jobs"]))).toBe(false);
    expect(dehydrateOptions.shouldDehydrateQuery(withData(["public", "jobs"]))).toBe(true);
  });

  it("never keeps a mutation: its variables are what somebody typed", () => {
    expect(dehydrateOptions.shouldDehydrateMutation()).toBe(false);
  });

  it("forgets after a day", () => {
    expect(MAX_AGE_MS).toBe(24 * 60 * 60 * 1000);
  });

  it("recognises the public prefix and nothing that merely looks like it", () => {
    expect(isPublicKey(["public"])).toBe(true);
    expect(isPublicKey(["Public"])).toBe(false);
    expect(isPublicKey([["public"]])).toBe(false);
  });
});

describe("signing out", () => {
  it("removes the persisted cache", async () => {
    const removed: string[] = [];
    await wipePersistedCache({ removeItem: async (k) => void removed.push(k) });
    expect(removed).toEqual([CACHE_STORAGE_KEY]);
  });

  it("is not stopped by a storage that cannot be cleared", async () => {
    await expect(
      wipePersistedCache({ removeItem: async () => Promise.reject(new Error("disk full")) }),
    ).resolves.toBeUndefined();
  });
});
