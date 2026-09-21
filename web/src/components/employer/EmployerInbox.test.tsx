import { screen, waitFor } from "@testing-library/react";
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
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a), PATCH: vi.fn() } }));

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

function answer(items: ReturnType<typeof applicant>[]) {
  GET.mockResolvedValue({
    data: {
      job: { slug: "gda-chennai", title: "General Duty Assistant" },
      total: items.length,
      items,
    },
    error: undefined,
  });
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
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
