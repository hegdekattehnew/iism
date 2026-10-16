import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MatchBrowser } from "@/components/MatchBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() } }));

const skill = (name: string, mandatory = true, importance = 3) => ({
  name,
  nos_code: `T/${name.length}`,
  importance,
  is_mandatory: mandatory,
  evidence: "self_declared",
  proficiency: 3,
});

const match = (n: number, extra: Record<string, unknown> = {}) => ({
  job: {
    slug: `job-${n}`,
    title: `Ward attendant ${n}`,
    location_state: "Maharashtra",
    location_district: "Pune",
    nsqf_level_min: 3,
  },
  score: 90 - n,
  coverage: 0.8,
  matched: [skill("Wash hands"), skill("Make a bed"), skill("Take a pulse"), skill("Lift a patient")],
  missing: [{ ...skill("Control infection"), skill_id: "s1" }],
  missing_mandatory: 1,
  level_shortfall: null,
  experience_shortfall: null,
  capped_by_mandatory: false,
  locality: 0,
  ...extra,
});

function serve(items: unknown[], total = items.length) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/me/matches") return { data: { items, total, has_skills: true } };
    if (path === "/me/matches/{slug}") return { data: { courses: [], entry: null } };
    return { data: undefined };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 70, UI-13: a match answers "why this score, and what do I do", before it reports. */
describe("a match card", () => {
  it("says what the person has and lacks, in a sentence, before any list", async () => {
    serve([match(1)]);
    renderUi(<MatchBrowser />);
    expect(
      await screen.findByText("You have 4 of 5 skills this job asks for. Missing: Control infection."),
    ).toBeTruthy();
  });

  it("says so when nothing is missing, and offers the job rather than courses", async () => {
    serve([match(1, { missing: [], missing_mandatory: 0 })]);
    renderUi(<MatchBrowser />);
    expect(await screen.findByText("You have every skill this job asks for.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "See courses that close this" })).toBeNull();
    const link = screen.getByRole("link", { name: "View the job" });
    expect(link.getAttribute("href")).toBe("/jobs/job-1");
  });

  it("names the first two missing skills, required first, and counts the rest", async () => {
    serve([
      match(1, {
        matched: [skill("Wash hands")],
        missing: [
          { ...skill("Greet visitors", false, 5), skill_id: "a" },
          { ...skill("Manage waste", true, 2), skill_id: "b" },
          { ...skill("Record vitals", true, 4), skill_id: "c" },
          { ...skill("Fill forms", false, 1), skill_id: "d" },
        ],
      }),
    ]);
    renderUi(<MatchBrowser />);
    expect(
      await screen.findByText(
        "You have 1 of 5 skills this job asks for. Missing: Record vitals, Manage waste and 2 more.",
      ),
    ).toBeTruthy();
  });

  it("has one primary action when there is a gap: the courses that close it", async () => {
    serve([match(1)]);
    renderUi(<MatchBrowser />);
    const action = await screen.findByRole("button", { name: "See courses that close this" });
    expect(action.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(action);
    expect(GET.mock.calls.some((c) => c[0] === "/me/matches/{slug}")).toBe(true);
    expect(
      (await screen.findByRole("button", { name: "All matches" })).getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("keeps the report behind Details, closed", async () => {
    serve([match(1)]);
    const { container } = renderUi(<MatchBrowser />);
    await screen.findByText(/You have 4 of 5/);
    const details = container.querySelector("details")!;
    expect(details.open).toBe(false);
    expect(within(details).getByText("Details")).toBeTruthy();
    // The lists, the level scale and the codes are in there, not above it.
    expect(within(details).getByText("You have")).toBeTruthy();
    expect(within(details).getByText("You need")).toBeTruthy();
    expect(within(details).getByText("T/17")).toBeTruthy();
  });

  it("does not repeat the lists outside Details", async () => {
    serve([match(1)]);
    const { container } = renderUi(<MatchBrowser />);
    await screen.findByText(/You have 4 of 5/);
    const li = container.querySelector("li")!;
    const outside = [...li.children].filter((c) => c.tagName !== "DETAILS");
    for (const part of outside) expect(part.textContent).not.toMatch(/You need|T\/\d+/);
  });
});

describe("the list of matches", () => {
  const eight = Array.from({ length: 8 }, (_, i) => match(i + 1));

  it("asks for the best fifty, the route's most", async () => {
    serve(eight);
    renderUi(<MatchBrowser />);
    await screen.findByText("Ward attendant 1");
    const call = GET.mock.calls.find((c) => c[0] === "/me/matches")!;
    expect(call[1].params.query.limit).toBe(50);
  });

  it("shows five, then offers the rest and says how many are left", async () => {
    serve(eight);
    renderUi(<MatchBrowser />);
    await screen.findByText("Ward attendant 1");
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(5);
    fireEvent.click(screen.getByRole("button", { name: "Show more (3 left)" }));
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(8);
    expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();
  });

  it("has no button when there are five or fewer", async () => {
    serve(eight.slice(0, 3));
    renderUi(<MatchBrowser />);
    await screen.findByText("Ward attendant 1");
    expect(screen.queryByRole("button", { name: /Show more/ })).toBeNull();
  });

  it("says it is the best of a larger number when the server has more than it sent", async () => {
    serve(eight, 137);
    renderUi(<MatchBrowser />);
    expect(await screen.findByText("These are your best 8 of 137 matches.")).toBeTruthy();
  });

  it("does not say that when it sent them all", async () => {
    serve(eight, 8);
    renderUi(<MatchBrowser />);
    await screen.findByText("Ward attendant 1");
    expect(screen.queryByText(/your best/)).toBeNull();
  });
});
