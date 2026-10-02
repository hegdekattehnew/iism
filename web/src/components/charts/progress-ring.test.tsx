import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressRing } from "@/components/charts/progress-ring";
import { renderUi } from "@/test/harness";

describe("ProgressRing", () => {
  it("renders the percentage and label", () => {
    renderUi(<ProgressRing percent={62} label="Profile completeness" />);
    expect(screen.getByText("62%")).toBeTruthy();
    expect(screen.getByText("Profile completeness")).toBeTruthy();
  });

  it("clamps an out-of-range percentage rather than drawing an invalid arc", () => {
    renderUi(<ProgressRing percent={140} label="Conversion" />);
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("renders the secondary line when given one", () => {
    renderUi(<ProgressRing percent={40} label="Conversion" secondary="6 of 15" />);
    expect(screen.getByText("6 of 15")).toBeTruthy();
  });
});
