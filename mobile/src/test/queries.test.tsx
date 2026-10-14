import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";

import { isPublicKey } from "../core/persist";
import {
  useCourse,
  useCourses,
  useJob,
  useJobs,
  useSearch,
  useSkill,
  useSkillCourses,
  useSkillJobs,
  useSkills,
} from "../lib/queries";
import { api, ok, page, resetWorld, world } from "./mocks";

jest.mock("../runtime", () => require("./mocks").runtimeModule);

beforeEach(() => resetWorld());

/** Every query a visitor's screen makes, run once, so the keys they were stored under can be read. */
async function keysAfterRunning(locale: "en" | "hi") {
  world.locale = locale;
  const arrays = new Set(["/skills/search", "/roles/search", "/skills/{slug}/jobs", "/skills/{slug}/courses"]);
  const lists = new Set(["/jobs", "/courses", "/skills"]);
  api.GET.mockImplementation(async (path: string) =>
    arrays.has(path) ? ok([]) : lists.has(path) ? ok(page([])) : ok({ slug: "x" }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const all = await renderHook(
    () => ({
      jobs: useJobs({ q: "a" }),
      courses: useCourses({ q: "a" }),
      skills: useSkills({ q: "" }),
      searched: useSkills({ q: "blood" }),
      job: useJob("j"),
      course: useCourse("c"),
      skill: useSkill("s"),
      skillJobs: useSkillJobs("s"),
      skillCourses: useSkillCourses("s"),
      search: useSearch("nurse"),
    }),
    { wrapper },
  );
  await waitFor(() => expect(client.isFetching()).toBe(0));
  all.unmount();
  return client.getQueryCache().getAll().map((q) => q.queryKey);
}

describe("every query a visitor's screen makes", () => {
  it("is public, so it may be kept for offline reading, and is keyed by language", async () => {
    const keys = await keysAfterRunning("hi");
    expect(keys.length).toBeGreaterThanOrEqual(11);
    for (const key of keys) {
      expect(isPublicKey(key)).toBe(true);
      expect(key[1]).toBe("hi");
    }
  });

  it("is a different entry in English, so a Hindi list is never served as English", async () => {
    const english = await keysAfterRunning("en");
    expect(english.every((key) => key[1] === "en")).toBe(true);
  });

  it("includes what the list was filtered by, so two filters are two entries", async () => {
    const keys = (await keysAfterRunning("en")).map((k) => JSON.stringify(k));
    expect(keys.some((k) => k.includes('"jobs"') && k.includes('"q":"a"'))).toBe(true);
    expect(keys.some((k) => k.includes('"skills"') && k.includes('"q":"blood"'))).toBe(true);
  });
});
