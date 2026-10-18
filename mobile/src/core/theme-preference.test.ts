import { THEME_STORAGE_KEY, createThemeStore, parsePreference } from "./theme-preference";

function fakeStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: async (k: string) => data.get(k) ?? null,
    setItem: async (k: string, v: string) => void data.set(k, v),
    removeItem: async (k: string) => void data.delete(k),
  };
}

describe("parsePreference", () => {
  it("only light and dark are choices", () => {
    expect(parsePreference("light")).toBe("light");
    expect(parsePreference("dark")).toBe("dark");
    for (const odd of [null, undefined, "", "system", "Dark", "auto", 1, {}]) expect(parsePreference(odd)).toBe("system");
  });
});

describe("the theme store", () => {
  it("starts on the phone's own setting", () => {
    expect(createThemeStore(fakeStorage()).get()).toBe("system");
  });

  it("remembers a choice and tells subscribers", () => {
    const storage = fakeStorage();
    const store = createThemeStore(storage);
    const seen: string[] = [];
    store.subscribe(() => seen.push(store.get()));
    store.set("dark");
    expect(store.get()).toBe("dark");
    expect(storage.data.get(THEME_STORAGE_KEY)).toBe("dark");
    expect(seen).toEqual(["dark"]);
  });

  it("choosing the phone's own setting forgets the choice on disk", () => {
    const storage = fakeStorage({ [THEME_STORAGE_KEY]: "dark" });
    const store = createThemeStore(storage);
    store.set("system");
    expect(storage.data.has(THEME_STORAGE_KEY)).toBe(false);
  });

  it("an unknown value cannot be set", () => {
    const store = createThemeStore(fakeStorage());
    store.set("purple" as never);
    expect(store.get()).toBe("system");
  });

  it("is read back at the next launch, and an unreadable value is the phone's own", async () => {
    const store = createThemeStore(fakeStorage({ [THEME_STORAGE_KEY]: "light" }));
    await store.restore();
    expect(store.get()).toBe("light");
    const odd = createThemeStore(fakeStorage({ [THEME_STORAGE_KEY]: "neon" }));
    await odd.restore();
    expect(odd.get()).toBe("system");
    const broken = createThemeStore({
      getItem: async () => {
        throw new Error("unreadable");
      },
      setItem: async () => undefined,
      removeItem: async () => undefined,
    });
    broken.set("dark");
    await broken.restore();
    expect(broken.get()).toBe("system");
  });

  it("is forgotten, in memory and on disk, when the session ends, so a shared phone starts on its own setting", async () => {
    const storage = fakeStorage();
    const store = createThemeStore(storage);
    store.set("dark");
    await store.clear();
    expect(store.get()).toBe("system");
    expect(storage.data.has(THEME_STORAGE_KEY)).toBe(false);
  });

  it("still applies for this visit when storage refuses to write", async () => {
    const store = createThemeStore({
      getItem: async () => null,
      setItem: async () => {
        throw new Error("full");
      },
      removeItem: async () => undefined,
    });
    store.set("dark");
    await Promise.resolve();
    expect(store.get()).toBe("dark");
  });

  it("a store made without storage keeps to the one attached later", async () => {
    const store = createThemeStore();
    const storage = fakeStorage();
    store.set("light"); // in memory only
    expect(storage.data.size).toBe(0);
    store.attach(storage);
    store.set("dark");
    expect(storage.data.get(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("stops telling a subscriber that left", () => {
    const store = createThemeStore(fakeStorage());
    let calls = 0;
    const off = store.subscribe(() => calls++);
    store.set("dark");
    off();
    store.set("light");
    expect(calls).toBe(1);
  });
});
