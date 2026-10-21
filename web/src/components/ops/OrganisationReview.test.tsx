import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OrganisationReview } from "@/components/ops/OrganisationReview";
import { renderUi, resetWorld, world } from "@/test/harness";

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

/** Sprint 73: verifying is the admin tier's alone (OPS_ORG_VERIFY), so the control is not offered to support. */
describe("who may decide", () => {
  it("offers the note and both buttons to the admin tier", async () => {
    world.staffTier = "admin";
    detail(VERIFIED);
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    expect(await screen.findByRole("button", { name: "Verify this organisation" })).toBeTruthy();
    expect(screen.getByLabelText("What you verified")).toBeTruthy();
  });

  it("offers a support-tier operator no button that would answer 403, and says why", async () => {
    world.staffTier = "support";
    detail(VERIFIED);
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    expect(await screen.findByText(/Only an admin-tier operator can verify or revoke/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Verify this organisation" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Withdraw verification" })).toBeNull();
    expect(screen.queryByLabelText("What you verified")).toBeNull();
    // Reading is still theirs: the history and the badge are shown.
    expect(screen.getAllByText(/NABH accreditation confirmed/).length).toBeTruthy();
  });
});

/** Sprint 89, BL-19.19: whether an organisation is verified, and what each past decision was, are chips with shapes. */
describe("the organisation review -- the look of a verdict", () => {
  it("draws 'verified' in the good tone with a shield and 'not verified' neutral with a different shape", async () => {
    detail(VERIFIED);
    const first = renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    const yes = (await screen.findAllByText("Verified", { selector: "span" }))[0] as HTMLElement;
    expect(yes.className).toContain("bg-success-surface");
    const yesShape = yes.querySelector("svg")!.innerHTML;
    first.unmount();
    detail(UNVERIFIED);
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    const no = (await screen.findByText("Not verified", { selector: "span" })) as HTMLElement;
    expect(no.className).toContain("bg-surface-muted");
    expect(no.querySelector("svg")!.innerHTML).not.toBe(yesShape);
  });

  it("draws a granted decision and a withdrawn one with different shapes and tones", async () => {
    detail({
      ...VERIFIED,
      history: [
        ...VERIFIED.history,
        { id: "2", decision: "revoked", note: "Registration lapsed.", created_at: "2026-09-24T10:00:00Z", actor_name: "Priya" },
      ],
    });
    renderUi(<OrganisationReview slug="apollo-care-hospitals" />);
    const withdrawn = (await screen.findByText("Withdrawn", { selector: "span" })) as HTMLElement;
    expect(withdrawn.className).toContain("bg-warning-surface");
    const granted = screen.getAllByText("Verified", { selector: "span" }).find((s) => s.closest("li")) as HTMLElement;
    expect(granted.querySelector("svg")!.innerHTML).not.toBe(withdrawn.querySelector("svg")!.innerHTML);
  });
});
