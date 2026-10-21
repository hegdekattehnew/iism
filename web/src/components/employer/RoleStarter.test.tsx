import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobEditor } from "@/components/employer/JobEditor";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const ROLE = { slug: "general-duty-assistant", job_role: "General Duty Assistant", qp_code: "HSS/Q5101", standards_count: 4, match_kind: "alias", matched_on: "ward boy", variants: 1 };
const STANDARDS = [
  { slug: "hand-hygiene", name: "Maintain hand hygiene", nos_code: "HSS/N5113", requirement: "compulsory", group_name: null },
  { slug: "bed-making", name: "Make the bed", nos_code: "HSS/N5114", requirement: "compulsory", group_name: null },
  { slug: "elective-one", name: "An elective", nos_code: "HSS/N9001", requirement: "elective", group_name: "Choose one" },
  { slug: "optional-one", name: "An optional extra", nos_code: "HSS/N9002", requirement: "optional", group_name: null },
];

function serve(opts: { roles?: unknown[]; standards?: unknown[] | null } = {}) {
  GET.mockImplementation(async (path: string) => {
    if (path === "/roles/search") return { data: opts.roles ?? [ROLE], error: undefined };
    if (path === "/roles/{slug}/standards") {
      return opts.standards === null
        ? { data: undefined, error: { detail: "x" } }
        : { data: { standards: opts.standards ?? STANDARDS }, error: undefined };
    }
    return { data: [], error: undefined };
  });
}

const editor = () => <JobEditor job={null} saving={false} onSave={vi.fn()} onCancel={vi.fn()} />;
const search = (q = "ward boy") =>
  fireEvent.change(screen.getByLabelText("Start from a job role"), { target: { value: q } });
const choose = async () => fireEvent.click(await screen.findByRole("button", { name: /General Duty Assistant/ }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  serve();
});

/**
 * Sprint 91, B22.3. An employer had to find National Occupational Standards one at a time to post a
 * vacancy; the single-vacancy form was the only place without the role-first path bulk upload has.
 */
describe("JobEditor — start from a job role", () => {
  it("offers the role search above the standards search, in the employer's words", () => {
    renderUi(editor());
    expect(screen.getByLabelText("Start from a job role")).toBeTruthy();
    expect(screen.getByText(/Type the job, such as/)).toBeTruthy();
    expect(screen.getByPlaceholderText("e.g. ward boy, electrician, cashier")).toBeTruthy();
  });

  it("adds only the role's compulsory standards, at importance 3 and not mandatory", async () => {
    renderUi(editor());
    search();
    await choose();

    expect(await screen.findByText(/Added 2 skills for General Duty Assistant/)).toBeTruthy();
    expect(screen.getByText("Maintain hand hygiene")).toBeTruthy();
    expect(screen.getByText("Make the bed")).toBeTruthy();
    expect(screen.queryByText("An elective")).toBeNull();
    expect(screen.queryByText("An optional extra")).toBeNull();

    // The same defaults the bulk upload gives a `job_role`.
    const rows = screen.getAllByText(/Maintain hand hygiene|Make the bed/).map((e) => e.closest("li") as HTMLElement);
    for (const row of rows) {
      const importance = within(row).getByRole("combobox") as HTMLSelectElement;
      expect(importance.value).toBe("3");
      expect((within(row).getByRole("checkbox") as HTMLInputElement).checked).toBe(false);
    }
  });

  it("does not add a standard the vacancy already has", async () => {
    renderUi(editor());
    search();
    await choose();
    await screen.findByText(/Added 2 skills/);

    // Choosing the same role again adds nothing new, and says so.
    search("ward boy ");
    await choose();
    expect(await screen.findByText("Everything for General Duty Assistant is already on the vacancy.")).toBeTruthy();
    expect(screen.getAllByText("Maintain hand hygiene")).toHaveLength(1);
  });

  it("never lists a standard twice when two lookups of the same role finish after each other", async () => {
    // Typing on while the first lookup is in flight chooses the role again: both answers arrive after
    // the page last rendered, so `chosen` is stale for the second and only the list itself can refuse.
    const waiting: Array<(v: unknown) => void> = [];
    GET.mockImplementation(async (path: string) => {
      if (path === "/roles/search") return { data: [ROLE], error: undefined };
      return new Promise((resolve) => waiting.push(resolve));
    });
    renderUi(editor());
    search();
    await choose();
    search("ward boy ");
    await choose();
    await waitFor(() => expect(waiting).toHaveLength(2));
    for (const resolve of waiting) resolve({ data: { standards: STANDARDS }, error: undefined });

    await screen.findByText(/Added /);
    await waitFor(() => expect(screen.getAllByText("Maintain hand hygiene")).toHaveLength(1));
    expect(screen.getAllByText("Make the bed")).toHaveLength(1);
  });

  it("offers the role as the title only while the title is empty, and fills it when asked", async () => {
    renderUi(editor());
    search();
    await choose();

    const useTitle = await screen.findByRole("button", { name: "Use “General Duty Assistant” as the title" });
    fireEvent.click(useTitle);
    expect((screen.getByLabelText(/Job title/) as HTMLInputElement).value).toBe("General Duty Assistant");
  });

  it("does not offer to overwrite a title that has been typed", async () => {
    renderUi(editor());
    fireEvent.change(screen.getByLabelText(/Job title/), { target: { value: "Night ward attendant" } });
    search();
    await choose();
    await screen.findByText(/Added 2 skills/);
    expect(screen.queryByRole("button", { name: /as the title/ })).toBeNull();
  });

  it("says so when no job has that name, and leaves the standards search", async () => {
    serve({ roles: [] });
    renderUi(editor());
    search("zzzz");
    expect(await screen.findByText("No job by that name. Try another word, or add skills yourself below.")).toBeTruthy();
    expect(screen.getByPlaceholderText(/Search/i)).toBeTruthy();
  });

  it("says so, and adds nothing, when the standards cannot be loaded", async () => {
    serve({ standards: null });
    renderUi(editor());
    search();
    await choose();
    expect(await screen.findByText("Could not load the skills for this job. Try again.")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText(/^Added /)).toBeNull());
    expect(screen.queryByText("Maintain hand hygiene")).toBeNull();
  });
});
