import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProfileEditor } from "@/components/ProfileEditor";
import { ApiError } from "@/lib/http";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const profileState = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
}));

vi.mock("@/lib/profile", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/profile")>()),
  useProfile: () => profileState.current,
}));

beforeEach(resetWorld);

/**
 * A profile that failed to load is not an empty profile.
 *
 * `useProfile` turned any failure into `null`, so a 500 or a dropped
 * connection rendered the full editor at 0% complete -- and the About section
 * saves the whole form with a PUT, so pressing save wrote those blanks over
 * the profile the page had failed to read.
 */
describe("ProfileEditor — a failed load never becomes a blank editor", () => {
  it("shows the error, and no form to save, when the profile cannot be read", () => {
    profileState.current = {
      isPending: false,
      isError: true,
      error: new ApiError(500, null),
      data: undefined,
    };
    renderUi(<ProfileEditor />);

    expect(screen.getByText("Could not load your profile. Please try again.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("says the session expired on a 401, rather than a load failure", () => {
    profileState.current = {
      isPending: false,
      isError: true,
      error: new ApiError(401, null),
      data: undefined,
    };
    renderUi(<ProfileEditor />);

    expect(
      screen.getByText("Your session has expired. Sign in again to continue."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("shows the server's own words when it gave a reason", () => {
    profileState.current = {
      isPending: false,
      isError: true,
      error: new ApiError(503, "Profile service is restarting"),
      data: undefined,
    };
    renderUi(<ProfileEditor />);

    expect(screen.getByText("Profile service is restarting")).toBeTruthy();
  });
});
