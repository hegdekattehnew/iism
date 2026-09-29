import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrganisationReview } from "@/components/ops/OrganisationReview";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const UNVERIFIED = {
  slug: "apollo-care-hospitals",
  name: "Apollo Care Hospitals",
  is_verified: false,
  verified_at: null,
  verification_note: null,
  history: [],
};

const VERIFIED = {
  ...UNVERIFIED,
  is_verified: true,
  verified_at: "2026-09-23T10:00:00Z",
  verification_note: "Hospital registration and NABH accreditation confirmed.",
  history: [
    {
      id: "1",
      decision: "granted",
      note: "Hospital registration and NABH accreditation confirmed.",
      created_at: "2026-09-23T10:00:00Z",
      actor_name: "Priya",
    },
  ],
};

function detail(data: unknown, status = 200) {
  GET.mockImplementation(async () =>
    status === 200
      ? { data, error: null, response: { status } }
      : { data: undefined, error: {}, response: { status } },
  );
}

const NOTE = "Registration certificate checked against the state register.";

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  detail(UNVERIFIED);
  POST.mockImplementation(async () => ({
    data: VERIFIED,
    error: null,
    response: { status: 200 },
  }));
});

describe("recording a decision", () => {
  it("will not let a badge be granted without evidence", async () => {
    // The note is the only record of why a candidate should believe the badge,
    // so "ok" is not a reason. `min_length=10` on the server, mirrored here so
    // the browser says so before a request is made.
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    const grant = await screen.findByRole("button", { name: /Verify this organisation/ });
    expect(grant.hasAttribute("disabled")).toBe(true);

    fireEvent.change(screen.getByLabelText(/What you verified/), {
      target: { value: "too short" },
    });
    expect(grant.hasAttribute("disabled")).toBe(true);

    fireEvent.change(screen.getByLabelText(/What you verified/), {
      target: { value: NOTE },
    });
    expect(grant.hasAttribute("disabled")).toBe(false);
  });

  it("sends the decision and the note the operator wrote", async () => {
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    fireEvent.change(await screen.findByLabelText(/What you verified/), {
      target: { value: NOTE },
    });
    fireEvent.click(screen.getByRole("button", { name: /Verify this organisation/ }));

    await waitFor(() => expect(POST).toHaveBeenCalled());
    const [, options] = POST.mock.calls[0];
    expect(options.body).toEqual({ decision: "granted", note: NOTE });
  });

  it("offers withdrawal only once there is something to withdraw", async () => {
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    await screen.findByRole("button", { name: /Verify this organisation/ });
    expect(screen.queryByRole("button", { name: /Withdraw verification/ })).toBeNull();

    detail(VERIFIED);
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    expect(
      await screen.findByRole("button", { name: /Withdraw verification/ }),
    ).toBeTruthy();
  });

  it("shows what the server said, not a fixed sentence", async () => {
    // "Never throw away what the server said" -- it names the field and the
    // reason, and the generic line is the fallback for a failure that carried
    // nothing.
    POST.mockImplementation(async () => ({
      data: undefined,
      error: { detail: "String should have at least 10 characters" },
      response: { status: 422 },
    }));
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    fireEvent.change(await screen.findByLabelText(/What you verified/), {
      target: { value: NOTE },
    });
    fireEvent.click(screen.getByRole("button", { name: /Verify this organisation/ }));

    expect(
      await screen.findByText("String should have at least 10 characters"),
    ).toBeTruthy();
  });
});

describe("the history", () => {
  it("names every decision, its reason and who made it", async () => {
    detail(VERIFIED);
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    expect(await screen.findByText(/Priya/)).toBeTruthy();
    expect(
      screen.getAllByText(/NABH accreditation confirmed/).length,
    ).toBeGreaterThan(0);
  });

  it("says 'a former operator' rather than inventing a name", async () => {
    // `verified_by` is SET NULL, because an operator may exercise their own
    // erasure and the record about the organisation must survive them.
    detail({
      ...VERIFIED,
      history: [{ ...VERIFIED.history[0], actor_name: null }],
    });
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    expect(await screen.findByText(/a former operator/)).toBeTruthy();
  });

  it("tells an unknown address apart from a failure", async () => {
    // A 404 means the slug is not an organisation we can review -- a personal
    // workspace, or nothing. It is not an error state.
    detail(null, 404);
    renderUi(<OrganisationReview slug="nope" />);
    expect(await screen.findByText(/No organisation with that address/)).toBeTruthy();
  });
});
