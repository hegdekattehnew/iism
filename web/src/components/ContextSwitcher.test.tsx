import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ContextSwitcher } from "@/components/ContextSwitcher";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

/**
 * The switcher, at the size a real account reaches.
 *
 * It had no test file at all, which is how it got to ten organisations
 * unnoticed. Measured before the fix: 656px of a 720px laptop screen, and on
 * the 360x640 phone this product targets the open mobile nav came to 1311px --
 * more than twice the screen -- with "Create an organisation" below all of it.
 *
 * jsdom has no layout, so none of that can be measured here. What *can* be
 * checked is the structure that produces it: that the list sits inside a
 * bounded scroll container, that the two controls which must never be pushed
 * away sit outside it, and that the filter and ordering do their job.
 */

const TEN = [
  "Zeta Staffing",
  "Apollo Care Hospitals",
  "Medline Diagnostics",
  "Bharat Vocational Centre",
  "Swift Logistics",
  "Sunrise Multispeciality",
  "NSDC Healthcare Academy",
  "SkillBridge Institute",
  "Care First Clinics",
  "Delta Training Trust",
];

const manyOrgs = () =>
  TEN.map((name, i) =>
    org(`org-${i}`, i % 2 ? "course_provider" : "employer", name),
  );

const menu = () => screen.getByRole("menu");
const scrollBox = () =>
  menu().querySelector<HTMLElement>(".overflow-y-auto") as HTMLElement;
const openSwitcher = () =>
  fireEvent.click(screen.getByRole("button", { expanded: false }));

beforeEach(() => {
  resetWorld();
  localStorage.clear();
});

describe("ContextSwitcher — a list that does not grow without limit", () => {
  it("puts every organisation inside one bounded, scrollable box", () => {
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();

    const box = scrollBox();
    expect(box).not.toBeNull();
    // The bound itself. Without it the panel is as tall as the list.
    expect(box.className).toMatch(/max-h-/);
    expect(box.className).toMatch(/overflow-y-auto/);
    expect(within(box).getAllByRole("menuitem")).toHaveLength(TEN.length);
  });

  it("keeps the job-seeker row and Create outside that box", () => {
    // These are the two things a long list used to push off the screen, and
    // Create is what somebody opens the menu for when they cannot find what
    // they are looking for.
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();

    const box = scrollBox();
    const create = screen.getByRole("menuitem", { name: "Create an organisation" });
    const seeker = screen.getByRole("menuitem", { name: /Job seeker/ });
    expect(box.contains(create)).toBe(false);
    expect(box.contains(seeker)).toBe(false);
  });
});

describe("ContextSwitcher — the filter", () => {
  it("appears once there are enough organisations to be worth filtering", () => {
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    expect(screen.getByRole("searchbox", { name: "Filter your organisations" })).toBeTruthy();
  });

  it("stays out of the way when the whole list is already visible", () => {
    // Below the threshold a filter is noise: pointing is faster than typing.
    world.memberships = [personal(), org("a", "employer", "Acme"), org("b")];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("narrows the list by name", () => {
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "apollo" } });

    const names = within(scrollBox())
      .getAllByRole("menuitem")
      .map((b) => b.textContent);
    expect(names).toHaveLength(1);
    expect(names[0]).toMatch(/Apollo Care Hospitals/);
  });

  it("matches the slug too, for somebody who knows the URL", () => {
    world.memberships = [personal(), org("bharat-vtc", "employer", "Totally Different Name")];
    world.memberships.push(...manyOrgs());
    renderUi(<ContextSwitcher />);
    openSwitcher();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "bharat-vtc" } });
    expect(within(scrollBox()).getAllByRole("menuitem")).toHaveLength(1);
  });

  it("says nothing matched rather than showing an empty box", () => {
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzzzz" } });

    expect(within(scrollBox()).queryAllByRole("menuitem")).toHaveLength(0);
    expect(screen.getByText("Nothing matched that.")).toBeTruthy();
    // And the way out is still there.
    expect(screen.getByRole("menuitem", { name: "Create an organisation" })).toBeTruthy();
  });

  it("does not reopen still filtered", () => {
    // Reopening to a narrowed list with no memory of having typed reads as
    // "my organisations are missing".
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "apollo" } });
    fireEvent.keyDown(document, { key: "Escape" });

    openSwitcher();
    expect(within(scrollBox()).getAllByRole("menuitem")).toHaveLength(TEN.length);
  });
});

describe("ContextSwitcher — the order", () => {
  const names = () =>
    within(scrollBox())
      .getAllByRole("menuitem")
      .map((b) => (b.textContent ?? "").split("Employer")[0].split("Training")[0].trim());

  it("falls back to alphabetical, so a long tail is scannable", () => {
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();

    const shown = names();
    expect(shown[0]).toBe("Apollo Care Hospitals");
    expect(shown[shown.length - 1]).toBe("Zeta Staffing");
  });

  it("puts the organisation you are standing in first", () => {
    world.memberships = [personal(), ...manyOrgs()];
    world.pathname = "/employer/org-0"; // Zeta Staffing, last alphabetically
    renderUi(<ContextSwitcher />);
    openSwitcher();
    expect(names()[0]).toBe("Zeta Staffing");
  });

  it("floats recently used organisations above the rest", () => {
    // The two you actually move between should not be a scroll away.
    localStorage.setItem("iism.recent_contexts", JSON.stringify(["org-4", "org-6"]));
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();

    expect(names().slice(0, 2)).toEqual(["Swift Logistics", "NSDC Healthcare Academy"]);
  });

  it("ignores a corrupted recency value rather than failing to render", () => {
    localStorage.setItem("iism.recent_contexts", "not json at all");
    world.memberships = [personal(), ...manyOrgs()];
    renderUi(<ContextSwitcher />);
    openSwitcher();
    expect(names()[0]).toBe("Apollo Care Hospitals");
  });
});
