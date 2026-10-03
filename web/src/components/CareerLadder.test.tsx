import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CareerLadder } from "@/components/CareerLadder";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

const ANCHOR = {
  slug: "ward-assistant",
  qp_code: "HSS/Q0101",
  job_role: "Ward Assistant",
  nsqf_level: 3,
  sector_name: "Healthcare",
};

const STEP = {
  role: {
    slug: "senior-ward-assistant",
    qp_code: "HSS/Q0201",
    job_role: "Senior Ward Assistant",
    nsqf_level: 4,
    sector_name: "Healthcare",
  },
  basis: { shared_standards: 2, compulsory_count: 5, same_occupation: true, shared_nco: false },
  variants: 1,
  score: 38,
  coverage: 0.4,
  missing: [
    {
      skill_id: "s1",
      nos_code: "HSS/N5127",
      name: "Dress minor wounds",
      importance: 3,
      is_mandatory: true,
      nsqf_level: 4,
    },
  ],
  missing_mandatory: 1,
  level_shortfall: null,
  experience_shortfall: null,
  courses: [
    {
      slug: "wound-care",
      title: "Wound Care",
      mode: "offline",
      duration_hours: 40,
      fee_inr: null,
      closes: ["HSS/N5127"],
      closes_count: 1,
      gap_size: 1,
      covers_mandatory: 1,
    },
  ],
  entry: {
    qp_code: "HSS/Q0201",
    qp_name: "Senior Ward Assistant",
    routes_total: 2,
    education_options: ["Diploma", "Grade 12"],
    lowest_experience_years: 1.5,
  },
};

const LADDER = {
  anchor: ANCHOR,
  anchor_source: "chosen",
  needs_choice: false,
  has_skills: true,
  steps: [STEP],
};

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("CareerLadder", () => {
  it("shows the starting role and each step with the reason it was offered", async () => {
    GET.mockResolvedValue(ok(LADDER));
    renderUi(<CareerLadder />);

    expect(await screen.findByText("Senior Ward Assistant")).toBeTruthy();
    expect(screen.getByText("Ward Assistant")).toBeTruthy();
    expect(
      screen.getByText("Shares 2 of 5 required standards with Ward Assistant."),
    ).toBeTruthy();
    expect(screen.getByText("Same occupation")).toBeTruthy();
    expect(screen.queryByText("Shared national occupation code")).toBeNull();
    // With skills listed the fit is shown -- the contrast the no-skills test needs.
    expect(screen.getByText(/of what this role requires/i)).toBeTruthy();
  });

  it("opens what it would take: the gap, the courses and the way in", async () => {
    GET.mockResolvedValue(ok(LADDER));
    renderUi(<CareerLadder />);
    fireEvent.click(await screen.findByRole("button", { name: "What it would take" }));

    expect(screen.getByText("Dress minor wounds")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Wound Care" }).getAttribute("href")).toBe(
      "/courses/wound-care",
    );
    expect(screen.getByText("Education accepted: Diploma, Grade 12")).toBeTruthy();
    expect(screen.getByText("From 1.5 years of experience")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByText("Dress minor wounds")).toBeNull();
  });

  it("says plainly that a guessed starting role is a guess", async () => {
    GET.mockResolvedValue(ok({ ...LADDER, anchor_source: "guessed" }));
    renderUi(<CareerLadder />);
    expect(
      await screen.findByText("We picked this from your profile. If it is not your role, change it."),
    ).toBeTruthy();
  });

  it("does not say it for a role the person chose", async () => {
    GET.mockResolvedValue(ok(LADDER));
    renderUi(<CareerLadder />);
    await screen.findByText("Senior Ward Assistant");
    expect(screen.queryByText(/We picked this from your profile/)).toBeNull();
  });

  it("asks which role when the server could not be sure, and shows no ladder", async () => {
    GET.mockResolvedValue(
      ok({ anchor: null, anchor_source: "none", needs_choice: true, has_skills: true, steps: [] }),
    );
    renderUi(<CareerLadder />);

    expect(
      await screen.findByText(
        "Tell us the role you do now and we will show the roles that build on it.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Starting from")).toBeNull();
    // The "no further step" sentence is about a role; with no role it would be false.
    expect(screen.queryByText(/no further step/)).toBeNull();
    expect(screen.queryByText(/Built from the national qualification framework/)).toBeNull();
  });

  it("starts the ladder again from the role the person picks", async () => {
    GET.mockImplementation(async (path: string, init?: { params?: { query?: { role?: string } } }) => {
      if (path === "/roles/search") {
        return ok([
          {
            slug: "electrician-helper",
            qp_code: "ELE/Q1",
            job_role: "Electrician Helper",
            nsqf_level: 3,
            sector_name: "Electronics",
            standards_count: 4,
            variants: 1,
            matched_on: "Electrician Helper",
            match_kind: "exact",
          },
        ]);
      }
      return init?.params?.query?.role
        ? ok({ ...LADDER, anchor: { ...ANCHOR, job_role: "Electrician Helper" } })
        : ok({ anchor: null, anchor_source: "none", needs_choice: true, has_skills: true, steps: [] });
    });
    renderUi(<CareerLadder />);

    fireEvent.change(await screen.findByLabelText("Your role"), {
      target: { value: "electrician" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /Electrician Helper/ }));

    await waitFor(() => expect(screen.getByText("Starting from")).toBeTruthy());
    const careerCalls = GET.mock.calls.filter((c) => c[0] === "/me/careers");
    expect(careerCalls.at(-1)?.[1].params.query).toEqual({ role: "electrician-helper" });
  });

  it("says it found no further step, and that this may be the data, rather than showing nothing", async () => {
    GET.mockResolvedValue(ok({ ...LADDER, steps: [] }));
    renderUi(<CareerLadder />);
    expect(
      await screen.findByText(
        "We found no further step from this role in the national qualification data. That can mean there is none, or that the data does not link them. Try a different role.",
      ),
    ).toBeTruthy();
  });

  it("tells somebody with no skills why every step shows no fit, and links to add them", async () => {
    GET.mockResolvedValue(ok({ ...LADDER, has_skills: false }));
    renderUi(<CareerLadder />);

    expect(
      await screen.findByText("Add the skills you already have to see how close each role is."),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Add my skills" }).getAttribute("href")).toBe(
      "/profile",
    );
    // A 0% bar for somebody who simply has not listed anything is a false verdict.
    expect(screen.queryByText(/of what this role requires/i)).toBeNull();
  });

  it("says an expired session is expired", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderUi(<CareerLadder />);
    expect(
      await screen.findByText("Your session has expired. Sign in again to continue."),
    ).toBeTruthy();
  });

  it("shows what the server said when it refuses, and a fixed line only when it said nothing", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Role not found" },
      response: { status: 404 },
    });
    renderUi(<CareerLadder />);
    expect(await screen.findByText("Role not found")).toBeTruthy();
  });
});
