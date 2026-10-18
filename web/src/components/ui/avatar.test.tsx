import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar, initialOf, toneIndex } from "@/components/ui/avatar";

/** Sprint 84, BL-19.15: a mark that stands in for a logo the CSP would block. */
describe("the initial", () => {
  it.each([
    ["Apollo Care", "A"],
    ["  apollo care", "A"],
    ["आपोलो केयर", "आ"],
    ["3M India", "3"],
    ["(Swift) Logistics", "S"],
    ["ñandú", "Ñ"],
  ])("%s is %s", (name, initial) => {
    expect(initialOf(name)).toBe(initial);
  });

  it("is a question mark for a name with nothing to show, never an empty box", () => {
    expect(initialOf("")).toBe("?");
    expect(initialOf("   ")).toBe("?");
    expect(initialOf("--- ...")).toBe("?");
  });

  it("is one character even when the first is outside the basic plane", () => {
    expect(Array.from(initialOf("𝒜pollo")).length).toBe(1);
  });
});

describe("the tint", () => {
  it("is the same for the same name however much space is round it", () => {
    expect(toneIndex("Apollo Care")).toBe(toneIndex("  Apollo Care "));
  });

  it("is always one of the four, and the names of a real list do not all share one", () => {
    const names = ["Apollo Care", "MedLife", "Swift Logistics", "Urban Retail", "Skill Forge", "Nagpur Training", "आपोलो", "Zen"];
    const tones = names.map(toneIndex);
    for (const t of tones) {
      expect(t).toBeGreaterThanOrEqual(0);
      expect(t).toBeLessThan(4);
    }
    expect(new Set(tones).size).toBeGreaterThan(1);
  });
});

describe("the mark", () => {
  it("is decorative: the name is written beside it, so a screen reader skips it", () => {
    const { container } = render(<Avatar name="Apollo Care" />);
    const mark = container.firstElementChild as HTMLElement;
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.textContent).toBe("A");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("takes its colours from tokens, not from a literal", () => {
    const { container } = render(<Avatar name="Apollo Care" />);
    const cls = (container.firstElementChild as HTMLElement).className;
    expect(cls).toMatch(/bg-(accent-soft|info-surface|success-surface|warning-surface)/);
    expect(cls).not.toMatch(/#|rgb|\[/);
  });

  it("takes an extra class without losing its own", () => {
    const { container } = render(<Avatar name="Apollo Care" className="h-12 w-12" />);
    expect((container.firstElementChild as HTMLElement).className).toContain("h-12");
  });
});
