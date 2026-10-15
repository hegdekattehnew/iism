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

export const api = { GET: jest.fn(), POST: jest.fn(), PUT: jest.fn(), DELETE: jest.fn() };
export const router = {
  push: jest.fn(),
  replace: jest.fn(),
  navigate: jest.fn(),
  setParams: jest.fn(),
};
export const setLocale = jest.fn();
export const endSession = jest.fn(async () => undefined);
export const tokens = { refresh: () => "r", access: () => null, clear: jest.fn(async () => undefined) };

export function resetWorld() {
  world.signedIn = false;
  world.locale = "en";
  world.params = {};
  api.GET.mockReset();
  api.POST.mockReset();
  api.PUT.mockReset();
  api.DELETE.mockReset();
  for (const fn of Object.values(router)) fn.mockReset();
  setLocale.mockReset();
  endSession.mockClear();
  tokens.clear.mockClear();
  push.permission = "undetermined";
  push.declined = false;
  push.ask.mockClear();
  push.decline.mockClear();
  push.register.mockClear();
  push.taps.mockReset();
  push.registration.mockReset();
}

export const runtimeModule = {
  api: {
    GET: (...args: unknown[]) => api.GET(...args),
    POST: (...args: unknown[]) => api.POST(...args),
    PUT: (...args: unknown[]) => api.PUT(...args),
    DELETE: (...args: unknown[]) => api.DELETE(...args),
  },
  tokens,
  useLocale: () => world.locale,
  setLocale: (...args: unknown[]) => setLocale(...args),
  endSession: () => endSession(),
  useSignedIn: () => world.signedIn,
  useUpgradeRequired: () => null,
};

/** What `src/push.ts` would say, so a screen test needs no operating system. */
export const push = {
  permission: "undetermined" as "undetermined" | "granted" | "denied",
  declined: false,
  ask: jest.fn(async (..._args: unknown[]) => undefined),
  decline: jest.fn(),
  register: jest.fn(async (..._args: unknown[]) => undefined),
  taps: jest.fn((_go: (path: string) => void) => () => undefined),
  registration: jest.fn((..._args: unknown[]) => undefined),
};

export const pushModule = {
  usePushPermission: () => ({
    permission: push.permission,
    declined: push.declined,
    ask: (...args: unknown[]) => push.ask(...args),
    decline: () => push.decline(),
  }),
  registerThisDevice: (...args: unknown[]) => push.register(...args),
  unregisterThisDevice: async () => undefined,
  listenForTaps: (go: (path: string) => void) => push.taps(go),
  showForegroundNotifications: () => undefined,
  usePushRegistration: (...args: unknown[]) => push.registration(...args),
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

// ---- the signed-in person's side ----

type Answer = unknown | ((init: unknown) => unknown);

/**
 * Answer by route: `serve(api.GET, { "/me/matches": ok(...) })`. A route nobody listed answers 404,
 * so a screen that asks for something the test did not expect fails loudly instead of hanging.
 */
export function serve(method: jest.Mock, table: Record<string, Answer>) {
  method.mockImplementation(async (path: string, init: unknown) => {
    const answer = table[path];
    if (answer === undefined) return failed(404);
    return typeof answer === "function" ? (answer as (i: unknown) => unknown)(init) : answer;
  });
}

const personal = { tenant: { id: "t0", slug: "me", name: "Personal workspace", tenant_type: "personal" }, role: "owner" };
const organisation = { tenant: { id: "t1", slug: "apollo", name: "Apollo Care", tenant_type: "employer" }, role: "owner" };

/** What `/auth/me` says: a job seeker, or an organisation owner who signed in on a phone. */
export const account = (kind: "seeker" | "organisation" = "seeker") => ({
  id: "u1",
  memberships: [kind === "seeker" ? personal : organisation],
});

const skillRef = (name: string, mandatory: boolean, importance: number) => ({
  nos_code: `HSS/${name.length}`,
  name,
  importance,
  is_mandatory: mandatory,
});

export const matchItem = (n: number, extra: Record<string, unknown> = {}) => ({
  job: {
    slug: `ward-assistant-${n}`,
    title: `Ward assistant ${n}`,
    location_state: "Maharashtra",
    location_district: "Pune",
    employment_type: "full_time",
    nsqf_level_min: 4,
  },
  score: 80 - n,
  coverage: 0.75,
  matched: [{ ...skillRef("Hand hygiene", false, 3), evidence: "self_declared", proficiency: 3 }],
  missing: [
    { ...skillRef("Bed making", false, 2), skill_id: "s2" },
    { ...skillRef("Infection control", true, 5), skill_id: "s3" },
  ],
  missing_mandatory: 1,
  level_shortfall: null,
  experience_shortfall: null,
  capped_by_mandatory: false,
  locality: 0,
  ...extra,
});

export const suggestion = (n: number, extra: Record<string, unknown> = {}) => ({
  slug: `phlebotomy-${n}`,
  title: `Phlebotomy ${n}`,
  mode: "offline",
  language: "hi",
  duration_hours: 120,
  fee_inr: 12500,
  closes: ["Infection control"],
  closes_count: 1,
  gap_size: 2,
  covers_mandatory: 1,
  location_state: "Maharashtra",
  location_district: "Pune",
  starts_on: "2026-11-02",
  seats_left: 5,
  reach: "district",
  started: false,
  full: false,
  within_budget: null,
  attendable: true,
  ...extra,
});

export const application = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `a${n}`,
  job: {
    slug: `ward-assistant-${n}`,
    title: `Ward assistant ${n}`,
    location_state: "Maharashtra",
    location_district: "Pune",
    employment_type: "full_time",
    tenant,
    removed: false,
  },
  status: "applied",
  message: null,
  status_message: null,
  status_message_at: null,
  applied_at: "2026-10-14T20:00:00+00:00",
  updated_at: "2026-10-14T20:00:00+00:00",
  reviewed: false,
  ...extra,
});

export const interest = (n: number, extra: Record<string, unknown> = {}) => ({
  id: `i${n}`,
  course: { slug: `phlebotomy-${n}`, title: `Phlebotomy ${n}`, tenant: { ...tenant, name: "Pune Skills Academy" } },
  status: "registered",
  message: null,
  registered_at: "2026-10-14T20:00:00+00:00",
  updated_at: "2026-10-14T20:00:00+00:00",
  ...extra,
});

export const profile = (extra: Record<string, unknown> = {}) => ({
  id: "p1",
  full_name: "Asha Rao",
  headline: "Ward boy",
  location_state: "Maharashtra",
  location_district: "Pune",
  years_experience: 3,
  education_level: "secondary",
  skills: [],
  completeness: { percent: 60, missing: ["skills"] },
  ...extra,
});

export const roleHit = (n: number, extra: Record<string, unknown> = {}) => ({
  slug: `general-duty-assistant-${n}`,
  job_role: `General Duty Assistant ${n}`,
  qp_code: `HSS/Q5101-${n}`,
  nsqf_level: 4,
  sector_name: "Healthcare",
  standards_count: 4,
  variants: 1,
  matched_on: "ward boy",
  match_kind: "alias",
  ...extra,
});

export const roleStandard = (slug: string, requirement: string, group_name: string | null = null) => ({
  id: slug,
  slug,
  name: `Standard ${slug}`,
  skill_type: "technical",
  nsqf_level: 4,
  qp_count: 1,
  nos_code: `HSS/${slug}`,
  requirement,
  group_name,
});
