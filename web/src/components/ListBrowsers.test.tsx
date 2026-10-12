import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseBrowser } from "@/components/CourseBrowser";
import { JobBrowser } from "@/components/JobBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

/**
 * Sprint 54. While the list is on its way a browser must say so (`data-loading` is what hides the
 * footer, see `skeleton.test.tsx`) and must not claim there are no results: "0 results" for a
 * moment, then forty, is both a lie and a layout shift.
 */
describe("the public lists while they load", () => {
  beforeEach(() => {
    resetWorld();
    GET.mockReset();
    GET.mockReturnValue(new Promise(() => undefined)); // never answers
  });

  for (const [name, Browser] of [
    ["vacancies", JobBrowser],
    ["courses", CourseBrowser],
  ] as const) {
    it(`${name}: shows placeholders and no result count`, () => {
      const { container } = renderUi(<Browser />);
      expect(container.querySelectorAll("[data-loading]").length).toBeGreaterThan(1);
      // "No jobs" for a moment, then forty, is a lie and a layout shift.
      expect(screen.queryByText(/^No (jobs|courses)$/)).toBeNull();
      expect(screen.queryByText(/matched/i)).toBeNull();
    });
  }

  it("vacancies: the placeholders go away, and the count appears, once the list has arrived", async () => {
    GET.mockResolvedValue({ data: { items: [] } });
    const { container } = renderUi(<JobBrowser />);
    expect(await screen.findByText("No jobs")).toBeTruthy();
    expect(container.querySelectorAll("[data-loading]")).toHaveLength(0);
  });
});
