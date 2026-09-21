import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RolePicker } from "@/components/profile/RolePicker";
import { SkillsSection } from "@/components/profile/SkillsSection";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * The path that decides whether a new candidate gets any matches at all: name
 * a job, tick the standards behind it. Every case here is a way the screen
 * could claim something on the candidate's behalf, or lose what they chose.
 */

const GDA = {
  slug: "cii-hss-q5101",
  job_role: "General Duty Assistant",
  qp_code: "CII/HSS/Q5101",
  nsqf_level: 3,
  sector_name: "Healthcare",
  standards_count: 4,
  variants: 2,
  matched_on: "ward boy",
  match_kind: "alias",
};

const std = (slug: string, requirement: string, group_name: string | null = null) => ({
  id: slug,
  slug,
  name: `Standard ${slug}`,
  nos_code: `HSS/${slug.toUpperCase()}`,
  skill_type: "technical",
  qp_count: 1,
  requirement,
  group_name,
  weightage: null,
});

const STANDARDS = {
  slug: GDA.slug,
  job_role: GDA.job_role,
  qp_code: GDA.qp_code,
  qp_name: "General Duty Assistant",
  nsqf_level: 3,
  sector_name: "Healthcare",
  variants: 2,
  standards: [
    std("n1", "compulsory"),
    std("n2", "compulsory"),
    std("n3", "elective", "Elective 1: Critical Care"),
    std("n4", "optional"),
  ],
};

function routeGets(roles: unknown[] = [GDA]) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/roles/search") return { data: roles, error: undefined };
    if (path === "/roles/{slug}/standards") return { data: STANDARDS, error: undefined };
    if (path === "/skills/search") return { data: [], error: undefined };
    return { data: undefined, error: { status: 404 } };
  });
}

async function pickGda() {
  fireEvent.change(screen.getByLabelText("What work do you do?"), {
    target: { value: "ward boy" },
  });
  fireEvent.click(await screen.findByRole("button", { name: /General Duty Assistant/ }));
  await screen.findByText("Standard n1");
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  POST.mockResolvedValue({ data: { skills: [] }, error: undefined, response: { status: 200 } });
  routeGets();
});

describe("RolePicker — finding the role", () => {
  it("shows the code, the level and how many standards, and why it matched", async () => {
    renderUi(<RolePicker held={new Set()} />);
    fireEvent.change(screen.getByLabelText("What work do you do?"), {
      target: { value: "ward boy" },
    });
    const row = await screen.findByRole("button", { name: /General Duty Assistant/ });
    expect(row.textContent).toContain("CII/HSS/Q5101");
    expect(row.textContent).toContain("NSQF 3");
    expect(row.textContent).toContain("4 standards");
    // Otherwise "General Duty Assistant" for "ward boy" looks like a mistake.
    expect(row.textContent).toContain("Matched “ward boy”");
    expect(row.textContent).toContain("2 versions of this qualification");
  });

  it("says so when no role matches, and points at the fallback", async () => {
    routeGets([]);
    renderUi(<RolePicker held={new Set()} />);
    fireEvent.change(screen.getByLabelText("What work do you do?"), {
      target: { value: "astronaut" },
    });
    expect(await screen.findByText(/No job by that name yet/)).toBeTruthy();
  });
});

