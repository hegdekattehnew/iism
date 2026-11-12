import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchPage } from "@/components/BatchPage";
import { publicBatch } from "@/test/batch-fixtures";
import { personal, renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() } }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  world.memberships = [personal()];
});

/** Sprint 101: where a notice, a bookmark or a shared link lands. */
describe("BatchPage", () => {
  it("asks for the batch by its id and shows it, with the register control and no link to itself", async () => {
    GET.mockResolvedValue({ data: publicBatch({ id: "b42" }), error: undefined });
    renderUi(<BatchPage id="b42" />);
    expect(await screen.findByText("Delivered by Partner Skills at Hadapsar Centre")).toBeTruthy();
    expect(GET.mock.calls[0][0]).toBe("/batches/{batch_id}");
    expect((GET.mock.calls[0][1] as { params: { path: { batch_id: string } } }).params.path.batch_id).toBe("b42");
    expect(await screen.findByRole("button", { name: /Register interest/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Batch details" })).toBeNull();
    expect(screen.getByRole("link", { name: "All batches" }).getAttribute("href")).toBe("/batches");
  });

  it("says a missing batch is not available and gives a way back, never a blank page", async () => {
    GET.mockResolvedValue({ data: undefined, error: {}, response: { status: 404 } });
    renderUi(<BatchPage id="gone" />);
    expect(await screen.findByText("This batch is not available")).toBeTruthy();
    expect(screen.getByRole("link", { name: "See open batches" }).getAttribute("href")).toBe("/batches");
    expect(screen.queryByRole("button", { name: /Register/ })).toBeNull();
  });

  it("holds the card's room while it loads", () => {
    GET.mockReturnValue(new Promise(() => undefined));
    const { container } = renderUi(<BatchPage id="b1" />);
    const place = container.querySelector("[data-loading]");
    expect(place).toBeTruthy();
    expect(place?.className).toContain("h-72");
  });

  it("shows a cancelled batch as cancelled, with nothing to press", async () => {
    GET.mockResolvedValue({
      data: publicBatch({ phase: "cancelled", cancel_reason: "by_organisation" }),
      error: undefined,
    });
    renderUi(<BatchPage id="b1" />);
    expect(await screen.findByText("This batch was cancelled.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Register/ })).toBeNull();
  });

  it("asks a visitor to sign in rather than showing a button that would fail", async () => {
    world.signedIn = false;
    GET.mockResolvedValue({ data: publicBatch(), error: undefined });
    renderUi(<BatchPage id="b1" />);
    expect(
      (await screen.findByRole("link", { name: "Sign in to register interest" })).getAttribute("href"),
    ).toBe("/signin");
  });
});
