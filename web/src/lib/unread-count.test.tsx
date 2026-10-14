import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderUi, resetWorld } from "@/test/harness";
import { useUnreadCount } from "@/lib/unread-count";

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

function Probe({ signedIn }: { signedIn: boolean }) {
  return <output data-testid="n">{useUnreadCount(signedIn)}</output>;
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  GET.mockResolvedValue({
    data: { unread: 4 },
    error: undefined,
    response: { status: 200 },
  });
});

describe("the header's unread count", () => {
  it("is asked for by somebody signed in, and is the server's number", async () => {
    renderUi(<Probe signedIn />);
    await waitFor(() => expect(screen.getByTestId("n").textContent).toBe("4"));
    expect(GET.mock.calls[0][0]).toBe("/me/notifications/unread-count");
  });

  it("makes no request at all for a signed-out visitor (a request that can only answer 401)", async () => {
    renderUi(<Probe signedIn={false} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(GET).not.toHaveBeenCalled();
    expect(screen.getByTestId("n").textContent).toBe("0");
  });

  it("reads as nothing, not as an error, when the server cannot say", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "down" },
      response: { status: 500 },
    });
    renderUi(<Probe signedIn />);
    await waitFor(() => expect(GET).toHaveBeenCalled());
    expect(screen.getByTestId("n").textContent).toBe("0");
  });
});
