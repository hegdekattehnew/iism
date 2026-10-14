/**
 * The two seams every screen test controls: the router and the runtime (the API, the session, the
 * language). A `jest.mock` factory runs when a screen is first imported, before the test file's
 * own `const`s exist, so each test file says
 *
 *     jest.mock("../runtime", () => require("./mocks").runtimeModule);
 *     jest.mock("expo-router", () => require("./mocks").routerModule);
 *
 * and these objects look everything up lazily.
 */

export const world = {
  signedIn: false,
  locale: "en" as "en" | "hi",
  params: {} as Record<string, string | undefined>,
};

export const api = { GET: jest.fn(), POST: jest.fn() };
export const router = {
  push: jest.fn(),
  replace: jest.fn(),
  navigate: jest.fn(),
  setParams: jest.fn(),
};
export const setLocale = jest.fn();
export const tokens = { refresh: () => "r", access: () => null, clear: jest.fn(async () => undefined) };

export function resetWorld() {
  world.signedIn = false;
  world.locale = "en";
  world.params = {};
  api.GET.mockReset();
  api.POST.mockReset();
  for (const fn of Object.values(router)) fn.mockReset();
  setLocale.mockReset();
  tokens.clear.mockClear();
}

export const runtimeModule = {
  api: {
    GET: (...args: unknown[]) => api.GET(...args),
    POST: (...args: unknown[]) => api.POST(...args),
  },
  tokens,
  useLocale: () => world.locale,
  setLocale: (...args: unknown[]) => setLocale(...args),
  useSignedIn: () => world.signedIn,
  useUpgradeRequired: () => null,
};

export const routerModule = {
  useRouter: () => router,
  useLocalSearchParams: () => world.params,
  Stack: { Screen: () => null },
  Tabs: { Screen: () => null },
};

// ---- answers the API gives, built the way the real responses are shaped ----

export const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200, headers: new Headers() } });
export const failed = (status: number, detail?: string) => ({
  data: undefined,
  error: detail ? { detail } : {},
  response: { status, headers: new Headers() },
});
export const page = <T,>(items: T[], total = items.length, offset = 0) => ({ items, total, limit: 20, offset });

export const tenant = { id: "t1", slug: "apollo", name: "Apollo Care", tenant_type: "employer", is_verified: true };

export const job = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `j${n}`,
  slug: `ward-assistant-${n}`,
  title: `Ward assistant ${n}`,
  description: "Looks after patients on the ward.",
  location_state: "Maharashtra",
  location_district: "Pune",
  employment_type: "full_time",
  experience_min_years: 1,
  experience_max_years: 3,
  salary_min_inr: 240000,
  salary_max_inr: 360000,
  nsqf_level_min: 4,
  tenant,
  is_open: true,
  positions: 1,
  ...extra,
});

export const course = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `c${n}`,
  slug: `phlebotomy-${n}`,
  title: `Phlebotomy ${n}`,
  mode: "offline",
  language: "hi",
  duration_hours: 120,
  fee_inr: 12500,
  nsqf_level: 4,
  location_state: "Maharashtra",
  location_district: "Pune",
  starts_on: "2026-11-02",
  started: false,
  tenant: { ...tenant, name: "Pune Skills Academy", tenant_type: "course_provider" },
  ...extra,
});

export const skill = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `s${n}`,
  slug: `hand-hygiene-${n}`,
  name: `Hand hygiene ${n}`,
  skill_type: "technical",
  nsqf_level: 4,
  qp_count: 2,
  nos_code: `HSS/N${n}`,
  context: { qualification_name: "General Duty Assistant", sector: "Healthcare" },
  ...extra,
});
