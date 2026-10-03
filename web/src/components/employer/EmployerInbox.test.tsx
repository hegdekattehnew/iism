import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EmployerInbox } from "@/components/employer/EmployerInbox";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const PATCH = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), PATCH: (...a: unknown[]) => PATCH(...a) },
}));

/**
 * The one screen where a candidate's contact details appear, and the one that
 * had never been rendered by a test. Both defects this file guards are the
 * kind that compile: a message key asked for in the wrong namespace, and a
 * withdrawn applicant whose details stay on screen.
 */
const applicant = (over: Record<string, unknown> = {}) => ({
  application_id: "a1",
  status: "applied",
  applied_at: "2026-09-17T04:53:36Z",
  message: null,
  candidate: {
    reference: "C-14B0AAA8",
    headline: "General Duty Assistant with ward experience",
    location_state: "Tamil Nadu",
    location_district: "Chennai",
    years_experience: 3,
    score: 88,
    coverage: 0.86,
    matched: [],
    missing: [],
    missing_mandatory: 0,
    capped_by_mandatory: false,
  },
  contact: { full_name: "Ward-ready GDA", phone: "+919000000001", email: null },
  ...over,
});

function answer(items: ReturnType<typeof applicant>[], employmentType = "full_time") {
  GET.mockResolvedValue({
    data: {
      job: {
        slug: "gda-chennai",
        title: "General Duty Assistant",
        employment_type: employmentType,
      },
      total: items.length,
      items,
    },
    error: undefined,
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  PATCH.mockReset();
  PATCH.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
});

const inbox = () => <EmployerInbox org="apollo-care-hospitals" jobSlug="gda-chennai" />;

describe("EmployerInbox", () => {
  it("renders the score as a label, not as the key it asked for", async () => {
    // `employerConsole.matchScore` did not exist -- the key lived in
    // `matchesPage` -- so this badge read "employerConsole.matchScore" on the
    // employer's own screen. The harness throws on a missing key now, so this
    // test fails at render rather than on the assertion.
    answer([applicant()]);
    renderUi(inbox());
    expect(await screen.findByText("88% match")).toBeTruthy();
  });

  it("shows the contact details of someone who applied", async () => {
    answer([applicant()]);
    renderUi(inbox());
    expect(await screen.findByText("Ward-ready GDA")).toBeTruthy();
    expect(screen.getByText(/\+919000000001/)).toBeTruthy();
  });

  it("shows nothing identifying about someone who withdrew", async () => {
    // The API sends no contact for a withdrawn application; the interface must
    // not name them from anything else it holds either.
    answer([applicant({ status: "withdrawn", contact: null })]);
    const { container } = renderUi(inbox());
    await waitFor(() => expect(screen.getByText("C-14B0AAA8")).toBeTruthy());
    expect(container.textContent).not.toContain("+919000000001");
    expect(container.textContent).not.toContain("Ward-ready GDA");
    // ...and cannot be moved along, which would put the details back on screen.
    expect(screen.queryByRole("button", { name: /Shortlist/i })).toBeNull();
  });

  it("says the inbox is empty rather than rendering an empty list", async () => {
    answer([]);
    renderUi(inbox());
    expect(await screen.findByText(/Nobody has applied yet/i)).toBeTruthy();
  });

  void world;
});

describe("EmployerInbox -- a gig's outcome", () => {
  // `completed` and `no_show` were reachable through the API from Sprint 37 and
  // from no screen at all, so a gig could be posted and hired for and never
  // finished.
  it("offers completed and did-not-attend for a hired worker on a gig", async () => {
    answer([applicant({ status: "hired" })], "gig");
    renderUi(inbox());

    expect(await screen.findByRole("button", { name: "Mark as completed" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Did not attend" })).toBeTruthy();
  });

  it("does not offer them on a permanent vacancy", async () => {
    // The server would refuse with a 422; the screen should not ask.
    answer([applicant({ status: "hired" })], "full_time");
    renderUi(inbox());

    await screen.findByText("Ward-ready GDA");
    expect(screen.queryByRole("button", { name: "Mark as completed" })).toBeNull();
  });

  it("does not offer them before the worker is hired", async () => {
    answer([applicant({ status: "shortlisted" })], "gig");
    renderUi(inbox());

    await screen.findByText("Ward-ready GDA");
    expect(screen.queryByRole("button", { name: "Mark as completed" })).toBeNull();
  });

  it("sends completed, and nothing else, when the button is pressed", async () => {
    answer([applicant({ status: "hired" })], "gig");
    renderUi(inbox());
    fireEvent.click(await screen.findByRole("button", { name: "Mark as completed" }));

    await waitFor(() => expect(PATCH).toHaveBeenCalledTimes(1));
    expect(PATCH.mock.calls[0][1].body).toEqual({ status: "completed" });
  });

  it("shows a finished engagement as final, with no way to move it", async () => {
    answer([applicant({ status: "completed" })], "gig");
    renderUi(inbox());

    expect(await screen.findByText(/This engagement has ended/)).toBeTruthy();
    expect(screen.getByText("Completed")).toBeTruthy();
    for (const name of [/Shortlist/, /Not suitable/, /Mark as hired/, /Mark as completed/]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });
});

describe("EmployerInbox -- rating the worker", () => {
  it("asks for a rating once a gig is completed and not yet rated", async () => {
    answer([applicant({ status: "completed", reviewed: false })], "gig");
    renderUi(inbox());

    expect(await screen.findByText("How was working with this person?")).toBeTruthy();
  });

  it("says it was rated, and offers no second form, once it has been", async () => {
    // The API answers a second review with a 409, so a form that stays on
    // screen is a form that fails on the next press.
    answer([applicant({ status: "completed", reviewed: true })], "gig");
    renderUi(inbox());

    expect(await screen.findByText("You rated this worker.")).toBeTruthy();
    expect(screen.queryByText("How was working with this person?")).toBeNull();
  });

  it("offers no rating for a no-show: there was no work to rate", async () => {
    answer([applicant({ status: "no_show" })], "gig");
    renderUi(inbox());

    await screen.findByText("Ward-ready GDA");
    expect(screen.queryByText("How was working with this person?")).toBeNull();
  });

  it("offers no rating before the gig is completed", async () => {
    answer([applicant({ status: "hired" })], "gig");
    renderUi(inbox());

    await screen.findByText("Ward-ready GDA");
    expect(screen.queryByText("How was working with this person?")).toBeNull();
  });
});

describe("EmployerInbox -- one failed save", () => {
  it("names the server's reason, on the row that failed and no other", async () => {
    // A single `setStatus.isError` was rendered inside the `.map`, so one
    // refusal showed its alert on every card and disabled every button.
    answer([
      applicant({ application_id: "a1" }),
      applicant({ application_id: "a2", contact: { full_name: "Second Person", phone: "+919000000002", email: null } }),
    ]);
    PATCH.mockResolvedValue({
      data: undefined,
      error: { detail: "This application has been withdrawn by the candidate" },
      response: { status: 409 },
    });
    renderUi(inbox());

    const hire = await screen.findAllByRole("button", { name: "Mark as hired" });
    fireEvent.click(hire[0]);

    expect(
      await screen.findByText("This application has been withdrawn by the candidate"),
    ).toBeTruthy();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});
