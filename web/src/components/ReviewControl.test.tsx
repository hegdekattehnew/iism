import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewControl } from "@/components/ReviewControl";
import { ApiError } from "@/lib/http";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

beforeEach(resetWorld);

const submitButton = () => screen.getByRole("button", { name: /Submit rating/ }) as HTMLButtonElement;

function setup(submit = vi.fn().mockResolvedValue(undefined), onSaved = vi.fn()) {
  renderUi(<ReviewControl prompt="How was it?" submit={submit} onSaved={onSaved} />);
  return { submit, onSaved };
}

/**
 * The control a finished gig's two parties use to rate each other. The API
 * answers a second review with a 409, so what matters here is that it cannot
 * submit nothing, sends exactly what was chosen, and says why when refused.
 */
describe("ReviewControl", () => {
  it("cannot be submitted before a rating is chosen", () => {
    setup();
    expect(submitButton().disabled).toBe(true);
  });

  it("sends the chosen rating and a trimmed note", async () => {
    const { submit, onSaved } = setup();
    fireEvent.click(screen.getByLabelText("4 stars"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "  Paid on time  " } });
    expect(submitButton().disabled).toBe(false);
    fireEvent.click(submitButton());

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit.mock.calls[0][0]).toEqual({ rating: 4, comment: "Paid on time" });
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  });

  it("sends no note at all, rather than an empty one, when none was written", async () => {
    const { submit } = setup();
    fireEvent.click(screen.getByLabelText("1 star"));
    fireEvent.click(submitButton());

    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(submit.mock.calls[0][0]).toEqual({ rating: 1, comment: null });
  });

  it("shows the server's own reason, and does not report it saved", async () => {
    const { onSaved } = setup(
      vi.fn().mockRejectedValue(new ApiError(409, "This has already been reviewed")),
    );
    fireEvent.click(screen.getByLabelText("5 stars"));
    fireEvent.click(submitButton());

    expect(await screen.findByText("This has already been reviewed")).toBeTruthy();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("falls back to its own line when the failure carried nothing", async () => {
    setup(vi.fn().mockRejectedValue(new ApiError(500, null)));
    fireEvent.click(screen.getByLabelText("3 stars"));
    fireEvent.click(submitButton());

    expect(await screen.findByText(/That rating could not be saved/)).toBeTruthy();
  });
});
