import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsentBanner } from "@/components/ConsentBanner";
import { PRIVACY_NOTICE_VERSION } from "@/lib/legal";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const POST = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: vi.fn(), POST: (...a: unknown[]) => POST(...a) } }));

beforeEach(() => {
  resetWorld();
  POST.mockReset();
  sessionStorage.clear();
});

/** Sprint 72: ask when the notice changed, say so when the account is paused, never block. */
describe("the consent banner", () => {
  it("says nothing to somebody who agreed to the notice in force", () => {
    renderUi(<ConsentBanner />);
    expect(screen.queryByText("The privacy notice has changed")).toBeNull();
    expect(screen.queryByText("Your account is paused")).toBeNull();
  });

  it("says nothing to somebody with no consent on record: that is the Account page's sentence", () => {
    world.account.consent_version = null;
    world.account.consent_current = false;
    renderUi(<ConsentBanner />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("renders nothing until the account has arrived, so it cannot push the page down", () => {
    world.pending = true;
    world.account.consent_current = false;
    renderUi(<ConsentBanner />);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("asks a person whose notice is stale to read it and confirm, and confirms the version it shows", async () => {
    world.account.consent_version = "2026-09-11";
    world.account.consent_current = false;
    POST.mockResolvedValue({ data: { withdrawn: false }, response: { status: 200 } });
    renderUi(<ConsentBanner />);
    expect(screen.getByText("The privacy notice has changed")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Read the notice" }).getAttribute("href")).toBe("/privacy");
    fireEvent.click(screen.getByRole("button", { name: "I have read it and I am 18 or over" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(POST).toHaveBeenCalledWith("/me/account/consent", {
      body: { consent_version: PRIVACY_NOTICE_VERSION },
    });
  });

  it("tells somebody who withdrew that the account is paused and offers to switch it back on", () => {
    world.account.consent_withdrawn = true;
    renderUi(<ConsentBanner />);
    expect(screen.getByText("Your account is paused")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Confirm and switch back on" })).toBeTruthy();
  });

  it("shows the server's sentence when confirming is refused, not a fixed line", async () => {
    world.account.consent_current = false;
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "consent_required" },
      response: { status: 422 },
    });
    renderUi(<ConsentBanner />);
    fireEvent.click(screen.getByRole("button", { name: "I have read it and I am 18 or over" }));
    expect(await screen.findByText(/consent_required|We could not record that/)).toBeTruthy();
  });

  it("is fixed to the window, so arriving late can never move the page (ADR-065)", () => {
    world.account.consent_current = false;
    renderUi(<ConsentBanner />);
    const box = screen.getByRole("status").parentElement!;
    expect(box.className).toContain("fixed");
    // At the bottom of the window, above the job seeker's tab bar when there is one (`--tabbar` is 0 when not).
    expect(box.className).toContain("bottom-[var(--tabbar)]");
  });

  it("hides for this session on 'Not now', and asks again in the next one", () => {
    world.account.consent_current = false;
    const first = renderUi(<ConsentBanner />);
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(screen.queryByRole("status")).toBeNull();
    first.unmount();
    renderUi(<ConsentBanner />); // same session: still hidden
    expect(screen.queryByRole("status")).toBeNull();
    sessionStorage.clear(); // a new session
    first.unmount();
    renderUi(<ConsentBanner />);
    expect(screen.getByRole("status")).toBeTruthy();
  });

  it("does not let a dismissed stale notice hide the paused account's banner", () => {
    sessionStorage.setItem("iism.consent.dismissed.stale", "1");
    world.account.consent_withdrawn = true;
    renderUi(<ConsentBanner />);
    expect(screen.getByText("Your account is paused")).toBeTruthy();
  });

  it("holds this build's version equal to the sentence's: the date is the one in the notice file", () => {
    expect(PRIVACY_NOTICE_VERSION).toBe("2026-10-24");
  });
});
