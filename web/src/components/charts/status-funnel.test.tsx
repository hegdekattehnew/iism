import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StatusFunnel } from "@/components/charts/status-funnel";
import { renderUi } from "@/test/harness";

describe("StatusFunnel", () => {
  it("renders every stage with its value", () => {
    renderUi(
      <StatusFunnel
        stages={[
          { key: "applied", label: "Applied", value: 10 },
          { key: "shortlisted", label: "Shortlisted", value: 4 },
          { key: "hired", label: "Hired", value: 1 },
        ]}
      />,
    );
    expect(screen.getByText("Applied")).toBeTruthy();
    expect(screen.getByText("10")).toBeTruthy();
    expect(screen.getByText("Hired")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
  });

  it("does not divide by zero when the first stage is empty", () => {
    renderUi(
      <StatusFunnel
        stages={[
          { key: "applied", label: "Applied", value: 0 },
          { key: "hired", label: "Hired", value: 0 },
        ]}
      />,
    );
    expect(screen.getAllByText("0").length).toBe(2);
  });

  it("calls onSelectStage with the stage's key when clicked", () => {
    const onSelectStage = vi.fn();
    renderUi(
      <StatusFunnel
        stages={[{ key: "applied", label: "Applied", value: 5 }]}
        onSelectStage={onSelectStage}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Applied/ }));
    expect(onSelectStage).toHaveBeenCalledWith("applied");
  });
});
