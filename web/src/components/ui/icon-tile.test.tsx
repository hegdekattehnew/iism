import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IconTile } from "@/components/ui/icon-tile";
import { BriefcaseIcon } from "@/components/ui/icons";

/** Sprint 85, BL-19.15: the mark a tile, a band or a row leads with. */
describe("IconTile", () => {
  it("is hidden from assistive technology: the words beside it say the same thing", () => {
    const { container } = render(
      <IconTile>
        <BriefcaseIcon />
      </IconTile>,
    );
    const tile = container.firstElementChild as HTMLElement;
    expect(tile.getAttribute("aria-hidden")).toBe("true");
    expect(tile.querySelector("svg")).toBeTruthy();
  });

  it.each([
    ["brand", "bg-accent-soft"],
    ["good", "bg-success-surface"],
    ["info", "bg-info-surface"],
    ["warn", "bg-warning-surface"],
    ["neutral", "bg-surface-muted"],
  ] as const)("a %s tile is on the %s token", (tone, token) => {
    const { container } = render(<IconTile tone={tone}>x</IconTile>);
    expect((container.firstElementChild as HTMLElement).className).toContain(token);
  });

  it("is brand and 40 px by default, 32 px when small, and the icon is scaled to the tile", () => {
    const big = render(<IconTile>x</IconTile>).container.firstElementChild as HTMLElement;
    expect(big.className).toContain("bg-accent-soft");
    expect(big.className).toContain("h-10 w-10");
    expect(big.className).toContain("[&>svg]:h-5");
    const small = render(<IconTile size="sm">x</IconTile>).container.firstElementChild as HTMLElement;
    expect(small.className).toContain("h-8 w-8");
    expect(small.className).toContain("[&>svg]:h-4");
  });

  it("keeps a class the caller adds", () => {
    const { container } = render(<IconTile className="mt-1">x</IconTile>);
    expect((container.firstElementChild as HTMLElement).className).toContain("mt-1");
  });
});
