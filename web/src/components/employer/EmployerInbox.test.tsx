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
const PUT = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    PATCH: (...a: unknown[]) => PATCH(...a),
    PUT: (...a: unknown[]) => PUT(...a),
  },
}));
const saveCsv = vi.fn();
vi.mock("@/lib/download", () => ({ saveCsv: (...a: unknown[]) => saveCsv(...a) }));

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
  PUT.mockReset();
  saveCsv.mockReset();
  PATCH.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
  PUT.mockResolvedValue({ data: {}, error: undefined, response: { status: 200 } });
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

describe("EmployerInbox -- a message with a status, a private note, and the spreadsheet (Sprint 60)", () => {
  it("sends the message with the status button that is pressed, then empties the field", async () => {
    answer([applicant()]);
    renderUi(inbox());
    fireEvent.change(await screen.findByLabelText(/Message for this person/), {
      target: { value: "  Interview Tuesday 11 am, Kothrud clinic.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Shortlist" }));
    await waitFor(() => expect(PATCH).toHaveBeenCalledTimes(1));
    expect(PATCH.mock.calls[0][1].body).toEqual({
      status: "shortlisted",
      message: "Interview Tuesday 11 am, Kothrud clinic.",
    });
    await waitFor(() =>
      expect((screen.getByLabelText(/Message for this person/) as HTMLTextAreaElement).value).toBe(""),
    );
  });

  it("sends no message at all when nothing was typed", async () => {
    answer([applicant()]);
    renderUi(inbox());
    fireEvent.click(await screen.findByRole("button", { name: "Not suitable" }));
    await waitFor(() => expect(PATCH).toHaveBeenCalled());
    expect(PATCH.mock.calls[0][1].body).toEqual({ status: "rejected", message: undefined });
  });

  it("shows what you last told them, and does not offer a message to a withdrawn applicant", async () => {
    answer([
      applicant({
        status: "shortlisted",
        status_message: "Bring your ID.",
        status_message_at: "2026-10-10T08:00:00Z",
      }),
      applicant({ application_id: "a2", status: "withdrawn", contact: null }),
    ]);
    renderUi(inbox());
    expect(await screen.findByText("Bring your ID.")).toBeTruthy();
    expect(screen.getAllByLabelText(/Message for this person/)).toHaveLength(1);
  });

  it("saves a note only once it has changed, and says what the server said when it cannot", async () => {
    answer([applicant({ notes: "Strong." })]);
    renderUi(inbox());
    const field = (await screen.findByLabelText("Your private note")) as HTMLTextAreaElement;
    const save = screen.getByRole("button", { name: "Save note" }) as HTMLButtonElement;
    expect(field.value).toBe("Strong.");
    expect(save.disabled).toBe(true);

    fireEvent.change(field, { target: { value: "Strong. Call back." } });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => expect(PUT).toHaveBeenCalledTimes(1));
    expect(PUT.mock.calls[0][1].body).toEqual({ notes: "Strong. Call back." });

    PUT.mockResolvedValue({
      data: undefined,
      error: { detail: "Too long." },
      response: { status: 422 },
    });
    fireEvent.change(field, { target: { value: "x" } });
    fireEvent.click(save);
    expect(await screen.findByText("Too long.")).toBeTruthy();
  });

  it("downloads the spreadsheet the server built, and says so when it cannot", async () => {
    answer([applicant()]);
    renderUi(inbox());
    const button = await screen.findByRole("button", { name: "Download as spreadsheet" });
    GET.mockResolvedValue({ data: "reference,name\r\nC-1,A\r\n", error: undefined, response: { status: 200 } });
    fireEvent.click(button);
    await waitFor(() => expect(saveCsv).toHaveBeenCalledWith("applicants-gda-chennai.csv", expect.stringContaining("reference")));
    expect(GET.mock.calls.at(-1)?.[1].parseAs).toBe("text");

    GET.mockResolvedValue({ data: undefined, error: { detail: "Nope" }, response: { status: 500 } });
    fireEvent.click(button);
    expect(await screen.findByText("Nope")).toBeTruthy();
  });

  it("offers no spreadsheet for an empty inbox", async () => {
    answer([]);
    renderUi(inbox());
    await screen.findByText(/empty|No one/i).catch(() => undefined);
    expect(screen.queryByRole("button", { name: "Download as spreadsheet" })).toBeNull();
  });
});


/** Sprint 88, BL-19.18: an applicant's state is a word with a shape, and the score has one too. */
describe("EmployerInbox -- the look of an applicant's state", () => {
  it("marks a new application with a shape, in the good tone", async () => {
    answer([applicant()]);
    renderUi(<EmployerInbox org="acme" jobSlug="gda-chennai" />);
    const chip = (await screen.findByText("New", { selector: "span" })) as HTMLElement;
    expect(chip.className).toContain("bg-success-surface");
    expect(chip.querySelector("svg")).toBeTruthy();
  });

  it.each([
    ["shortlisted", "Shortlisted", "bg-success-surface"],
    ["rejected", "Not suitable", "bg-surface-muted"],
    ["hired", "Hired", "bg-success-surface"],
  ])("draws %s as %s on %s, with the same shape the candidate sees", async (status, word, token) => {
    answer([applicant({ status })]);
    renderUi(<EmployerInbox org="acme" jobSlug="gda-chennai" />);
    const chip = (await screen.findByText(word, { selector: "span" })) as HTMLElement;
    expect(chip.className).toContain(token);
    expect(chip.querySelector("svg")).toBeTruthy();
  });

  it("gives the score a shape, and a rejection a different one from a shortlisting", async () => {
    answer([applicant({ status: "shortlisted" }), applicant({ application_id: "a2", status: "rejected" })]);
    const { container } = renderUi(<EmployerInbox org="acme" jobSlug="gda-chennai" />);
    const short = (await screen.findByText("Shortlisted", { selector: "span" })) as HTMLElement;
    const rejected = screen.getByText("Not suitable", { selector: "span" }) as HTMLElement;
    expect(short.querySelector("svg")!.innerHTML).not.toBe(rejected.querySelector("svg")!.innerHTML);
    const scores = screen.getAllByText("88% match", { selector: "span" }) as HTMLElement[];
    expect(scores.length).toBe(2);
    for (const s of scores) expect(s.querySelector("svg")).toBeTruthy();
    expect(container.querySelectorAll("ul > li").length).toBeGreaterThanOrEqual(2);
  });

  it("gives the score a shape of its own, not the one the New chip has", async () => {
    answer([applicant()]);
    renderUi(<EmployerInbox org="acme" jobSlug="gda-chennai" />);
    const fresh = (await screen.findByText("New", { selector: "span" })) as HTMLElement;
    const score = screen.getByText("88% match", { selector: "span" }) as HTMLElement;
    expect(score.querySelector("svg")!.innerHTML).not.toBe(fresh.querySelector("svg")!.innerHTML);
  });
});
