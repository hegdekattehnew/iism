import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import AboutPage from "@/app/[locale]/about/page";
import EmployersPage from "@/app/[locale]/employers/page";
import NotFound from "@/app/[locale]/not-found";
import ProvidersPage from "@/app/[locale]/providers/page";
import { AudiencePage } from "@/components/AudiencePage";
import { LegalPage } from "@/components/LegalPage";
import { PlaceholderPage } from "@/components/PlaceholderPage";
import { BookOpenIcon } from "@/components/ui/icons";
import messages from "@/messages/en.json";

vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);
// The server's own translator, built from the English catalogue the pages read (it has `raw`, which the legal page needs).
vi.mock("next-intl/server", async () => {
  const intl = await import("next-intl");
  const en = (await import("@/messages/en.json")).default;
  return {
    getTranslations: async (ns: string) => intl.createTranslator({ locale: "en", messages: en, namespace: ns as never }),
    setRequestLocale: () => undefined,
  };
});
// Client bands the pages embed are other tests' business.
vi.mock("@/components/StatsBand", () => ({ StatsBand: () => <div data-testid="stats" /> }));
vi.mock("@/components/FrameworkBand", () => ({ FrameworkBand: () => <div data-testid="framework" /> }));

const show = async (page: Promise<React.ReactElement>) =>
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {await page}
    </NextIntlClientProvider>,
  );

const marks = (container: HTMLElement) => [...container.querySelectorAll("[aria-hidden='true']")].filter((e) => e.querySelector("svg"));
const params = { params: Promise.resolve({ locale: "en" }) };

/** Sprint 89, BL-19.20: the audience pages, the 404, the placeholder and the legal pages carry marks. */
describe("AudiencePage", () => {
  it("draws the mark it was given beside its point, in order, and none for a point with none", async () => {
    const { container } = await show(
      AudiencePage({
        namespace: "aboutPage",
        points: ["one", "two", "three"],
        primaryHref: "/skills",
        icons: [<BookOpenIcon key="a" />, null, null],
      }),
    );
    const cards = [...container.querySelectorAll(".grid > div")] as HTMLElement[];
    expect(cards.length).toBe(3);
    expect(cards[0].querySelector("[aria-hidden='true'] svg")).toBeTruthy();
    expect(cards[1].querySelector("[aria-hidden='true'] svg")).toBeNull();
    expect(cards[2].querySelector("svg")).toBeNull();
  });

  it("draws no mark at all when no icons are passed, and keeps every word", async () => {
    const { container } = await show(AudiencePage({ namespace: "aboutPage", points: ["one", "two", "three"], primaryHref: "/skills" }));
    expect(marks(container).length).toBe(0);
    expect(screen.getByText("One vocabulary")).toBeTruthy();
    expect(screen.getByText("Scores you can interrogate")).toBeTruthy();
  });
});

/** A page returns an element tree whose `AudiencePage` is an async server component jsdom cannot render, so the tree is walked
 *  for it and it is rendered by awaiting it with the props the page gave it. */
function audienceOf(node: React.ReactNode): React.ReactElement<React.ComponentProps<typeof AudiencePage>> | null {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = audienceOf(child);
      if (found) return found;
    }
    return null;
  }
  const el = node as React.ReactElement<{ children?: React.ReactNode }>;
  if (el.type === AudiencePage) return el as never;
  return audienceOf(el.props?.children);
}

describe.each([
  ["About", () => AboutPage(params), "One vocabulary"],
  ["For employers", () => EmployersPage(params), "Hire against a standard, not a keyword"],
  ["For providers", () => ProvidersPage(params), "Recommended by gap, not by advertising"],
])("the %s page", (_name, page, firstPoint) => {
  it("gives each of its three points its own mark", async () => {
    const audience = audienceOf(await page());
    expect(audience).toBeTruthy();
    expect(audience!.props.icons?.length).toBe(3);
    const { container } = await show(AudiencePage(audience!.props));
    expect(screen.getByText(firstPoint)).toBeTruthy();
    const cards = [...container.querySelectorAll(".grid.gap-4 > div")] as HTMLElement[];
    expect(cards.length).toBe(3);
    const shapes = cards.map((c) => c.querySelector("[aria-hidden='true'] svg")?.innerHTML);
    expect(shapes.every(Boolean)).toBe(true);
    expect(new Set(shapes).size).toBe(3);
  });
});

describe("the 404", () => {
  it("has a mark above its badge, and its words and both ways out unchanged", async () => {
    const { container } = await show(NotFound());
    expect(marks(container).length).toBe(1);
    expect(screen.getByText("404")).toBeTruthy();
    expect(screen.getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/", "/jobs"]);
  });
});

describe("the placeholder page", () => {
  it("draws a clock in its 'drafting' badge, and says drafting, never coming soon", async () => {
    const { container } = await show(PlaceholderPage({ titleKey: "careers", noteKey: "careers" }));
    const badge = screen.getByText("Drafting");
    expect(badge.querySelector("svg")).toBeTruthy();
    expect(container.textContent?.toLowerCase()).not.toContain("coming soon");
  });
});

describe("the legal pages", () => {
  it("put a warning shape in the draft badge, on every page that carries it", async () => {
    for (const doc of ["privacy", "terms", "grievance"] as const) {
      const { unmount } = await show(LegalPage({ doc }));
      const badge = screen.getByText("Draft — pending legal review");
      expect(badge.querySelector("svg"), doc).toBeTruthy();
      unmount();
    }
  });

  it("mark the grievance officer's heading with a shield, and no other page has that block", async () => {
    const grievance = await show(LegalPage({ doc: "grievance" }));
    const heading = screen.getByRole("heading", { name: "Grievance officer" });
    expect(heading.parentElement!.querySelector("[aria-hidden='true'] svg")).toBeTruthy();
    grievance.unmount();
    await show(LegalPage({ doc: "privacy" }));
    expect(screen.queryByRole("heading", { name: "Grievance officer" })).toBeNull();
  });

  it("make the link back to the account a 44 px target on every legal page", async () => {
    for (const doc of ["privacy", "terms", "grievance"] as const) {
      const { unmount } = await show(LegalPage({ doc }));
      expect(screen.getByRole("link", { name: "Go to your Account page" }).className, doc).toContain("min-h-11");
      unmount();
    }
  });
});
