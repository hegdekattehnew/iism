import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AboutSection } from "@/components/profile/AboutSection";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: vi.fn(),
    POST: vi.fn(),
    PUT: (...a: unknown[]) => PUT(...a),
    DELETE: vi.fn(),
  },
}));

/**
 * Core details and preferences.
 *
 * This form had a success indicator and **no failure one**: a refused save --
 * a name over 120 characters, a salary range the server rejects, an expired
 * token -- left the button ready and nothing else changed, so the only way to
 * tell a save from a silent refusal was to reload the page.
 */

const profile = {
  id: "p1",
  full_name: "Asha",
  years_experience: 0,
  skills: [],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any;

beforeEach(() => {
  resetWorld();
  PUT.mockReset();
  PUT.mockResolvedValue({ data: profile, error: undefined, response: { status: 200 } });
});

const save = () => fireEvent.click(screen.getByRole("button", { name: "Save" }));

describe("AboutSection", () => {
  it("shows the field and the rule the server named", async () => {
    PUT.mockResolvedValue({
      data: undefined,
      error: { detail: [{ loc: ["body", "full_name"], msg: "String should have at most 120 characters" }] },
      response: { status: 422 },
    });
    renderUi(<AboutSection profile={profile} />);
    save();

    expect(
      await screen.findByText(/Full name: String should have at most 120 characters/),
    ).toBeTruthy();
  });

  it("falls back to the generic line when the refusal carried nothing", async () => {
    PUT.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<AboutSection profile={profile} />);
    save();

    expect(await screen.findByText(/Could not save\. Please check the fields/)).toBeTruthy();
  });

  it("says saved, and nothing about a failure, when it worked", async () => {
    renderUi(<AboutSection profile={profile} />);
    save();

    expect(await screen.findByText("Saved")).toBeTruthy();
    expect(screen.queryByText(/Could not save/)).toBeNull();
  });
});
