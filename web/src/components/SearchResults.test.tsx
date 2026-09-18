import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SearchResults } from "@/components/SearchResults";
import { lookalikeNames } from "@/components/SkillBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

/**
 * The homepage search used to answer "General Duty Assistant" with 24
 * technical units -- two identically named, told apart only by opening them --
 * and no vacancy. These guard both halves of the fix.
 */

const JOB = {
  slug: "gda-chennai",
  title: "General Duty Assistant",
  location_state: "Tamil Nadu",
  location_district: "Chennai",
  employment_type: "full_time",
  experience_min_years: 0,
  experience_max_years: 2,
  salary_min_inr: 168000,
  salary_max_inr: 216000,
  tenant: { name: "Apollo Care Hospitals" },
};

const ROLE = {
  slug: "cii-hss-q5101",
  job_role: "General Duty Assistant",
  qp_code: "CII/HSS/Q5101",
  nsqf_level: 3,
  sector_name: "Healthcare",
  standards_count: 9,
  variants: 2,
  matched_on: "General Duty Assistant",
  match_kind: "exact",
};

const twin = (code: string, qp: string, level: number) => ({
  slug: code.toLowerCase(),
  name: "Broad Functions of General Duty Assistant",
  skill_type: "technical",
  nsqf_level: level,
  nos_code: code,
  context: {
    awarding_body: "Medhavi Foundation",
    sector: "Healthcare",
    qualification_code: qp,
    qualification_name: "Certificate in General Duty Assistance",
  },
});

function answer({
  jobs = [JOB],
  jobsTotal,
  roles = [ROLE],
  standards = [twin("MSU/HSS/CRS0005-001", "MSU/HSS/CRS0005", 4), twin("MSU/HSS/CRS0021-001", "MSU/HSS/CRS0021", 4.5)],
}: { jobs?: unknown[]; jobsTotal?: number; roles?: unknown[]; standards?: unknown[] } = {}) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/jobs")
      return { data: { items: jobs, total: jobsTotal ?? jobs.length, limit: 5, offset: 0 } };
    if (path === "/roles/search") return { data: roles };
    if (path === "/skills/search") return { data: standards };
    return { data: undefined };
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  answer();
});

describe("SearchResults", () => {
  it("answers a job title with jobs first, then roles, then standards", async () => {
    const { container } = renderUi(<SearchResults query="General Duty Assistant" />);
    await screen.findByText("Apollo Care Hospitals · Chennai, Tamil Nadu");
    const text = container.textContent ?? "";
    const at = (s: string) => text.indexOf(s);
    expect(at("Open jobs")).toBeGreaterThanOrEqual(0);
    expect(at("Open jobs")).toBeLessThan(at("Job roles"));
    expect(at("Job roles")).toBeLessThan(at("Skill standards"));
  });

  it("tells two same-named standards apart without opening either", async () => {
    renderUi(<SearchResults query="General Duty Assistant" />);
    expect(await screen.findByText("MSU/HSS/CRS0005-001")).toBeTruthy();
    expect(screen.getByText("MSU/HSS/CRS0021-001")).toBeTruthy();
    expect(screen.getByText("(MSU/HSS/CRS0005)")).toBeTruthy();
    expect(screen.getByText("(MSU/HSS/CRS0021)")).toBeTruthy();
    // And says outright that the sameness is real, and where to look.
    expect(
      screen.getAllByText("Same name as another result — compare the codes"),
    ).toHaveLength(2);
  });

  it("links to every job when there are more than it previews, keeping the query", async () => {
    answer({ jobsTotal: 12 });
    renderUi(<SearchResults query="ward attendant" />);
    const link = await screen.findByRole("link", { name: /See all 12 jobs/ });
    expect(link.getAttribute("href")).toBe("/jobs?q=ward%20attendant");
  });

  it("says a band is empty rather than leaving a heading over nothing", async () => {
    answer({ jobs: [], roles: [], standards: [] });
    renderUi(<SearchResults query="astronaut" />);
    expect(await screen.findByText("No open vacancy matches this yet.")).toBeTruthy();
    expect(screen.getByText("No job role by that name.")).toBeTruthy();
    expect(screen.getByText("No standard matches this.")).toBeTruthy();
  });

  it("asks for a query instead of searching for nothing", () => {
    renderUi(<SearchResults query="  " />);
    expect(screen.getByText("Type a job title or a skill above.")).toBeTruthy();
    expect(GET).not.toHaveBeenCalled();
  });
});

describe("lookalikeNames", () => {
  it("matches as a reader would, ignoring case and stray spaces", () => {
    const found = lookalikeNames([
      { name: "Bed Making" },
      { name: " bed making" },
      { name: "Hand hygiene" },
    ]);
    expect([...found]).toEqual(["bed making"]);
  });
});

describe("StandardOrigin", () => {
  it("does not repeat a council named after its own sector", async () => {
    answer({
      standards: [
        {
          slug: "hss-n5113",
          name: "Clean medical equipment",
          skill_type: "technical",
          nsqf_level: 4.5,
          nos_code: "HSS/N5113",
          context: { awarding_body: "Healthcare", sector: "Healthcare" },
        },
      ],
    });
    renderUi(<SearchResults query="clean" />);
    expect(await screen.findByText("Healthcare")).toBeTruthy();
    expect(screen.queryByText("Healthcare · Healthcare")).toBeNull();
    // Level is one of the few things that tells twins apart.
    expect(screen.getByText("Level 4.5")).toBeTruthy();
  });
});
