import { createSignOutWatch } from "./sign-out-watch";
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
