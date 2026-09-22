import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Header } from "@/components/Header";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(() => {
  resetWorld();
  localStorage.clear();
});

const link = (name: string) => screen.queryByRole("link", { name });

describe("Header — the whole header switches, not half of it", () => {
  it("never shows a training provider the employer's nav", () => {
    world.memberships = [personal(), org("tnt", "course_provider")];
    world.pathname = "/employer/tnt";
    renderUi(<Header />);

    expect(link("Vacancies")).toBeNull();
    expect(link("Courses")?.getAttribute("href")).toBe("/employer/tnt");
    // Sprint 24: a provider reaches their inbox from the nav, because they
    // have no vacancy to reach it through the way an employer does.
    expect(link("Interested learners")?.getAttribute("href")).toBe(
      "/employer/tnt/interests",
    );
    // Sprint 25: both kinds of organisation manage a team the same way, so
    // this item is the one thing the two navs have in common.
    expect(link("Team")?.getAttribute("href")).toBe("/employer/tnt/team");
  });

  it("does not offer an employer the provider's inbox", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<Header />);

    expect(link("Interested learners")).toBeNull();
  });

  it("shows no organisation nav while it cannot yet tell what kind it is", () => {
    // `ORG_NAV[orgType ?? "employer"]` flashed "Vacancies" at every provider.
    world.pending = true;
    world.pathname = "/employer/tnt";
    renderUi(<Header />);

    expect(link("Vacancies")).toBeNull();
    expect(link("Team")).toBeNull();
  });

  it("carries no job-seeker buttons inside an organisation", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<Header />);

    expect(link("Vacancies")).not.toBeNull();
    expect(link("Team")?.getAttribute("href")).toBe("/employer/acme/team");
    expect(link("My profile")).toBeNull();
    expect(link("My matches")).toBeNull();
    expect(link("Organisation profile")).not.toBeNull();
  });

  it("shows the public nav outside an organisation", () => {
    world.pathname = "/";
    renderUi(<Header />);

    expect(link("Jobs")?.getAttribute("href")).toBe("/jobs");
    // The team belongs to an organisation, so it is not in the seeker nav.
    expect(link("Team")).toBeNull();
  });

  it("remembers which side of the account was last used", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<Header />);

    expect(localStorage.getItem("iism.last_context")).toBe("acme");
  });
});
