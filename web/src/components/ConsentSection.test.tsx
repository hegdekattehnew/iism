import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsentSection } from "@/components/ConsentSection";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const STATE = {
  consent_version: "2026-10-24",
  consented_at: "2026-10-01T10:00:00Z",
  notice_version: "2026-10-24",
  current: true,
  withdrawn: false,
  consent_withdrawn_at: null as string | null,
  live_applications: 0,
  live_interests: 0,
};

function serve(over: Partial<typeof STATE> = {}) {
  GET.mockImplementation(async () => ({ data: { ...STATE, ...over }, response: { status: 200 } }));
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

/** Sprint 72: withdrawing consent shows who holds your details first, and is a pause, not a deletion. */
describe("the consent section", () => {
  it("says what was agreed and when, and offers to withdraw", async () => {
    serve();
    renderUi(<ConsentSection />);
    expect(await screen.findByText(/You agreed to the privacy notice of 2026-10-24/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Withdraw my consent…" })).toBeTruthy();
  });

  it("is a placeholder, not a claim, until the state arrives", () => {
    GET.mockImplementation(() => new Promise(() => undefined));
    renderUi(<ConsentSection />);
    expect(screen.queryByText(/You agreed/)).toBeNull();
    expect(screen.queryByText(/No consent is recorded/)).toBeNull();
  });

  it("shows who holds the person's details before the button that ends it", async () => {
    serve({ live_applications: 2, live_interests: 1 });
    renderUi(<ConsentSection />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw my consent…" }));
    expect(
      await screen.findByText(/takes back 2 applications and 1 course interest/),
    ).toBeTruthy();
    expect(POST).not.toHaveBeenCalled(); // looking changes nothing
  });

  it("says plainly when nobody holds them", async () => {
    serve();
    renderUi(<ConsentSection />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw my consent…" }));
    expect(await screen.findByText(/No employer or training provider holds your contact/)).toBeTruthy();
  });

  it("withdraws on confirmation and says it is not an erasure", async () => {
    serve();
    POST.mockResolvedValue({ data: { ...STATE, withdrawn: true }, response: { status: 200 } });
    renderUi(<ConsentSection />);
    expect(await screen.findByText(/This is a pause, not an erasure/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw my consent…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw my consent" }));
    await waitFor(() => expect(POST).toHaveBeenCalledWith("/me/account/consent/withdraw"));
  });

  it("offers to come back, not to withdraw again, once withdrawn", async () => {
    serve({ withdrawn: true, consent_withdrawn_at: "2026-10-05T08:00:00Z" });
    renderUi(<ConsentSection />);
    expect(await screen.findByText(/You withdrew your consent on Oct 5, 2026/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Confirm and switch my account back on" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Withdraw my consent…" })).toBeNull();
  });

  it("reads a refusal to withdraw and says nothing changed", async () => {
    serve();
    POST.mockResolvedValue({ data: undefined, error: { detail: "boom" }, response: { status: 500 } });
    renderUi(<ConsentSection />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw my consent…" }));
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw my consent" }));
    expect(await screen.findByText(/boom|could not be withdrawn/)).toBeTruthy();
  });
});
