import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SeekerOnly } from "@/components/SeekerOnly";
import { WorkspaceIdentity } from "@/components/WorkspaceIdentity";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

const CANDIDATE_PAGE = "the candidate profile editor";

describe("SeekerOnly — an organisation account never sees the job-seeker side", () => {
  it("replaces the candidate page for an organisation-only account", () => {
    // It used to be walked into the candidate onboarding wizard.
    world.memberships = [org("acme")];
    world.pathname = "/profile";
    renderUi(<SeekerOnly>{CANDIDATE_PAGE}</SeekerOnly>);

    expect(screen.queryByText(CANDIDATE_PAGE)).toBeNull();
    expect(screen.getByText("This is an organisation account")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Go to my workspace" }).getAttribute("href"),
    ).toBe("/employer/acme");
  });

  it("shows the page to a job seeker, including one who also hires", () => {
    world.memberships = [personal(), org("acme")];
    renderUi(<SeekerOnly>{CANDIDATE_PAGE}</SeekerOnly>);

    expect(screen.getByText(CANDIDATE_PAGE)).toBeTruthy();
  });

  it("shows nothing rather than a page about to be withdrawn", () => {
    world.pending = true;
    renderUi(<SeekerOnly>{CANDIDATE_PAGE}</SeekerOnly>);

    expect(screen.queryByText(CANDIDATE_PAGE)).toBeNull();
  });

  it("leaves a signed-out visitor to the page's own sign-in prompt", () => {
    world.signedIn = false;
    renderUi(<SeekerOnly>{CANDIDATE_PAGE}</SeekerOnly>);

    expect(screen.getByText(CANDIDATE_PAGE)).toBeTruthy();
  });
});

describe("WorkspaceIdentity — no cross-link to a side the account does not have", () => {
  it("renders nothing for an organisation-only account", () => {
    world.memberships = [org("acme")];
    world.pathname = "/profile";
    const { container } = renderUi(<WorkspaceIdentity sibling="matches" />);

    expect(container.textContent).toBe("");
  });

  it("names the job-seeker context and links across for a job seeker", () => {
    world.memberships = [personal()];
    world.pathname = "/profile";
    renderUi(<WorkspaceIdentity sibling="matches" />);

    expect(screen.getByText("Job seeker")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "My matches" }).getAttribute("href"),
    ).toBe("/matches");
  });
});
