import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OperatorDashboard } from "@/components/ops/OperatorDashboard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

beforeEach(() => {
  resetWorld();
  GET.mockReset();
});

describe("OperatorDashboard", () => {
  it("renders the queue counts and platform totals together", async () => {
    GET.mockResolvedValue({
      data: {
        unverified_organisations: 3,
        unverified_certifications: 5,
        organisations: 40,
        candidates: 400,
        published_jobs: 20,
        published_courses: 50,
      },
      error: undefined,
      response: { status: 200 },
    });
    renderUi(<OperatorDashboard />);
    expect(await screen.findByText("3")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy();
    expect(screen.getByText("40")).toBeTruthy();
    expect(screen.getByText("400")).toBeTruthy();
  });

  it("shows the failure message rather than nothing, since operators have no other screen to fall back on", async () => {
    GET.mockResolvedValue({
      data: undefined,
      error: { detail: "server error" },
      response: { status: 500 },
    });
    renderUi(<OperatorDashboard />);
    expect(await screen.findByText("The dashboard could not be loaded.")).toBeTruthy();
  });
});
