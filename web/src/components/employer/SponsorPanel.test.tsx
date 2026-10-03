import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CandidateShortlist } from "@/components/employer/CandidateShortlist";
import { SponsorPanel } from "@/components/employer/SponsorPanel";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
// The real `@/lib/org` for `useOrgCandidates`, with only the harness's
// `world`-driven pieces swapped in (the pattern `EmployerWorkspace.test` uses).
vi.mock("@/lib/org", async () => ({
  ...(await vi.importActual<typeof import("@/lib/org")>("@/lib/org")),
  ...(await import("@/test/harness")).orgMock,
}));
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
const POST = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const TRAINING = {
  reference: "C-14B0AAA8",
  standard: {
    skill_id: "s1",
    nos_code: "HSS/N5127",
    name: "Provide ancillary services for supporting patient care",
    importance: 5,
    is_mandatory: true,
    nsqf_level: 4,
  },
  courses: [
    {
      slug: "patient-care-basics",
      title: "Patient Care Basics",
      mode: "offline",
      duration_hours: 40,
      fee_inr: null,
      closes: ["HSS/N5127"],
      closes_count: 1,
      gap_size: 1,
      covers_mandatory: 1,
    },
  ],
  offered: false,
};

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
  GET.mockResolvedValue(ok(TRAINING));
  POST.mockResolvedValue({ data: { offered: true }, error: undefined, response: { status: 201 } });
});

const panel = () => <SponsorPanel orgSlug="apollo" jobSlug="gda-chennai" reference="C-14B0AAA8" />;
const openIt = async () =>
  fireEvent.click(await screen.findByRole("button", { name: "Train and hire" }));

/**
 * The employer may prompt a candidate and may not learn who they are first
 * (ADR-048, ADR-037). The panel's wording is part of that: it must never claim
 * the candidate was notified, because an opted-out or capped candidate is not,
 * and the difference is a fact about them.
 */
describe("SponsorPanel", () => {
  it("fetches nothing until it is opened", () => {
    renderUi(panel());
    expect(GET).not.toHaveBeenCalled();
  });

  it("shows the one missing standard and the courses that teach it", async () => {
    renderUi(panel());
    await openIt();

    expect(
      await screen.findByText("Provide ancillary services for supporting patient care"),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Patient Care Basics" }).getAttribute("href")).toBe(
      "/courses/patient-care-basics",
    );
    expect(GET.mock.calls[0][0]).toBe("/org/{org_slug}/candidates/{job_slug}/{reference}/training");
    expect(GET.mock.calls[0][1].params.path).toEqual({
      org_slug: "apollo",
      job_slug: "gda-chennai",
      reference: "C-14B0AAA8",
    });
  });

  it("records the offer, and says only that it was recorded", async () => {
    GET.mockResolvedValueOnce(ok(TRAINING)).mockResolvedValue(ok({ ...TRAINING, offered: true }));
    const { container } = renderUi(panel());
    await openIt();
    fireEvent.click(await screen.findByRole("button", { name: "Offer to sponsor this training" }));

    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText(/Offer recorded\. If they choose to apply/),
    ).toBeTruthy();
    // An opted-out candidate is not told, and that is a fact about them: the
    // panel must never imply the candidate was notified or has seen anything.
    expect(container.textContent).not.toMatch(/notified|has been told|was told|seen it/i);
  });

  it("offers nothing to sponsor when no course teaches the standard", async () => {
    GET.mockResolvedValue(ok({ ...TRAINING, courses: [] }));
    renderUi(panel());
    await openIt();

    expect(await screen.findByText(/nothing to sponsor/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Offer to sponsor this training" })).toBeNull();
  });

  it("shows an offer already made, with no second button", async () => {
    GET.mockResolvedValue(ok({ ...TRAINING, offered: true }));
    renderUi(panel());
    await openIt();

    expect(await screen.findByText("You have offered to sponsor this training.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Offer to sponsor this training" })).toBeNull();
  });

  it("shows the server's own reason when the offer is refused", async () => {
    POST.mockResolvedValue({
      data: undefined,
      error: { detail: "You have already made this offer" },
      response: { status: 409 },
    });
    renderUi(panel());
    await openIt();
    fireEvent.click(await screen.findByRole("button", { name: "Offer to sponsor this training" }));

    expect(await screen.findByText("You have already made this offer")).toBeTruthy();
  });

  it("says an expired session is expired", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderUi(panel());
    await openIt();

    expect(
      await screen.findByText("Your session has expired. Sign in again to continue."),
    ).toBeTruthy();
  });
});

describe("CandidateShortlist -- who is offered training", () => {
  const card = (reference: string, missing_mandatory: number) => ({
    reference,
    headline: `Candidate ${reference}`,
    location_state: "Tamil Nadu",
    location_district: "Chennai",
    years_experience: 2,
    score: 70,
    coverage: 0.7,
    matched: [],
    missing: [],
    missing_mandatory,
    capped_by_mandatory: missing_mandatory > 0,
  });

  it("offers it to a candidate exactly one standard short, and to nobody else", async () => {
    GET.mockResolvedValue(
      ok({
        job: { slug: "gda-chennai", title: "General Duty Assistant" },
        items: [card("C-READY000", 0), card("C-NEAR0000", 1), card("C-FAR00000", 2)],
        total: 3,
      }),
    );
    renderUi(<CandidateShortlist orgSlug="apollo" jobSlug="gda-chennai" />);

    await screen.findByText("Candidate C-NEAR0000");
    expect(screen.getAllByRole("button", { name: "Train and hire" })).toHaveLength(1);
  });
});
