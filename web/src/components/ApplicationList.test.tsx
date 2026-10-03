import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationList } from "@/components/ApplicationList";
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
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: (...a: unknown[]) => POST(...a),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

/**
 * A gig's two outcomes, `completed` and `no_show`, shipped in the API a sprint
 * before this screen knew them. `renderUi` throws on a missing message key, so
 * rendering each status is the guard against it showing a raw key again.
 */

const application = (status: string, id = status) => ({
  id,
  status,
  message: null,
  applied_at: "2026-09-28T07:24:06Z",
  updated_at: "2026-09-28T07:24:06Z",
  job: {
    slug: `shift-${id}`,
    title: `Weekend shift ${id}`,
    location_state: "Tamil Nadu",
    location_district: "Chennai",
    employment_type: "gig",
    tenant: { id: "t1", slug: "acme", name: "Acme", tenant_type: "employer" },
  },
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  POST.mockReset();
});

const GAP = {
  application_id: "rejected",
  job: { slug: "shift-rejected", title: "Weekend shift rejected" },
  status: "rejected",
  score: 38,
  coverage: 0.4,
  missing: [
    {
      skill_id: "s1",
      nos_code: "HSS/N5127",
      name: "Provide ancillary services for supporting patient care",
      importance: 5,
      is_mandatory: true,
      nsqf_level: 4,
    },
    { skill_id: "s2", nos_code: null, name: "Working effectively in a team", importance: 2, is_mandatory: false },
  ],
  missing_mandatory: 1,
  level_shortfall: null,
  capped_by_mandatory: true,
  courses: [
    {
      slug: "patient-care-basics",
      title: "Patient Care Basics",
      mode: "offline",
      duration_hours: 40,
      fee_inr: null,
      closes: ["HSS/N5127"],
      closes_count: 2,
      gap_size: 2,
      covers_mandatory: 1,
    },
  ],
};

/** The list and the gap come from different routes on one mocked client. */
function answer(
  list: unknown[],
  gap: unknown = { data: GAP, error: undefined, response: { status: 200 } },
) {
  GET.mockImplementation(async (path: string) =>
    path === "/me/applications" ? { data: list, error: undefined } : gap,
  );
}

describe("ApplicationList -- why not me", () => {
  it("offers it on a rejection and on nothing else", async () => {
    answer([
      application("rejected"),
      application("applied"),
      application("hired"),
      application("withdrawn"),
    ]);
    renderUi(<ApplicationList />);

    await screen.findByText("Weekend shift rejected");
    expect(screen.getAllByRole("button", { name: "See what you were missing" })).toHaveLength(1);
  });

  it("fetches nothing until it is opened", async () => {
    // Most people open none, so the gap is not requested with the list.
    answer([application("rejected")]);
    renderUi(<ApplicationList />);

    await screen.findByText("Weekend shift rejected");
    expect(GET).toHaveBeenCalledTimes(1);
    expect(GET.mock.calls[0][0]).toBe("/me/applications");
  });

  it("shows what was missing, mandatory first, and the courses that close it", async () => {
    answer([application("rejected")]);
    renderUi(<ApplicationList />);
    fireEvent.click(await screen.findByRole("button", { name: "See what you were missing" }));

    expect(
      await screen.findByText("Provide ancillary services for supporting patient care"),
    ).toBeTruthy();
    expect(screen.getByText("HSS/N5127")).toBeTruthy();
    expect(screen.getByText("Working effectively in a team")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Patient Care Basics" }).getAttribute("href")).toBe(
      "/courses/patient-care-basics",
    );
    const gapCall = GET.mock.calls.find((c) => c[0] === "/me/applications/{application_id}/gap");
    expect(gapCall?.[1].params.path.application_id).toBe("rejected");
  });

  it("does not report a course click as a recommendation", async () => {
    // `course_opened` pairs with `course_recommended`, which this list never
    // recorded: counting these clicks would inflate ADR-025's click-through.
    answer([application("rejected")]);
    renderUi(<ApplicationList />);
    fireEvent.click(await screen.findByRole("button", { name: "See what you were missing" }));
    fireEvent.click(await screen.findByRole("link", { name: "Patient Care Basics" }));

    expect(POST).not.toHaveBeenCalled();
  });

  it("says plainly when nothing is missing any more", async () => {
    answer([application("rejected")], {
      data: { ...GAP, missing: [], courses: [], missing_mandatory: 0, capped_by_mandatory: false, coverage: 1 },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<ApplicationList />);
    fireEvent.click(await screen.findByRole("button", { name: "See what you were missing" }));

    expect(await screen.findByText(/Nothing is missing now/)).toBeTruthy();
    expect(screen.queryByText("Courses that close this gap")).toBeNull();
  });

  it("closes again, and says an expired session is expired", async () => {
    answer([application("rejected")], {
      data: undefined,
      error: { detail: "Not authenticated" },
      response: { status: 401 },
    });
    renderUi(<ApplicationList />);
    const toggle = await screen.findByRole("button", { name: "See what you were missing" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toggle);

    expect(
      await screen.findByText("Your session has expired. Sign in again to continue."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByText("Your session has expired. Sign in again to continue.")).toBeNull();
  });
});

describe("ApplicationList -- rating the employer", () => {
  it("asks the worker to rate a completed gig they have not yet rated", async () => {
    GET.mockResolvedValue({
      data: [{ ...application("completed"), reviewed: false }],
      error: undefined,
    });
    renderUi(<ApplicationList />);

    expect(await screen.findByText("How was working for Acme?")).toBeTruthy();
  });

  it("says it was rated once it has been, with no second form", async () => {
    GET.mockResolvedValue({
      data: [{ ...application("completed"), reviewed: true }],
      error: undefined,
    });
    renderUi(<ApplicationList />);

    expect(await screen.findByText("You rated this employer.")).toBeTruthy();
    expect(screen.queryByText("How was working for Acme?")).toBeNull();
  });

  it("offers no rating for a hired or no-show engagement", async () => {
    GET.mockResolvedValue({
      data: [application("hired"), application("no_show")],
      error: undefined,
    });
    renderUi(<ApplicationList />);

    await screen.findByText("Did not attend");
    expect(screen.queryByText(/How was working for/)).toBeNull();
  });
});

describe("ApplicationList", () => {
  it("names a completed gig and a no-show in words, not keys", async () => {
    GET.mockResolvedValue({
      data: [application("completed"), application("no_show")],
      error: undefined,
    });
    renderUi(<ApplicationList />);
    expect(await screen.findByText("Completed")).toBeTruthy();
    expect(screen.getByText("Did not attend")).toBeTruthy();
    expect(screen.getByText("You finished this assignment.")).toBeTruthy();
  });
});
