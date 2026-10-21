import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { INTEREST_LOOK, InterestCard, type Interest } from "@/components/cards/InterestCard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

const row = (over: Partial<Interest> = {}): Interest =>
  ({
    id: "i1",
    status: "registered",
    registered_at: "2026-09-21T10:00:00Z",
    course: { slug: "ward-shift", title: "Ward Shift Management", tenant: { name: "NSDC Healthcare Academy" } },
    ...over,
  }) as unknown as Interest;

/** Sprint 87, BL-19.17: a course the learner asked about, on the same card as an application. */
describe("InterestCard", () => {
  it("has the provider's mark, the course as a link, the provider and the date as an icon chip", () => {
    const { container } = renderUi(<InterestCard interest={row()} />);
    expect(screen.getByRole("link", { name: "Ward Shift Management" }).getAttribute("href")).toBe("/courses/ward-shift");
    expect(screen.getByText("NSDC Healthcare Academy")).toBeTruthy();
    expect([...container.querySelectorAll("[aria-hidden='true']")].some((e) => e.textContent === "N")).toBe(true);
    expect(screen.getByText(/Registered on Sep 21, 2026/).querySelector("svg")).toBeTruthy();
  });

  it.each([
    ["registered", "Registered"],
    ["contacted", "They got in touch"],
    ["enrolled", "Enrolled"],
    ["withdrawn", "Withdrawn"],
  ] as const)("draws %s as the word %s with a shape", (status, word) => {
    renderUi(<InterestCard interest={row({ status })} />);
    expect(screen.getByText(word, { selector: "span" }).querySelector("svg")).toBeTruthy();
  });

  it("has a look for every state a provider can set, enrolled included", () => {
    expect(Object.keys(INTEREST_LOOK).sort()).toEqual(["contacted", "enrolled", "registered", "withdrawn"]);
    expect(INTEREST_LOOK.enrolled.tone).toBe("good");
    expect(INTEREST_LOOK.withdrawn.tone).toBe("warn");
    expect(INTEREST_LOOK.registered.icon).not.toBe(INTEREST_LOOK.enrolled.icon);
  });
});
