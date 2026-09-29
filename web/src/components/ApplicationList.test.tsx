import { screen } from "@testing-library/react";
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
vi.mock("@/lib/api", () => ({
  api: {
    GET: (...a: unknown[]) => GET(...a),
    POST: vi.fn(),
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
