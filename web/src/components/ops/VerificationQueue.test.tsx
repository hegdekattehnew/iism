import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VerificationQueue } from "@/components/ops/VerificationQueue";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: vi.fn() },
}));

const ROW = {
  slug: "apollo-care-hospitals",
  name: "Apollo Care Hospitals",
  tenant_type: "employer",
  city: "Chennai",
  website: "https://apollo-care.example",
  created_at: "2026-09-02T08:38:17Z",
  jobs: 5,
  courses: 0,
  members: 3,
};

function answer(rows: unknown[] | null) {
  GET.mockImplementation(async () =>
    rows === null
      ? { data: undefined, error: {}, response: { status: 500 } }
      : { data: rows, error: null, response: { status: 200 } },
  );
}

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  answer([ROW]);
});

describe("the verification queue", () => {
  it("says the queue is answered rather than rendering an empty list", async () => {
    // An empty list and a finished queue look identical without this, and the
    // second is the one worth telling somebody about.
    answer([]);
    renderUi(<VerificationQueue />);
    expect(
      await screen.findByText(/Every organisation has been decided on/),
    ).toBeTruthy();
  });

  it("links each organisation to its own review page", async () => {
    renderUi(<VerificationQueue />);
    const link = await screen.findByRole("link", { name: "Apollo Care Hospitals" });
    expect(link.getAttribute("href")).toBe("/admin/apollo-care-hospitals");
  });

  it("shows what the organisation has actually done here", async () => {
    // Verifying an employer with no vacancies and no members is verifying an
    // intention, so the counts are on the row rather than a click away.
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/5 vacancies · 0 courses · 3 members/)).toBeTruthy();
  });

  it("says so when a field the operator would look for is missing", async () => {
    answer([{ ...ROW, city: null, website: null }]);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/No city given/)).toBeTruthy();
    expect(screen.getByText("No website given")).toBeTruthy();
  });

  it("reports a failure instead of showing an empty queue", async () => {
    // "Nothing is waiting" is the most misleading thing this screen could say
    // when the truth is that it could not ask.
    answer(null);
    renderUi(<VerificationQueue />);
    expect(await screen.findByText(/queue could not be loaded/)).toBeTruthy();
  });
});
