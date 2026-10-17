import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseEditor } from "@/components/employer/CourseEditor";
import { api } from "@/lib/api";
import type { OrgCourse } from "@/lib/org";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
vi.mock("@/lib/api", () => ({
  api: { GET: vi.fn(async () => ({ data: [], error: undefined })) },
}));

beforeEach(resetWorld);

/** Sprint 73, UI-26: the form says what a good description is, since the page already lists the standards. */
describe("CourseEditor -- the description field", () => {
  it("says what to write, in the field's own hint", () => {
    renderUi(<CourseEditor course={null} saving={false} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/Say who the course is for and what a learner can do afterwards/)).toBeTruthy();
  });
});

/** Sprint 75, BL-12.8: the provider says which qualification the course counts toward. */
describe("CourseEditor -- the qualification", () => {
  const GETMOCK = vi.mocked(api.GET);
  const saved = {
    slug: "c1",
    title: "Ward care basics",
    mode: "offline",
    language: "both",
    skills: [],
    qualification_pack_code: "HSS/Q0101",
    qualification_name: "General Duty Assistant",
    qualification_credits: 14,
  } as unknown as OrgCourse;

  const submit = () => fireEvent.click(screen.getByRole("button", { name: "Save" }));

  it("shows the saved qualification and sends it back unchanged, or saving would clear it", () => {
    const onSave = vi.fn();
    renderUi(<CourseEditor course={saved} saving={false} onSave={onSave} onCancel={vi.fn()} />);
    expect(screen.getByText("General Duty Assistant")).toBeTruthy();
    expect(screen.getByText(/14 credits/)).toBeTruthy();

    submit();

    expect(onSave.mock.calls[0][0].qualification_pack_code).toBe("HSS/Q0101");
  });

  it("sends nothing for a course that has none", () => {
    const onSave = vi.fn();
    renderUi(<CourseEditor course={null} saving={false} onSave={onSave} onCancel={vi.fn()} />);
    fireEvent.change(document.querySelector("input[name=title]")!, {
      target: { value: "A new course" },
    });
    submit();
    expect(onSave.mock.calls[0][0].qualification_pack_code).toBeNull();
  });

  it("clears it when the provider removes it", () => {
    const onSave = vi.fn();
    renderUi(<CourseEditor course={saved} saving={false} onSave={onSave} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove qualification" }));
    expect(screen.queryByText("General Duty Assistant")).toBeNull();
    submit();
    expect(onSave.mock.calls[0][0].qualification_pack_code).toBeNull();
  });

  it("finds one by searching and sends its code", async () => {
    GETMOCK.mockImplementation((async (path: string) =>
      path === "/roles/search"
        ? {
            data: [
              {
                slug: "gda",
                qp_code: "HSS/Q0101",
                job_role: "General Duty Assistant",
                sector_name: "Healthcare",
                credits: 14,
              },
            ],
          }
        : { data: [] }) as never);
    const onSave = vi.fn();
    renderUi(<CourseEditor course={null} saving={false} onSave={onSave} onCancel={vi.fn()} />);
    fireEvent.change(document.querySelector("input[name=title]")!, {
      target: { value: "A new course" },
    });

    fireEvent.change(screen.getByLabelText("Qualification (optional)"), {
      target: { value: "ward boy" },
    });
    fireEvent.click(await screen.findByRole("button", { name: /General Duty Assistant/ }));
    submit();

    expect(onSave.mock.calls[0][0].qualification_pack_code).toBe("HSS/Q0101");
  });
});
