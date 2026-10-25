import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BatchInterestList } from "@/components/BatchInterestList";
import { batchInterest, publicBatch } from "@/test/batch-fixtures";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

describe("BatchInterestList", () => {
  it("is absent for a learner who never looked at a batch", async () => {
    GET.mockResolvedValue({ data: [], error: undefined });
    const { container } = renderUi(<BatchInterestList />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent).toBe("");
  });

  it("is absent when the read fails: the interests list above it is the page", async () => {
    GET.mockResolvedValue({ data: undefined, error: {} });
    const { container } = renderUi(<BatchInterestList />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 30));
    expect(container.textContent).toBe("");
  });

  it("lists each interest with its state in words", async () => {
    GET.mockResolvedValue({
      data: [
        batchInterest({ id: "1", status: "registered" }),
        batchInterest({ id: "2", status: "enrolled" }),
        batchInterest({ id: "3", status: "withdrawn" }),
      ],
      error: undefined,
    });
    renderUi(<BatchInterestList />);
    expect(await screen.findByRole("heading", { name: "Batches you asked about" })).toBeTruthy();
    expect(screen.getByText("Registered", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Enrolled", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("Withdrawn", { selector: "span" })).toBeTruthy();
  });

  it("offers to withdraw only what can still be withdrawn", async () => {
    GET.mockResolvedValue({
      data: [
        batchInterest({ id: "1", status: "registered" }),
        batchInterest({ id: "2", status: "withdrawn" }),
        batchInterest({
          id: "3",
          status: "registered",
          batch: publicBatch({ phase: "cancelled", cancel_reason: "by_organisation" }),
        }),
      ],
      error: undefined,
    });
    renderUi(<BatchInterestList />);
    await screen.findByRole("heading", { name: "Batches you asked about" });
    expect(screen.getAllByRole("button", { name: /Withdraw:/ })).toHaveLength(1);
  });

  it("asks for the list again after a withdrawal, so the card changes under the learner's hand", async () => {
    GET.mockResolvedValue({ data: [batchInterest({ id: "9" })], error: undefined });
    POST.mockResolvedValue({
      data: { id: "9", status: "withdrawn" },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<BatchInterestList />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw: Welding basics" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    await waitFor(() => expect(GET.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("withdraws by the interest's id and shows the server's refusal if it comes", async () => {
    GET.mockResolvedValue({ data: [batchInterest({ id: "9" })], error: undefined });
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "That is not yours to withdraw" },
      response: { status: 404 },
    });
    renderUi(<BatchInterestList />);
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw: Welding basics" }));
    await waitFor(() => expect(POST).toHaveBeenCalled());
    expect(
      (POST.mock.calls[0][1] as { params: { path: { interest_id: string } } }).params.path.interest_id,
    ).toBe("9");
    expect((await screen.findByRole("alert")).textContent).toContain("That is not yours to withdraw");
  });
});
