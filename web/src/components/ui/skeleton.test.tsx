import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { ListSkeleton, Skeleton } from "@/components/ui/skeleton";

/**
 * Sprint 54. A footer on screen beside a half-loaded list is pushed off the bottom when the list
 * lands, which on a phone is the whole screen jumping (0.2 to 0.6 of layout shift against a limit of
 * 0.1). The fix has two ends that only work together: every placeholder carries `data-loading`, and
 * `globals.css` hides the footer while one is on the page. A rename of either end would compile,
 * pass every other test and quietly bring the jump back, so they are pinned here. The browser sweep
 * is the behavioural check; this one fails in a second and says which end moved.
 */
describe("loading placeholders", () => {
  it("a Skeleton marks the page as still loading", () => {
    const { container } = render(<Skeleton className="h-4" />);
    expect(container.firstElementChild?.hasAttribute("data-loading")).toBe(true);
  });

  it("a list placeholder is that many cards, each one a Skeleton, and hidden from assistive technology", () => {
    const { container } = render(<ListSkeleton rows={4} />);
    expect(container.querySelectorAll("li")).toHaveLength(4);
    expect(container.querySelectorAll("[data-loading]")).toHaveLength(4);
    expect(container.querySelector("ul")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("the stylesheet hides the footer while anything on the page is loading, and keeps its place in the layout", () => {
    const css = readFileSync(path.join(__dirname, "..", "..", "app", "globals.css"), "utf8");
    const rule = css.match(/body:has\(\[data-loading\]\)\s+footer\s*\{([^}]*)\}/);
    expect(rule, "the footer rule in globals.css").not.toBeNull();
    // `visibility`, not `display: none`: the footer must keep its box, or it appears by pushing
    // everything above it, which is the shift this exists to prevent.
    expect(rule?.[1]).toMatch(/visibility:\s*hidden/);
    expect(rule?.[1]).not.toMatch(/display:\s*none/);
  });
});
