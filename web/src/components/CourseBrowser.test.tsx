import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseBrowser } from "@/components/CourseBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const course = (n: number, extra: Record<string, unknown> = {}) => ({
  slug: `course-${n}`,
  title: `Course number ${n}`,
  mode: "offline",
  language: "en",
  duration_hours: 40,
  fee_inr: 0,
  tenant: { name: "Academy" },
  ...extra,
});

const serve = (items: unknown[]) =>
  GET.mockResolvedValue({ data: { items, total: items.length, limit: 24, offset: 0 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

/** Sprint 75, BL-12.8: what a provider says the course counts toward, as a small chip. */
describe("the credit chip on a course card", () => {
  it("says how many credits the qualification is worth", async () => {
    serve([course(1, { qualification_credits: 14 }), course(2, { qualification_credits: 1 })]);
    renderUi(<CourseBrowser />);
    expect(await screen.findByText("14 credits")).toBeTruthy();
    expect(screen.getByText("1 credit")).toBeTruthy();
  });

  it("draws nothing for a course with no qualification, a zero, or a figure that is not a number", async () => {
    serve([
      course(1),
      course(2, { qualification_credits: null }),
      course(3, { qualification_credits: 0 }),
      course(4, { qualification_credits: Number.NaN }),
    ]);
    renderUi(<CourseBrowser />);
    await screen.findByText("Course number 4");
    expect(screen.queryByText(/credit/i)).toBeNull();
  });
});

/** Sprint 84, BL-19.15: the filters are one row of chips; a chip that narrows the list is drawn filled. */
describe("the filter chips", () => {
  it("are one named group of three selects, and the card is the shared one", async () => {
    serve([course(1)]);
    renderUi(<CourseBrowser />);
    await screen.findByText("Course number 1");
    const group = screen.getByRole("group", { name: "Filters" });
    expect(group.querySelectorAll("select")).toHaveLength(3);
    expect(screen.getByText("Course number 1").closest("a")?.className).toContain("shadow-card");
  });

  it.each([
    ["All modes", "online"],
    ["All languages", "hi"],
    ["Any fee", "2000"],
  ])("%s is drawn filled once it has a value, and plain again when cleared", async (name, value) => {
    serve([course(1)]);
    renderUi(<CourseBrowser />);
    await screen.findByText("Course number 1");
    const chip = () => screen.getByRole("combobox", { name }).parentElement as HTMLElement;
    expect(chip().className).not.toContain("bg-accent-soft");
    fireEvent.change(screen.getByRole("combobox", { name }), { target: { value } });
    expect(chip().className).toContain("bg-accent-soft");
    fireEvent.click(await screen.findByRole("button", { name: "Clear" }));
    expect(chip().className).not.toContain("bg-accent-soft");
  });
});
