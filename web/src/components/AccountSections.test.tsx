import { readFileSync } from "node:fs";
import { join } from "node:path";

import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountPanel } from "@/components/AccountPanel";
import { ConsentSection } from "@/components/ConsentSection";
import { CredentialsSection } from "@/components/profile/CredentialsSection";
import { IconTile } from "@/components/ui/icon-tile";
import { UserIcon } from "@/components/ui/icons";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  GET.mockResolvedValue({
    data: {
      consent_version: "2026-10-24",
      consented_at: "2026-10-01T10:00:00Z",
      notice_version: "2026-10-24",
      current: true,
      withdrawn: false,
      consent_withdrawn_at: null,
      live_applications: 0,
      live_interests: 0,
    },
    error: undefined,
    response: { status: 200 },
  });
});

const tileBeside = (heading: HTMLElement) => heading.parentElement!.querySelector("[aria-hidden='true']") as HTMLElement | null;

/** Sprint 87, BL-19.17: the account's four sections each lead with a mark, and the profile's copy of one does not. */
describe("the account's sections", () => {
  it("lead with a mark each: sign-in, consent, export and delete", async () => {
    renderUi(<AccountPanel />);
    for (const name of ["How you sign in", "Consent", "Download your data", "Delete your account"]) {
      const heading = await screen.findByRole("heading", { level: 2, name });
      const tile = tileBeside(heading);
      expect(tile, name).toBeTruthy();
      expect(tile!.querySelector("svg"), name).toBeTruthy();
    }
  });

  it("says what each is by tone: consent is good, delete is a warning, the rest the brand's", async () => {
    renderUi(<AccountPanel />);
    expect(tileBeside(await screen.findByRole("heading", { name: "Consent" }))!.className).toContain("bg-success-surface");
    expect(tileBeside(await screen.findByRole("heading", { name: "Delete your account" }))!.className).toContain("bg-warning-surface");
    expect(tileBeside(await screen.findByRole("heading", { name: "Download your data" }))!.className).toContain("bg-accent-soft");
  });
});

describe("ConsentSection's link to the notice", () => {
  it("is a 44 px target and still goes to the notice", async () => {
    renderUi(<ConsentSection />);
    const link = await screen.findByRole("link", { name: "Read the privacy notice" });
    expect(link.getAttribute("href")).toBe("/privacy");
    expect(link.className).toContain("min-h-11");
  });
});

describe("CredentialsSection's optional mark", () => {
  it("draws what the account page hands it beside the heading", () => {
    world.account = { ...world.account, phone: "+919812349999", phone_verified_at: "2026-10-01T00:00:00Z" };
    renderUi(
      <CredentialsSection
        icon={
          <IconTile>
            <UserIcon />
          </IconTile>
        }
      />,
    );
    const heading = screen.getByRole("heading", { level: 2, name: "How you sign in" });
    expect(tileBeside(heading)).toBeTruthy();
  });

  it("draws nothing when it is given nothing (the profile's copy)", () => {
    world.account = { ...world.account, phone: "+919812349999", phone_verified_at: "2026-10-01T00:00:00Z" };
    renderUi(<CredentialsSection />);
    expect(tileBeside(screen.getByRole("heading", { level: 2, name: "How you sign in" }))).toBeNull();
  });

  it("does not import the icon module itself: /profile has about 1 KB left and the factory costs more", () => {
    const source = readFileSync(join(__dirname, "profile", "CredentialsSection.tsx"), "utf8");
    expect(source).not.toMatch(/from "@\/components\/ui\/(icons|icon-tile)"/);
  });
});
