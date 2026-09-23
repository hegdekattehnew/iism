import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OperatorOnly } from "@/components/ops/OperatorOnly";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

// The real `notFound()` throws -- that is how it interrupts a render. A mock
// that merely records the call would let the children render on afterwards,
// and the test would then be asserting something production never does.
class NotFound extends Error {}
const notFound = vi.fn(() => {
  throw new NotFound();
});
vi.mock("next/navigation", () => ({ notFound: () => notFound() }));

/**
 * The back office's front door, and the three answers it has to keep apart.
 *
 * 404 for a signed-in non-operator, a sign-in prompt for somebody signed out,
 * and nothing at all while the answer is still in flight. The third is the one
 * that rots: it is invisible on a fast connection and 404s every operator on a
 * slow one.
 *
 * Asserted on the **mock**, never on "nothing rendered" -- that also passes
 * while loading, which is precisely the case being distinguished.
 */

beforeEach(() => {
  resetWorld();
  notFound.mockReset();
});

describe("OperatorOnly", () => {
  it("shows the back office to an operator", async () => {
    world.isStaff = true;
    renderUi(
      <OperatorOnly>
        <p>the queue</p>
      </OperatorOnly>,
    );
    expect(await screen.findByText("the queue")).toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  });

  it("answers a signed-in stranger with not-found, not no-access", async () => {
    // A 403-shaped page would tell them they had found the back office and
    // that one flag on their row was all that stood in the way (ADR-042).
    world.isStaff = false;
    expect(() =>
      renderUi(
        <OperatorOnly>
          <p>the queue</p>
        </OperatorOnly>,
      ),
    ).toThrow(NotFound);
    expect(notFound).toHaveBeenCalled();
  });

  it("asks somebody signed out to sign in, and does not 404 them", async () => {
    // Not a permission problem: they are not anybody yet. Rendering not-found
    // would send somebody who only needs to sign in away for good.
    world.signedIn = false;
    world.memberships = [];
    renderUi(
      <OperatorOnly>
        <p>the queue</p>
      </OperatorOnly>,
    );
    expect(await screen.findByText("Sign in to continue")).toBeTruthy();
    expect(notFound).not.toHaveBeenCalled();
  });

  it("renders nothing at all while the answer is in flight", () => {
    // Three things must be true at once, and only the third fails when the
    // loading branch is removed: nothing is 404'd, nothing is shown, and
    // **a signed-in operator is not told to sign in**. Without the last
    // assertion this test passes against a component that flashes the
    // signed-out prompt at every operator on a slow connection.
    world.pending = true;
    world.isStaff = true;
    renderUi(
      <OperatorOnly>
        <p>the queue</p>
      </OperatorOnly>,
    );
    expect(notFound).not.toHaveBeenCalled();
    expect(screen.queryByText("the queue")).toBeNull();
    expect(screen.queryByText("Sign in to continue")).toBeNull();
  });
});
