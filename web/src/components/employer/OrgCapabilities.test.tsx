import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrgCapabilities } from "@/components/employer/OrgCapabilities";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const PUT = vi.fn();
vi.mock("@/lib/api", () => ({ api: { PUT: (...a: unknown[]) => PUT(...a), GET: vi.fn(), POST: vi.fn() } }));

beforeEach(() => {
  resetWorld();
  PUT.mockReset();
});

const save = () => screen.getByRole("button", { name: "Save what it does" });

/** Sprint 94, ADR-102: the owner changes what the organisation does, and the server may refuse. */
describe("OrgCapabilities", () => {
  it("starts on what the organisation does, with Save held until something changes", () => {
    renderUi(<OrgCapabilities orgSlug="acme" sells delivers={false} />);
    expect(screen.getByRole("checkbox", { name: /Sells courses/ })).toHaveProperty("checked", true);
    expect(screen.getByRole("checkbox", { name: /Delivers training/ })).toHaveProperty("checked", false);
    expect(save()).toHaveProperty("disabled", true);
  });

  it("sends both values to the organisation's own route", async () => {
    PUT.mockResolvedValue({
      data: { slug: "acme", publishes_courses: true, delivers_training: true },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<OrgCapabilities orgSlug="acme" sells delivers={false} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Delivers training/ }));
    fireEvent.click(save());
    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    const [path, init] = PUT.mock.calls[0] as [
      string,
      { params: { path: { org_slug: string } }; body: Record<string, boolean> },
    ];
    expect(path).toBe("/org/{org_slug}/capabilities");
    expect(init.params.path.org_slug).toBe("acme");
    expect(init.body).toEqual({ sells_courses: true, delivers_training: true });
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("shows the server's own reason when it refuses, not a generic line", async () => {
    PUT.mockResolvedValue({
      data: undefined,
      error: { detail: "This organisation has published courses. Unpublish them first" },
      response: { status: 409 },
    });
    renderUi(<OrgCapabilities orgSlug="acme" sells delivers />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Sells courses/ }));
    fireEvent.click(save());
    expect((await screen.findByRole("alert")).textContent).toContain("Unpublish them first");
    expect(screen.queryByText("This could not be saved. Try again.")).toBeNull();
  });

  it("falls back to a plain line when the failure said nothing", async () => {
    PUT.mockResolvedValue({ data: undefined, error: {}, response: { status: 500 } });
    renderUi(<OrgCapabilities orgSlug="acme" sells delivers />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Delivers training/ }));
    fireEvent.click(save());
    expect(await screen.findByText("This could not be saved. Try again.")).toBeTruthy();
  });

  it("will not save an organisation that does neither", () => {
    renderUi(<OrgCapabilities orgSlug="acme" sells delivers={false} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Sells courses/ }));
    expect(save()).toHaveProperty("disabled", true);
    expect(PUT).not.toHaveBeenCalled();
  });
});
