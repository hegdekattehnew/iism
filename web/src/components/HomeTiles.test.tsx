import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BrowsePanels } from "@/components/BrowsePanels";
import { HowItWorks } from "@/components/HowItWorks";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
// A server component asks the request for its translator; the test hands it the key it was asked for.
vi.mock("next-intl/server", () => ({
  getTranslations: async (ns: string) => (key: string) => `${ns}.${key}`,
}));
vi.mock("@/components/LiveCount", () => ({
  LiveCount: ({ kind }: { kind: string }) => <span data-testid={`count-${kind}`} />,
}));

beforeEach(resetWorld);

/** Sprint 85, BL-19.15: the home's two blocks lead each tile with an icon. */
describe("the browse panels", () => {
  it("are three tiles, each led by an icon in a tile that a screen reader skips", async () => {
    renderUi(await BrowsePanels());
    const headings = screen.getAllByRole("heading", { level: 3 });
    expect(headings.map((h) => h.textContent)).toEqual(["browse.jobsTitle", "browse.coursesTitle", "browse.skillsTitle"]);
    for (const h of headings) {
      const row = h.parentElement as HTMLElement;
      const tile = row.querySelector("[aria-hidden='true']") as HTMLElement;
      expect(tile, h.textContent ?? "").toBeTruthy();
      expect(tile.querySelector("svg")).toBeTruthy();
    }
  });

  it("each draws its own icon, so the three read apart before a word is read", async () => {
    const { container } = renderUi(await BrowsePanels());
    const shapes = [...container.querySelectorAll("h3")].map(
      (h) => h.parentElement!.querySelector("svg")!.innerHTML,
    );
    expect(shapes.length).toBe(3);
    expect(new Set(shapes).size).toBe(3);
  });

  it("still link to their lists and still carry their live count", async () => {
    renderUi(await BrowsePanels());
    const links = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/jobs", "/courses", "/skills"]);
    for (const kind of ["jobs", "courses", "skills"]) expect(screen.getByTestId(`count-${kind}`)).toBeTruthy();
  });
});

describe("how it works", () => {
  it("is four steps in order, each led by its own icon", async () => {
    const { container } = renderUi(await HowItWorks());
    const steps = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(steps.length).toBe(4);
    const shapes = steps.map((li) => li.querySelector("svg")!.innerHTML);
    expect(new Set(shapes).size).toBe(4);
    expect(container.querySelectorAll("ol > li").length).toBe(4);
  });

  it("keeps the number visible beside the title, and hidden from a screen reader (the list says the order)", async () => {
    renderUi(await HowItWorks());
    const steps = within(screen.getByRole("list")).getAllByRole("listitem");
    steps.forEach((li, i) => {
      const number = within(li).getByText(String(i + 1));
      expect(number.getAttribute("aria-hidden")).toBe("true");
      expect(within(li).getByRole("heading", { level: 3 }).textContent).toBe(`how.step${i + 1}Title`);
      expect(within(li).getByText(`how.step${i + 1}Body`)).toBeTruthy();
    });
  });
});