describe("RolePicker — the standards", () => {
  it("starts with nothing ticked, so nothing is claimed on anyone's behalf", async () => {
    renderUi(<RolePicker held={new Set()} />);
    await pickGda();
    const boxes = screen.getAllByRole("checkbox").filter((b) =>
      (b.closest("label")?.textContent ?? "").startsWith("Standard"),
    );
    expect(boxes).toHaveLength(4);
    expect(boxes.every((b) => !(b as HTMLInputElement).checked)).toBe(true);
    expect(screen.getByRole("button", { name: "Tick at least one" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("keeps an elective under its group, never among the core standards", async () => {
    renderUi(<RolePicker held={new Set()} />);
    await pickGda();
    const elective = screen.getByText("Choose from: Elective 1: Critical Care");
    const group = elective.closest("fieldset")!;
    expect(group.textContent).toContain("Standard n3");
    expect(group.textContent).not.toContain("Standard n1");
    const core = screen.getByText("Core to the job").closest("fieldset")!;
    expect(core.textContent).not.toContain("Standard n3");
  });

  it("shows a standard already held as held, and does not offer it again", async () => {
    renderUi(<RolePicker held={new Set(["n2"])} />);
    await pickGda();
    const label = screen.getByText("Standard n2").closest("label")!;
    const box = label.querySelector("input") as HTMLInputElement;
    expect(box.checked).toBe(true);
    expect(box.disabled).toBe(true);
    expect(label.textContent).toContain("Already on your profile");
  });

  it("adds everything ticked in one request, with the role as a preferred role", async () => {
    renderUi(<RolePicker held={new Set()} />);
    await pickGda();
    fireEvent.click(screen.getByLabelText(/Standard n1/));
    fireEvent.click(screen.getByLabelText(/Standard n3/));
    fireEvent.click(screen.getByRole("button", { name: "Add 2 skills" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/me/profile/skills/bulk");
    expect(init.body).toEqual({
      items: [
        { skill_slug: "n1", proficiency: 3 },
        { skill_slug: "n3", proficiency: 3 },
      ],
      preferred_role_title: "General Duty Assistant",
    });
    expect(await screen.findByText(/2 skills added/)).toBeTruthy();
  });

  it("records no preferred role when the candidate unticks that box", async () => {
    renderUi(<RolePicker held={new Set()} />);
    await pickGda();
    fireEvent.click(screen.getByLabelText("Also save this as a job I'm looking for"));
    fireEvent.click(screen.getByLabelText(/Standard n1/));
    fireEvent.click(screen.getByRole("button", { name: "Add 1 skill" }));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    const init = POST.mock.calls[0][1] as { body: { preferred_role_title: unknown } };
    expect(init.body.preferred_role_title).toBeNull();
  });

  it("says so when adding fails, rather than sitting there", async () => {
    POST.mockResolvedValue({ data: undefined, error: { detail: "x" }, response: { status: 400 } });
    renderUi(<RolePicker held={new Set()} />);
    await pickGda();
    fireEvent.click(screen.getByLabelText(/Standard n1/));
    fireEvent.click(screen.getByRole("button", { name: "Add 1 skill" }));
    expect(await screen.findByText("Could not add these. Try again.")).toBeTruthy();
  });
});

describe("SkillsSection", () => {
  it("offers the role first and the standard search as the fallback", () => {
    const { container } = renderUi(<SkillsSection profile={null} />);
    const text = container.textContent ?? "";
    expect(text.indexOf("What work do you do?")).toBeLessThan(
      text.indexOf("Or search the standards directly"),
    );
  });

  it("the fallback is the shared picker: code shown, and an empty result said", async () => {
    // The section used to carry its own fork of this search, which had lost
    // both. These two assertions fail against that fork.
    GET.mockImplementation(async (path: string, init?: { params?: { query?: { q?: string } } }) => {
      if (path === "/skills/search" && init?.params?.query?.q === "blood") {
        return {
          data: [{ slug: "blood", name: "Collect blood samples", nos_code: "HSS/N0513" }],
          error: undefined,
        };
      }
      return { data: [], error: undefined };
    });
    renderUi(<SkillsSection profile={null} />);
    const search = screen.getByLabelText("Try 'blood', 'रक्त' or 'khoon nikalna'");

    fireEvent.change(search, { target: { value: "blood" } });
    expect(await screen.findByText("HSS/N0513")).toBeTruthy();

    fireEvent.change(search, { target: { value: "zzz" } });
    expect(await screen.findByText(/Nothing matched that/)).toBeTruthy();
  });
});
