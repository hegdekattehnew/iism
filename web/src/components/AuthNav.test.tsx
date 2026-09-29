import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthNav } from "@/components/AuthNav";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

const link = (name: string) => screen.queryByRole("link", { name });

/**
 * Open the account menu.
 *
 * Sprint 26 moved the account plumbing behind one trigger: ten controls in a
 * flat header row, with "My matches" as a filled brand button competing with
 * the page's own primary action, was the thing that made the header read as
 * unfinished. The destinations did not change -- every assertion below is the
 * one it was before, asked of an open menu.
 */
const openAccountMenu = () =>
  fireEvent.click(screen.getByRole("button", { name: "Account" }));

describe("AuthNav — the header's profile slot follows the context", () => {
  it("offers the organisation's profile, not the candidate's, inside an organisation", () => {
    // The reported bug: switched to `tnt`, clicked "My profile", landed on
    // the job-seeker editor.
    world.memberships = [personal(), org("tnt", "course_provider")];
    world.pathname = "/employer/tnt";
    renderUi(<AuthNav />);

    expect(link("Organisation profile")?.getAttribute("href")).toBe(
      "/employer/tnt/settings",
    );
    expect(link("My profile")).toBeNull();
    expect(link("My matches")).toBeNull();
  });

  it("offers matches and profile to a job seeker outside any organisation", () => {
    world.memberships = [personal(), org("tnt")];
    world.pathname = "/jobs";
    renderUi(<AuthNav />);

    // Matches stays the one visible action; the rest is one click away.
    expect(link("My matches")?.getAttribute("href")).toBe("/matches");
    openAccountMenu();
    expect(link("My profile")?.getAttribute("href")).toBe("/profile");
    expect(link("My applications")?.getAttribute("href")).toBe("/applications");
  });

  it("never offers the job-seeker side to an organisation-only account", () => {
    world.memberships = [org("acme")];
    world.pathname = "/jobs";
    renderUi(<AuthNav />);

    expect(link("My matches")).toBeNull();
    expect(link("My workspace")?.getAttribute("href")).toBe("/employer/acme");
    // And not hiding in the menu either, which is where a refactor would most
    // easily put it back.
    openAccountMenu();
    expect(link("My profile")).toBeNull();
    expect(link("My applications")).toBeNull();
  });

  it("does not treat a slug in the URL as membership", () => {
    world.memberships = [personal()];
    world.pathname = "/employer/someone-elses-org";
    renderUi(<AuthNav />);

    expect(link("Organisation profile")).toBeNull();
    openAccountMenu();
    expect(link("My profile")).not.toBeNull();
  });

  it("offers no destinations while it does not yet know who you are", () => {
    world.pending = true;
    renderUi(<AuthNav />);

    expect(link("My matches")).toBeNull();
    expect(link("Organisation profile")).toBeNull();
    // Signing out never depends on knowing what the account holds.
    openAccountMenu();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });

  it("offers every way in to someone signed out", () => {
    world.signedIn = false;
    renderUi(<AuthNav />);

    expect(link("Get started")?.getAttribute("href")).toBe("/signup");
  });
});
