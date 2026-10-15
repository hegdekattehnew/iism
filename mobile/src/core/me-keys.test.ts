import { ME_KEY, isMeKey, meKeys } from "./me-keys";
import { dehydrateOptions, isPublicKey } from "./persist";

const everyKey = (): (readonly unknown[])[] => [
  meKeys.all,
  meKeys.account,
  meKeys.profile,
  meKeys.matches,
  meKeys.match("ward-assistant"),
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
