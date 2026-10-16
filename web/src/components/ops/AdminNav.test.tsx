import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminNav } from "@/components/ops/AdminNav";
import { ADMIN_SECTIONS, sectionId } from "@/components/ops/admin-sections";
import { renderUi, resetWorld, world } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);

beforeEach(() => resetWorld());

/** Sprint 73, UI-16: a way to jump around a page that was thirty-one screens long. */
describe("the back office's section nav", () => {
  it("links every section by the id the page gives it, in the order an operator needs them", () => {
    renderUi(<AdminNav />);
    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(ADMIN_SECTIONS.map((s) => `#${sectionId(s)}`));
    expect(links[0].textContent).toBe("Overview");
    expect(links[1].textContent).toBe("Verification");
  });

  it("is a labelled landmark", () => {
    renderUi(<AdminNav />);
    expect(screen.getByRole("navigation", { name: "Back office sections" })).toBeTruthy();
  });

  it("offers enrolment to the admin tier, which alone may use it (OPS_ENROL)", () => {
    world.staffTier = "admin";
    renderUi(<AdminNav />);
    expect(screen.getByRole("link", { name: "Enrolment" })).toBeTruthy();
  });

  it("does not offer a support-tier operator a link to a panel that is not there", () => {
    world.staffTier = "support";
    renderUi(<AdminNav />);
    expect(screen.queryByRole("link", { name: "Enrolment" })).toBeNull();
    expect(screen.getAllByRole("link").length).toBe(ADMIN_SECTIONS.length - 1);
  });

  it("scrolls sideways on a phone and wraps from sm up, so no label is ever cut off at the edge", () => {
    renderUi(<AdminNav />);
    const list = screen.getAllByRole("link")[0].closest("ul")!;
    expect(list.className).toContain("overflow-x-auto");
    expect(list.className).toContain("sm:flex-wrap");
  });
});
