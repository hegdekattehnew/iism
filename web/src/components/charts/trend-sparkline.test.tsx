import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrendSparkline } from "@/components/charts/trend-sparkline";

describe("TrendSparkline", () => {
  it("renders a polyline through every point", () => {
    const { container } = render(
      <TrendSparkline
        points={[
          { bucket: "w1", value: 2 },
          { bucket: "w2", value: 5 },
          { bucket: "w3", value: 3 },
        ]}
        label="Applications per week"
      />,
    );
    expect(screen.getByText("Applications per week")).toBeTruthy();
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeTruthy();
    expect(polyline?.getAttribute("points")?.split(" ").length).toBe(3);
  });

  it("renders nothing for an empty series", () => {
    const { container } = render(<TrendSparkline points={[]} label="Applications per week" />);
    expect(container.textContent).toBe("");
  });
});
