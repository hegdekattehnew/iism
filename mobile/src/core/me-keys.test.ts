import { ME_KEY, isMeKey, meKeys } from "./me-keys";
import { dehydrateOptions, isPublicKey } from "./persist";

const everyKey = (): (readonly unknown[])[] => [
  meKeys.all,
  meKeys.account,
  meKeys.profile,
  meKeys.matches,
  meKeys.match("ward-assistant"),
  meKeys.match("ward-assistant", 5000),
  meKeys.gap("app-1"),
  meKeys.gap("app-1", 0),
  meKeys.careers(null),
  meKeys.careers("general-duty-assistant", 8000),
  meKeys.applications,
  meKeys.saved,
  meKeys.interests,
  meKeys.notices,
  meKeys.unread,
  meKeys.messages,
  meKeys.deletion,
  meKeys.roles("ward boy"),
  meKeys.roleStandards("general-duty-assistant"),
];

describe("the keys of everything about a person", () => {
  it("found keys to check", () => {
    expect(everyKey().length).toBeGreaterThan(5);
  });

  it("all start with the one word signing out removes", () => {
    for (const key of everyKey()) {
      expect(key[0]).toBe(ME_KEY);
      expect(isMeKey(key)).toBe(true);
    }
  });

  it("are never public, and so never reach the disk", () => {
    for (const key of everyKey()) {
      expect(isPublicKey(key)).toBe(false);
      expect(dehydrateOptions.shouldDehydrateQuery({ queryKey: [...key], state: { data: { items: [] } as unknown } })).toBe(false);
    }
  });

  it("do not mistake a public key for a personal one", () => {
    expect(isMeKey(["public", "en", "jobs", {}])).toBe(false);
    expect(isMeKey([])).toBe(false);
  });
});

describe("a match asked with a budget", () => {
  const { QueryClient } = jest.requireActual("@tanstack/react-query") as typeof import("@tanstack/react-query");

  it("is reached by the prefix for its vacancy, whatever the budget, and by no other vacancy's", () => {
    // `gcTime: Infinity`: the default garbage-collection timer would keep Jest from exiting.
    const qc = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
    for (const key of [meKeys.match("a"), meKeys.match("a", 5000), meKeys.match("a", 0), meKeys.match("b", 5000)]) {
      qc.setQueryData(key, {});
    }
    void qc.invalidateQueries({ queryKey: meKeys.matchesOf("a") });
    const stale = (key: readonly unknown[]) => qc.getQueryState(key)?.isInvalidated === true;
    expect(stale(meKeys.match("a"))).toBe(true);
    expect(stale(meKeys.match("a", 5000))).toBe(true);
    expect(stale(meKeys.match("a", 0))).toBe(true);
    expect(stale(meKeys.match("b", 5000))).toBe(false);
    qc.clear();
  });
});
