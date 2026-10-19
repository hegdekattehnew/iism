import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrustStrip } from "@/components/ui/trust-strip";

/** Sprint 85, BL-19.15: who is behind a listing, as an icon and a sentence. */
describe("TrustStrip", () => {
  it("says a verified organisation in words, in the success colour, on a green tile", () => {
    const { container } = render(
      <TrustStrip verified statement="Verified employer">
        <p>Never pay to apply.</p>
      </TrustStrip>,
    );
    const words = screen.getByText("Verified employer");
    expect(words.className).toContain("text-success-text");
    expect(container.querySelector("[aria-hidden='true']")!.className).toContain("bg-success-surface");
    expect(screen.getByText("Never pay to apply.")).toBeTruthy();
  });

  it("says 'not yet verified' plainly, muted and on a neutral tile, so nothing rests on colour", () => {
    const { container } = render(
      <TrustStrip verified={false} statement="Not yet verified">
        <p>Never pay to apply.</p>
      </TrustStrip>,
    );
    const words = screen.getByText("Not yet verified");
    expect(words.className).toContain("text-muted");
    expect(words.className).not.toContain("success");
    expect(container.querySelector("[aria-hidden='true']")!.className).toContain("bg-surface-muted");
  });

  it("draws a different shape for each state", () => {
    const a = render(<TrustStrip verified statement="x">y</TrustStrip>).container.querySelector("svg")!.innerHTML;
    const b = render(<TrustStrip verified={false} statement="x">y</TrustStrip>).container.querySelector("svg")!.innerHTML;
    expect(a).not.toBe(b);
  });

  it("holds the lines under it, links included", () => {
    render(
      <TrustStrip verified statement="Verified provider">
        <a href="#report">Report this</a>
      </TrustStrip>,
    );
    expect(screen.getByRole("link", { name: "Report this" }).getAttribute("href")).toBe("#report");
  });
});
