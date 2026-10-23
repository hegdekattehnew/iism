import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomeAccess } from "@/components/HomeAccess";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(() => {
  resetWorld();
  localStorage.clear();
});

const chooser = <p data-testid="chooser">I&apos;m here to…</p>;

/**
 * Sprint 91, B22.1. The front page offered "Find work / Hire / Publish courses" to a provider who
 * was signed in and running an organisation: the home page forgot who you were outside the
 * workspace. A signed-in person gets their own doors; the chooser is for a visitor.
 */
describe("HomeAccess", () => {
  it("shows a visitor the chooser it is given", () => {
    world.signedIn = false;
    renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByTestId("chooser")).toBeTruthy();
    expect(screen.queryByText("Welcome back")).toBeNull();
  });

  it("welcomes a provider back to its organisation, and offers no sign-up", () => {
    world.memberships = [org("nsdc-healthcare-academy", "course_provider", "NSDC Healthcare Academy")];
    renderUi(<HomeAccess>{chooser}</HomeAccess>);

    expect(screen.getByText("Welcome back")).toBeTruthy();
    const link = screen.getByRole("link", { name: /NSDC Healthcare Academy/ });
    expect(link.getAttribute("href")).toBe("/employer/nsdc-healthcare-academy");
    expect(screen.getByText("Training · open your workspace")).toBeTruthy();
    expect(screen.queryByTestId("chooser")).toBeNull();
  });

  it("says Hiring for an employer and Training for a provider", () => {
    world.memberships = [org("a", "employer", "Apollo Care"), org("b", "course_provider", "NSDC Academy")];
    renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByText("Hiring · open your workspace")).toBeTruthy();
    expect(screen.getByText("Training · open your workspace")).toBeTruthy();
  });

  it("says what a centre is when a manager has only a centre (Sprint 96)", () => {
    world.memberships = [org("hadapsar", "training_centre", "Hadapsar")];
    renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByText("Centre · open it")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Hadapsar/ }).getAttribute("href")).toBe("/employer/hadapsar");
  });

  it("offers a job seeker their matches", () => {
    world.memberships = [personal()];
    renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByRole("link", { name: /Your matches/ }).getAttribute("href")).toBe("/matches");
    expect(screen.queryByTestId("chooser")).toBeNull();
  });

  it("offers both to somebody who looks for work and runs an organisation", () => {
    world.memberships = [personal(), org("apollo", "employer", "Apollo Care")];
    renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByRole("link", { name: /Your matches/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Apollo Care/ })).toBeTruthy();
  });

  it("lists three organisations, the most recently used first, and points at the menu for the rest", () => {
    world.memberships = ["Zeta", "Alpha", "Beta", "Gamma", "Delta"].map((n) => org(n.toLowerCase(), "employer", n));
    localStorage.setItem("iism.recent_contexts", JSON.stringify(["zeta"]));
    renderUi(<HomeAccess>{chooser}</HomeAccess>);

    const names = screen.getAllByRole("link").map((a) => a.textContent ?? "");
    expect(names).toHaveLength(3);
    expect(names[0]).toContain("Zeta");
    expect(names[1]).toContain("Alpha");
    expect(screen.getByText("2 more workspaces are in the menu at the top.")).toBeTruthy();
  });

  it("holds its place with a placeholder, and never the chooser, while the account loads", () => {
    world.pending = true;
    const { container } = renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.queryByTestId("chooser")).toBeNull();
    expect(screen.queryByText("Welcome back")).toBeNull();
    expect(container.querySelector("[data-loading]")).toBeTruthy();
  });

  it("falls back to the chooser, marked as shown, when the stored sign-in is dead", () => {
    world.meError = true;
    const { container } = renderUi(<HomeAccess>{chooser}</HomeAccess>);
    expect(screen.getByTestId("chooser")).toBeTruthy();
    expect(container.querySelector("[data-home-chooser][data-shown]")).toBeTruthy();
  });

  it("marks a visitor's chooser so the stylesheet can hide it for a browser that holds a sign-in", () => {
    world.signedIn = false;
    const { container } = renderUi(<HomeAccess>{chooser}</HomeAccess>);
    const wrapper = container.querySelector("[data-home-chooser]");
    expect(wrapper).toBeTruthy();
    expect(wrapper?.hasAttribute("data-shown")).toBe(false);
  });
});
