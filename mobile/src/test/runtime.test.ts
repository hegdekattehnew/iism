import { BUDGET_STORAGE_KEY } from "../core/course-budget";
import { CACHE_STORAGE_KEY } from "../core/persist";
import { THEME_STORAGE_KEY } from "../core/theme-preference";
import { unregisterThisDevice } from "../push";
import {
  api,
  courseBudget,
  endSession,
  forgetPersistedCache,
  getLocale,
  restoreCourseBudget,
  restoreLocale,
  restoreThemePreference,
  setCourseBudget,
  setLocale,
  setThemePreference,
  tokens,
} from "../runtime";
import { storage } from "../storage";
import { themePreference } from "../theme/preference";

// A store in memory, and the two native modules the runtime would otherwise load.
jest.mock("../storage", () => {
  const data = new Map<string, string>();
  return {
    LOCALE_KEY: "iism.locale",
    storage: {
      data,
      failing: false,
      getItem: async (key: string) => {
        if ((jest.requireMock("../storage") as { storage: { failing: boolean } }).storage.failing) {
          throw new Error("unreadable");
        }
        return data.get(key) ?? null;
      },
      setItem: async (key: string, value: string) => void data.set(key, value),
      removeItem: async (key: string) => void data.delete(key),
    },
  };
});
jest.mock("../auth/secure-backend", () => ({
  secureBackend: { read: async () => null, write: async () => undefined, remove: async () => undefined },
}));
jest.mock("../push", () => ({ unregisterThisDevice: jest.fn(async () => undefined) }));
jest.mock("../config", () => ({ API_BASE_URL: "http://api.test", APP_VERSION: "1.0.0", PLATFORM: "android" }));

type Fake = { data: Map<string, string>; failing: boolean };
const fake = () => storage as unknown as Fake;

beforeEach(() => {
  fake().data.clear();
  fake().failing = false;
});

describe("the language the person chose", () => {
  it("follows the phone's own language the first time, and does not write it down", async () => {
    await restoreLocale(["hi-IN", "en-IN"]);
    expect(getLocale()).toBe("hi");
    expect(fake().data.has("iism.locale")).toBe(false);
  });

  it("falls back to English for a phone in a language the app does not offer", async () => {
    await restoreLocale(["fr-FR"]);
    expect(getLocale()).toBe("en");
  });

  it("remembers a choice across a restart, over the phone's language", async () => {
    setLocale("hi");
    await Promise.resolve();
    expect(fake().data.get("iism.locale")).toBe("hi");

    // A restart: the module state is gone, the store is not.
    await restoreLocale(["en-IN"]);
    expect(getLocale()).toBe("hi");
  });

  it("ignores a stored value the app does not offer", async () => {
    fake().data.set("iism.locale", "ms");
    await restoreLocale(["hi-IN"]);
    expect(getLocale()).toBe("hi");
    fake().data.set("iism.locale", "klingon");
    await restoreLocale(["en-GB"]);
    expect(getLocale()).toBe("en");
  });

  it("treats a store that cannot be read as nothing saved, not a crash at launch", async () => {
    fake().failing = true;
    await expect(restoreLocale(["hi-IN"])).resolves.toBeUndefined();
    expect(getLocale()).toBe("hi");
  });
});

describe("signing out", () => {
  it("removes the stored public cache and leaves the language alone", async () => {
    fake().data.set(CACHE_STORAGE_KEY, '{"clientState":{}}');
    fake().data.set("iism.locale", "hi");
    await forgetPersistedCache();
    expect(fake().data.has(CACHE_STORAGE_KEY)).toBe(false);
    expect(fake().data.get("iism.locale")).toBe("hi");
  });
});

describe("what the person would pay for a course", () => {
  it("is remembered across a launch", async () => {
    setCourseBudget(6000);
    expect(fake().data.get(BUDGET_STORAGE_KEY)).toBe("6000");
    courseBudget.set(null);
    fake().data.set(BUDGET_STORAGE_KEY, "6000");
    await restoreCourseBudget();
    expect(courseBudget.get()).toBe(6000);
  });

  it("is forgotten, in memory and on disk, when the session ends, so a shared phone starts empty", async () => {
    setCourseBudget(6000);
    await forgetPersistedCache();
    expect(courseBudget.get()).toBeNull();
    expect(fake().data.has(BUDGET_STORAGE_KEY)).toBe(false);
  });
});

describe("light, dark or follow the phone (BL-19.8)", () => {
  it("is remembered across a launch", async () => {
    setThemePreference("dark");
    expect(fake().data.get(THEME_STORAGE_KEY)).toBe("dark");
    themePreference.set("light");
    fake().data.set(THEME_STORAGE_KEY, "dark");
    await restoreThemePreference();
    expect(themePreference.get()).toBe("dark");
  });

  it("is forgotten, in memory and on disk, when the session ends, so a shared phone starts on the default", async () => {
    setThemePreference("dark");
    expect(themePreference.get()).toBe("dark");
    await forgetPersistedCache();
    expect(themePreference.get()).toBe("light");
    expect(fake().data.has(THEME_STORAGE_KEY)).toBe(false);
  });

  it("does not forget the language when the session ends", async () => {
    fake().data.set("iism.locale", "hi");
    setThemePreference("dark");
    await forgetPersistedCache();
    expect(fake().data.get("iism.locale")).toBe("hi");
  });
});

describe("ending the session", () => {
  afterEach(() => jest.restoreAllMocks());

  it("takes this phone off the push list while the session still exists, then ends it", async () => {
    jest.spyOn(api, "POST").mockResolvedValue({ data: undefined, error: undefined, response: new Response(null, { status: 204 }) } as never);
    await tokens.set({ access_token: "a", refresh_token: "r" });
    const seen: (string | null)[] = [];
    (unregisterThisDevice as jest.Mock).mockImplementationOnce(async () => {
      seen.push(tokens.access());
    });
    await endSession();
    // The server only lets a person remove their own phone, so it has to be done signed in.
    expect(seen).toEqual(["a"]);
    expect(tokens.access()).toBeNull();
  });

  it("ends the session even when the phone could not be taken off the list", async () => {
    jest.spyOn(api, "POST").mockResolvedValue({ data: undefined, error: undefined, response: new Response(null, { status: 204 }) } as never);
    await tokens.set({ access_token: "a", refresh_token: "r" });
    (unregisterThisDevice as jest.Mock).mockRejectedValueOnce(new Error("offline"));
    await endSession();
    expect(tokens.access()).toBeNull();
  });
});
