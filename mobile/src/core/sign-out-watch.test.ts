import { QueryClient } from "@tanstack/react-query";

import { meKeys } from "./me-keys";
import { createSignOutWatch, forgetEverything } from "./sign-out-watch";
import { createTokenStore, type SecretBackend } from "./token-store";

const backendWith = (seed: Record<string, string> = {}): SecretBackend => {
  const data = new Map(Object.entries(seed));
  return {
    read: async (key) => data.get(key) ?? null,
    write: async (key, value) => void data.set(key, value),
    remove: async (key) => void data.delete(key),
  };
};

describe("when the stored cache is wiped", () => {
  it("not when a signed-out phone starts: that is not a sign-out", () => {
    let wipes = 0;
    const watch = createSignOutWatch(() => (wipes += 1));
    watch(false);
    watch(false);
    expect(wipes).toBe(0);
  });

  it("when a session that was there ends, once", () => {
    let wipes = 0;
    const watch = createSignOutWatch(() => (wipes += 1));
    watch(true);
    watch(false);
    watch(false);
    expect(wipes).toBe(1);
  });

  it("again for a second session", () => {
    let wipes = 0;
    const watch = createSignOutWatch(() => (wipes += 1));
    [true, false, true, false].forEach(watch);
    expect(wipes).toBe(2);
  });

  it("with the real token store: launch signed out wipes nothing, signing out does", async () => {
    let wipes = 0;
    const store = createTokenStore(backendWith());
    store.subscribe(createSignOutWatch(() => (wipes += 1)));
    await store.load(); // the first load tells every subscriber "signed out"
    expect(wipes).toBe(0);
    await store.set({ access_token: "a", refresh_token: "r" });
    await store.clear();
    expect(wipes).toBe(1);
  });

  it("with the real token store: a restored session that is later ended wipes once", async () => {
    let wipes = 0;
    const store = createTokenStore(backendWith({ "iism.access_token": "a", "iism.refresh_token": "r" }));
    store.subscribe(createSignOutWatch(() => (wipes += 1)));
    await store.load();
    expect(wipes).toBe(0);
    await store.clear();
    expect(wipes).toBe(1);
  });
});


describe("what signing out forgets", () => {
  const client = () => new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });

  it("every query about the person, so the next person to sign in is shown nothing of theirs", () => {
    const qc = client();
    qc.setQueryData(meKeys.profile, { full_name: "Asha" });
    qc.setQueryData(meKeys.matches, { items: [] });
    qc.setQueryData(meKeys.applications, [{ id: "a1", status_message: "Interview at 10" }]);
    qc.setQueryData(meKeys.interests, []);
    qc.setQueryData(meKeys.match("ward-assistant-1"), { score: 80 });
    qc.setQueryData(meKeys.account, { memberships: [] });
    forgetEverything(qc, () => undefined);
    for (const key of [meKeys.profile, meKeys.matches, meKeys.applications, meKeys.interests, meKeys.match("ward-assistant-1"), meKeys.account]) {
      expect(qc.getQueryData(key)).toBeUndefined();
    }
    expect(qc.getQueryCache().getAll()).toHaveLength(0);
  });

  it("and the stored public cache too", () => {
    let forgotten = 0;
    forgetEverything(client(), () => void (forgotten += 1));
    expect(forgotten).toBe(1);
  });

  it("wired to the real token store: signing out forgets, a signed-out launch does not", async () => {
    const qc = client();
    qc.setQueryData(meKeys.profile, { full_name: "Asha" });
    const store = createTokenStore(backendWith());
    let forgotten = 0;
    const unsubscribe = store.subscribe(
      createSignOutWatch(() => forgetEverything(qc, () => void (forgotten += 1))),
    );
    await store.load();
    expect(forgotten).toBe(0);
    await store.set({ access_token: "a", refresh_token: "r" });
    await store.clear();
    expect(forgotten).toBe(1);
    expect(qc.getQueryData(meKeys.profile)).toBeUndefined();
    unsubscribe();
  });
});
