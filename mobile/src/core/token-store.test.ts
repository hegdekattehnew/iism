import { ACCESS_KEY, REFRESH_KEY, createTokenStore, type SecretBackend } from "./token-store";

function memoryBackend(seed: Record<string, string> = {}, fail = false) {
  const data = new Map(Object.entries(seed));
  const backend: SecretBackend = {
    async read(key) {
      if (fail) throw new Error("keystore locked");
      return data.get(key) ?? null;
    },
    async write(key, value) {
      if (fail) throw new Error("keystore locked");
      data.set(key, value);
    },
    async remove(key) {
      if (fail) throw new Error("keystore locked");
      data.delete(key);
    },
  };
  return { backend, data };
}

const TOKENS = { access_token: "a1", refresh_token: "r1" };

describe("the token store", () => {
  it("is signed out when nothing is stored", async () => {
    const store = createTokenStore(memoryBackend().backend);
    expect(await store.load()).toBeNull();
    expect(store.access()).toBeNull();
    expect(store.refresh()).toBeNull();
  });

  it("restores a stored session into memory", async () => {
    const { backend } = memoryBackend({ [ACCESS_KEY]: "a", [REFRESH_KEY]: "r" });
    const store = createTokenStore(backend);
    expect(await store.load()).toEqual({ access_token: "a", refresh_token: "r" });
    expect(store.access()).toBe("a");
  });

  it("needs both halves: an access token alone is not a session", async () => {
    const store = createTokenStore(memoryBackend({ [ACCESS_KEY]: "a" }).backend);
    expect(await store.load()).toBeNull();
  });

  it("writes through to the backend and answers from memory", async () => {
    const { backend, data } = memoryBackend();
    const store = createTokenStore(backend);
    await store.set(TOKENS);
    expect(store.access()).toBe("a1");
    expect(data.get(REFRESH_KEY)).toBe("r1");
  });

  it("clears both memory and the backend", async () => {
    const { backend, data } = memoryBackend();
    const store = createTokenStore(backend);
    await store.set(TOKENS);
    await store.clear();
    expect(store.access()).toBeNull();
    expect(data.size).toBe(0);
  });

  it("treats a locked keystore on launch as signed out, not a crash", async () => {
    const store = createTokenStore(memoryBackend({}, true).backend);
    expect(await store.load()).toBeNull();
  });

  it("keeps the session for this run when the write fails", async () => {
    const store = createTokenStore(memoryBackend({}, true).backend);
    await store.set(TOKENS);
    expect(store.access()).toBe("a1");
  });

  it("signs out of memory even when the delete fails", async () => {
    const store = createTokenStore(memoryBackend({}, true).backend);
    await store.set(TOKENS);
    await store.clear();
    expect(store.access()).toBeNull();
  });

  it("tells subscribers when the session starts and ends, and stops when they leave", async () => {
    const store = createTokenStore(memoryBackend().backend);
    const seen: boolean[] = [];
    const leave = store.subscribe((signedIn) => seen.push(signedIn));
    await store.set(TOKENS);
    await store.clear();
    leave();
    await store.set(TOKENS);
    expect(seen).toEqual([true, false]);
  });
});
