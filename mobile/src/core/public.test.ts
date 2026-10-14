import { createApi } from "./api";
import { ApiError } from "./errors";
import {
  PAGE_SIZE,
  getCourse,
  getJob,
  getSkill,
  listCourses,
  listJobs,
  listSkills,
  nextOffset,
  searchRoles,
  searchSkills,
  skillCourses,
  skillJobs,
} from "./public";
import { createTokenStore, type SecretBackend } from "./token-store";

const nothing: SecretBackend = {
  read: async () => null,
  write: async () => undefined,
  remove: async () => undefined,
};

type Seen = { path: string; query: URLSearchParams; headers: Headers };

function harness(answer: (seen: Seen) => Response) {
  const calls: Seen[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    const url = new URL(request.url);
    const seen = { path: url.pathname, query: url.searchParams, headers: request.headers };
    calls.push(seen);
    return answer(seen);
  }) as typeof fetch;
  const api = createApi({
    baseUrl: "https://api.test",
    tokens: createTokenStore(nothing),
    locale: () => "hi",
    appVersion: "1.0.0",
    platform: "android",
    onUpgradeRequired: () => undefined,
    fetch: fetcher,
  });
  return { api, calls };
}

const page = { items: [], total: 0, limit: PAGE_SIZE, offset: 0 };
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("listing vacancies", () => {
  it("asks for one page of twenty and says which language it wants", async () => {
    const { api, calls } = harness(() => json(200, page));
    await listJobs(api, {});
    expect(calls[0].path).toBe("/jobs");
    expect(calls[0].query.get("limit")).toBe("20");
    expect(calls[0].query.get("offset")).toBe("0");
    expect(calls[0].headers.get("accept-language")).toBe("hi");
  });

  it("sends the filters it was given and nothing it was not", async () => {
    const { api, calls } = harness(() => json(200, page));
    await listJobs(api, { q: "  nurse  ", employmentType: "gig", state: "Kerala", skill: "x" }, 40);
    const q = calls[0].query;
    expect([q.get("q"), q.get("employment_type"), q.get("location_state"), q.get("skill"), q.get("offset")]).toEqual(["nurse", "gig", "Kerala", "x", "40"]);

    await listJobs(api, { q: "   ", employmentType: "", state: "" });
    expect([...calls[1].query.keys()].sort()).toEqual(["limit", "offset"]);
  });
});

describe("listing courses and standards", () => {
  it("filters courses by mode and language", async () => {
    const { api, calls } = harness(() => json(200, page));
    await listCourses(api, { q: "welding", mode: "offline", language: "hi" });
    const q = calls[0].query;
    expect([q.get("q"), q.get("mode"), q.get("language")]).toEqual(["welding", "offline", "hi"]);
  });

  it("filters standards by type, and a search is capped and not paged", async () => {
    const { api, calls } = harness(() => json(200, page));
    await listSkills(api, "core", 20);
    expect(calls[0].query.get("skill_type")).toBe("core");
    expect(calls[0].query.get("offset")).toBe("20");

    const hits = harness(() => json(200, []));
    await searchSkills(hits.api, " triage ");
    expect(hits.calls[0].path).toBe("/skills/search");
    expect(hits.calls[0].query.get("q")).toBe("triage");
    expect(hits.calls[0].query.get("limit")).toBe("50");
    expect(hits.calls[0].query.get("offset")).toBeNull();
  });

  it("searches roles with a small cap", async () => {
    const { api, calls } = harness(() => json(200, []));
    await searchRoles(api, "ward boy");
    expect(calls[0].path).toBe("/roles/search");
    expect(calls[0].query.get("limit")).toBe("5");
  });
});

describe("details and what is related", () => {
  it("fetches each by its slug", async () => {
    const { api, calls } = harness(() => json(200, { slug: "x" }));
    await getJob(api, "ward-assistant");
    await getCourse(api, "welding-basics");
    await getSkill(api, "hand-hygiene");
    await skillJobs(api, "hand-hygiene");
    await skillCourses(api, "hand-hygiene", 3);
    expect(calls.map((c) => c.path)).toEqual([
      "/jobs/ward-assistant",
      "/courses/welding-basics",
      "/skills/hand-hygiene",
      "/skills/hand-hygiene/jobs",
      "/skills/hand-hygiene/courses",
    ]);
    expect(calls[3].query.get("limit")).toBe("5");
    expect(calls[4].query.get("limit")).toBe("3");
  });
});

describe("a failure keeps what the server said", () => {
  it("a missing vacancy stays a 404, so a screen can say not found", async () => {
    const { api } = harness(() => json(404, { detail: "Job not found" }));
    const error = await getJob(api, "nope").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).detail).toBe("Job not found");
  });

  it("an outage stays a 5xx, which is not 'not found'", async () => {
    const { api } = harness(() => json(503, { detail: "Database unavailable" }));
    const error = await listJobs(api, {}).catch((e: unknown) => e);
    expect((error as ApiError).status).toBe(503);
  });

  it("an empty failure body still fails", async () => {
    const { api } = harness(() => new Response(null, { status: 500 }));
    const error = await listCourses(api, {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });
});

describe("paging", () => {
  it("offers the next offset until the last page, then none", () => {
    expect(nextOffset({ offset: 0, limit: 20, total: 45 })).toBe(20);
    expect(nextOffset({ offset: 20, limit: 20, total: 45 })).toBe(40);
    expect(nextOffset({ offset: 40, limit: 20, total: 45 })).toBeUndefined();
    expect(nextOffset({ offset: 0, limit: 20, total: 20 })).toBeUndefined();
    expect(nextOffset({ offset: 0, limit: 20, total: 0 })).toBeUndefined();
  });
});
