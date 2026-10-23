import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrgWorkspace } from "@/components/employer/OrgWorkspace";
import { org, personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
// The three screens are what other tests are about; this one is about which is chosen.
vi.mock("@/components/employer/EmployerWorkspace", () => ({
  EmployerWorkspace: () => <div data-testid="employer-workspace" />,
}));
vi.mock("@/components/employer/ProviderWorkspace", () => ({
  ProviderWorkspace: () => <div data-testid="provider-workspace" />,
}));
vi.mock("@/components/employer/CentreWorkspace", () => ({
  CentreWorkspace: ({ slug }: { slug: string }) => <div data-testid="centre-workspace">{slug}</div>,
}));

beforeEach(resetWorld);

/** Sprint 96: a route that renders one of three screens loads one, and the right one. */
describe("OrgWorkspace", () => {
  it.each([
    ["employer", "employer-workspace", "Your workspace"],
    ["course_provider", "provider-workspace", "Your workspace"],
    ["training_centre", "centre-workspace", "Your centre"],
  ] as const)("shows the %s its own screen and heading", async (type, testId, heading) => {
    world.memberships = [personal(), org("here", type, "Here")];
    renderUi(<OrgWorkspace orgSlug="here" />);
    expect(await screen.findByTestId(testId)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(heading);
    for (const other of ["employer-workspace", "provider-workspace", "centre-workspace"]) {
      if (other !== testId) expect(screen.queryByTestId(other)).toBeNull();
    }
  });

  it("hands the centre page the centre's own slug", async () => {
    world.memberships = [org("acme-hadapsar", "training_centre", "Hadapsar")];
    renderUi(<OrgWorkspace orgSlug="acme-hadapsar" />);
    expect((await screen.findByTestId("centre-workspace")).textContent).toBe("acme-hadapsar");
  });

  it("shows nothing of any of them for an organisation the person does not hold", () => {
    world.memberships = [personal()];
    renderUi(<OrgWorkspace orgSlug="not-mine" />);
    expect(screen.queryByTestId("centre-workspace")).toBeNull();
    expect(screen.getByText(/do not have access/i)).toBeTruthy();
  });
});
