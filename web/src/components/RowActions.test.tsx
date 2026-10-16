import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RowActions } from "@/components/RowActions";

/** Sprint 73, UI-15: the row's actions are a primary, a secondary and a closed "More". */
describe("RowActions", () => {
  it("renders the primary and secondary in the row and the rest inside a closed details", () => {
    const { container } = render(
      <RowActions
        moreLabel="More"
        primary={<button>Primary</button>}
        secondary={<button>Secondary</button>}
        more={[<button key="a">Later</button>, <button key="b">Undo</button>]}
      />,
    );
    const more = container.querySelector("details")!;
    expect(more.hasAttribute("open")).toBe(false);
    expect(more.contains(screen.getByText("Primary"))).toBe(false);
    expect(more.contains(screen.getByText("Secondary"))).toBe(false);
    expect(more.contains(screen.getByText("Later"))).toBe(true);
    expect(more.contains(screen.getByText("Undo"))).toBe(true);
    expect(container.querySelector("summary")!.textContent).toContain("More");
  });

  it("draws no More at all when nothing is left to put in it", () => {
    const { container } = render(
      <RowActions moreLabel="More" primary={<button>Primary</button>} more={[false, null, undefined]} />,
    );
    expect(container.querySelector("details")).toBeNull();
  });

  it("holds the More control itself to 44 px", () => {
    const { container } = render(<RowActions moreLabel="More" more={[<button key="a">x</button>]} />);
    expect(container.querySelector("summary")!.className).toMatch(/min-h-11/);
  });
});
