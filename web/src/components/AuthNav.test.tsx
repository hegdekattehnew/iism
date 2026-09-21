import { screen } from "@testing-library/react";
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

    expect(link("My matches")?.getAttribute("href")).toBe("/matches");
    expect(link("My profile")?.getAttribute("href")).toBe("/profile");
  });

  it("never offers the job-seeker side to an organisation-only account", () => {
    world.memberships = [org("acme")];
    world.pathname = "/jobs";
    renderUi(<AuthNav />);

    expect(link("My matches")).toBeNull();
    expect(link("My profile")).toBeNull();
    expect(link("My workspace")?.getAttribute("href")).toBe("/employer/acme");
  });

  it("does not treat a slug in the URL as membership", () => {
    world.memberships = [personal()];
    world.pathname = "/employer/someone-elses-org";
    renderUi(<AuthNav />);

    expect(link("Organisation profile")).toBeNull();
    expect(link("My profile")).not.toBeNull();
  });

  it("offers no destinations while it does not yet know who you are", () => {
    world.pending = true;
    renderUi(<AuthNav />);

    expect(link("My matches")).toBeNull();
    expect(link("Organisation profile")).toBeNull();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeTruthy();
  });

  it("offers every way in to someone signed out", () => {
    world.signedIn = false;
    renderUi(<AuthNav />);

    expect(link("Get started")?.getAttribute("href")).toBe("/signup");
  });
});
