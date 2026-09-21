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
  });

  it("shows no organisation nav while it cannot yet tell what kind it is", () => {
    // `ORG_NAV[orgType ?? "employer"]` flashed "Vacancies" at every provider.
    world.pending = true;
    world.pathname = "/employer/tnt";
    renderUi(<Header />);

    expect(link("Vacancies")).toBeNull();
  });

  it("carries no job-seeker buttons inside an organisation", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<Header />);

    expect(link("Vacancies")).not.toBeNull();
    expect(link("My profile")).toBeNull();
    expect(link("My matches")).toBeNull();
    expect(link("Organisation profile")).not.toBeNull();
  });

  it("shows the public nav outside an organisation", () => {
    world.pathname = "/";
    renderUi(<Header />);

    expect(link("Jobs")?.getAttribute("href")).toBe("/jobs");
  });

  it("remembers which side of the account was last used", () => {
    world.memberships = [personal(), org("acme")];
    world.pathname = "/employer/acme";
    renderUi(<Header />);

    expect(localStorage.getItem("iism.last_context")).toBe("acme");
  });
});
