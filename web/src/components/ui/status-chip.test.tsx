import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CheckCircleIcon, XCircleIcon } from "@/components/ui/icons";
import { StatusChip } from "@/components/ui/status-chip";

/** Sprint 87, BL-19.17: a state is a word, a shape and a tone, never colour alone. */
describe("StatusChip", () => {
  it("says the word, with a shape beside it", () => {
    render(
      <StatusChip tone="good" icon={CheckCircleIcon}>
        Shortlisted
      </StatusChip>,
    );
    const chip = screen.getByText("Shortlisted");
    expect(chip.querySelector("svg")).toBeTruthy();
    expect(chip.className).toContain("bg-success-surface");
  });

  it.each([
    ["neutral", "bg-surface-muted"],
    ["good", "bg-success-surface"],
    ["warn", "bg-warning-surface"],
    ["bad", "bg-danger-surface"],
    ["info", "bg-info-surface"],
    ["brand", "bg-accent-soft"],
  ] as const)("a %s chip is on the %s token", (tone, token) => {
    render(
      <StatusChip tone={tone} icon={XCircleIcon}>
        x
      </StatusChip>,
    );
    expect(screen.getByText("x").className).toContain(token);
  });

  it("is the md badge, so the state is not an afterthought beside 15 px text", () => {
    render(
      <StatusChip tone="neutral" icon={XCircleIcon}>
        Applied
      </StatusChip>,
    );
    expect(screen.getByText("Applied").className).toContain("text-xs");
  });
});
