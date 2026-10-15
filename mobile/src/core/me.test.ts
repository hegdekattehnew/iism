import { createApi } from "./api";
import { ApiError } from "./errors";
import {
  MATCH_LIMIT,
  addSkillsBulk,
  applyTo,
  getMatch,
  getProfile,
  listApplications,
  listInterests,
  listMatches,
  listSaved,
  registerInterest,
  removeSkill,
  roleStandards,
  saveJob,
  searchRoleHits,
  unsaveJob,
  updateProfile,
  withdrawApplication,
  withdrawInterest,
} from "./me";
import { createTokenStore, type SecretBackend } from "./token-store";

const nothing: SecretBackend = {
  read: async () => null,
  write: async () => undefined,
  remove: async () => undefined,
};

type Seen = { method: string; path: string; query: URLSearchParams; body: unknown; headers: Headers };

function harness(answer: (seen: Seen) => Response) {
  const calls: Seen[] = [];
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input as RequestInfo, init);
    const url = new URL(request.url);
    const text = await request.clone().text();
    const seen: Seen = {
      method: request.method,
      path: url.pathname,
      query: url.searchParams,
      body: text ? JSON.parse(text) : undefined,
      headers: request.headers,
    };
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

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const empty204 = () => new Response(null, { status: 204 });

describe("the profile and its skills", () => {
  it("reads and updates the profile", async () => {
    const { api, calls } = harness(() => json(200, { id: "p" }));
    await getProfile(api);
    await updateProfile(api, { headline: "Ward boy", years_experience: 2 });
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(["GET /me/profile", "PUT /me/profile"]);
    expect(calls[1].body).toEqual({ headline: "Ward boy", years_experience: 2 });
  });

  it("adds skills in one request and removes one by slug", async () => {
    const { api, calls } = harness(() => json(200, { id: "p" }));
    await addSkillsBulk(api, { items: [{ skill_slug: "a", proficiency: 3 }], preferred_role_title: "Ward boy" });
    await removeSkill(api, "a");
    expect(calls[0].path).toBe("/me/profile/skills/bulk");
    expect(calls[0].body).toEqual({ items: [{ skill_slug: "a", proficiency: 3 }], preferred_role_title: "Ward boy" });
    expect(`${calls[1].method} ${calls[1].path}`).toBe("DELETE /me/profile/skills/a");
  });

  it("keeps the server's own sentence when a bulk add is refused", async () => {
    const { api } = harness(() => json(422, { detail: "A profile may hold at most 60 standards." }));
    await expect(addSkillsBulk(api, { items: [{ skill_slug: "a", proficiency: 3 }], preferred_role_title: null })).rejects.toMatchObject({
      status: 422,
      detail: "A profile may hold at most 60 standards.",
    });
  });

  it("searches roles and reads a role's standards", async () => {
    const { api, calls } = harness(() => json(200, []));
    await searchRoleHits(api, "  ward boy ");
    await roleStandards(api, "general-duty-assistant");
    expect(calls[0].query.get("q")).toBe("ward boy");
    expect(calls[0].query.get("limit")).toBe("8");
    expect(calls[1].path).toBe("/roles/general-duty-assistant/standards");
  });
});

describe("matches", () => {
  it("asks for the best fifty, in the language the app is showing", async () => {
    const { api, calls } = harness(() => json(200, { items: [], total: 0, has_skills: false }));
    await listMatches(api);
    expect(calls[0].query.get("limit")).toBe(String(MATCH_LIMIT));
    expect(calls[0].headers.get("accept-language")).toBe("hi");
  });

  it("reads one match by the vacancy's slug", async () => {
    const { api, calls } = harness(() => json(200, { score: 80 }));
    await getMatch(api, "ward-assistant-1");
    expect(calls[0].path).toBe("/me/matches/ward-assistant-1");
  });

  it("says 401 when signed out, and keeps it a 401", async () => {
    const { api } = harness(() => json(401, { detail: "Not authenticated" }));
    await expect(listMatches(api)).rejects.toMatchObject({ status: 401 });
  });
});

describe("applying", () => {
  it("sends the vacancy and the note, trimmed, and null for a blank note", async () => {
    const { api, calls } = harness(() => json(201, { id: "a1" }));
    await applyTo(api, "ward-assistant-1", "  I have two years on a ward.  ");
    await applyTo(api, "ward-assistant-1", "   ");
    expect(calls[0].body).toEqual({ job_slug: "ward-assistant-1", message: "I have two years on a ward." });
    expect(calls[1].body).toEqual({ job_slug: "ward-assistant-1", message: null });
  });

  it("keeps the status of a refusal, so the screen can say duplicate, cap or not-a-seeker", async () => {
    for (const status of [409, 429, 403]) {
      const { api } = harness(() => json(status, { detail: "no" }));
      await expect(applyTo(api, "x", "")).rejects.toBeInstanceOf(ApiError);
      await expect(applyTo(api, "x", "")).rejects.toMatchObject({ status });
    }
  });

  it("withdraws by application id", async () => {
    const { api, calls } = harness(() => json(200, { id: "a1", status: "withdrawn" }));
    await withdrawApplication(api, "a1");
    expect(`${calls[0].method} ${calls[0].path}`).toBe("POST /me/applications/a1/withdraw");
  });

  it("lists the applications", async () => {
    const { api, calls } = harness(() => json(200, []));
    await listApplications(api);
    expect(calls[0].path).toBe("/me/applications");
  });
});

describe("saving a vacancy", () => {
  it("saves, lists and unsaves, and a 204 is success", async () => {
    const { api, calls } = harness((seen) =>
      seen.method === "DELETE" ? empty204() : json(seen.method === "POST" ? 201 : 200, seen.method === "POST" ? { job: {}, saved_at: "x" } : []),
    );
    await saveJob(api, "ward-assistant-1");
    await listSaved(api);
    await unsaveJob(api, "ward-assistant-1");
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      "POST /me/saved-jobs",
      "GET /me/saved-jobs",
      "DELETE /me/saved-jobs/ward-assistant-1",
    ]);
    expect(calls[0].body).toEqual({ job_slug: "ward-assistant-1" });
  });

  it("does not call a refused unsave a success", async () => {
    const { api } = harness(() => json(500, { detail: "boom" }));
    await expect(unsaveJob(api, "x")).rejects.toMatchObject({ status: 500 });
  });
});

describe("registering interest in a course", () => {
  it("sends the course and the note, trimmed, and null for a blank one", async () => {
    const { api, calls } = harness(() => json(201, { id: "i1" }));
    await registerInterest(api, "phlebotomy-1", " evenings only ");
    await registerInterest(api, "phlebotomy-1", "");
    expect(calls[0].body).toEqual({ course_slug: "phlebotomy-1", message: "evenings only" });
    expect(calls[1].body).toEqual({ course_slug: "phlebotomy-1", message: null });
  });

  it("withdraws and lists", async () => {
    const { api, calls } = harness(() => json(200, []));
    await withdrawInterest(api, "i1");
    await listInterests(api);
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      "POST /me/course-interests/i1/withdraw",
      "GET /me/course-interests",
    ]);
  });
});
