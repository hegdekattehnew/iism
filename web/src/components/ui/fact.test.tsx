import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Fact, FactValue, Facts } from "@/components/ui/fact";
import { RupeeIcon } from "@/components/ui/icons";

/** Sprint 85, BL-19.15: a listing's facts as labelled values with an icon on each label. */
function grid() {
  return render(
    <Facts className="grid-cols-2">
      <Fact icon={<RupeeIcon />} label="Salary">
        <FactValue>About ₹18,300 a month</FactValue>
        <dd>₹2,20,000 a year</dd>
      </Fact>
      <Fact icon={<RupeeIcon />} label="Qualification" wide>
        <FactValue large>Nursing assistant</FactValue>
      </Fact>
    </Facts>,
  );
}

describe("Facts", () => {
  it("is a description list that holds only groups of terms and values", () => {
    const { container } = grid();
    const dl = container.querySelector("dl") as HTMLElement;
    expect(dl).toBeTruthy();
    const children = [...dl.children];
    expect(children.length).toBe(2);
    for (const group of children) {
      expect(group.tagName).toBe("DIV");
      for (const part of group.children) expect(["DT", "DD"]).toContain(part.tagName);
    }
  });

  it("gives each value its term, so a screen reader announces them together", () => {
    grid();
    expect(screen.getByText("Salary").tagName).toBe("DT");
    expect(screen.getByText("About ₹18,300 a month").tagName).toBe("DD");
    expect(screen.getByText("₹2,20,000 a year").tagName).toBe("DD");
  });

  it("draws the icon beside the label and hides it from assistive technology", () => {
    const { container } = grid();
    const term = container.querySelector("dt") as HTMLElement;
    const mark = term.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(mark.querySelector("svg")).toBeTruthy();
    expect(term.textContent).toBe("Salary");
  });

  it("lets a long value take the whole row, and only when asked", () => {
    const { container } = grid();
    const [first, second] = [...(container.querySelector("dl") as HTMLElement).children];
    expect(first.className).not.toContain("col-span-full");
    expect(second.className).toContain("col-span-full");
  });

  it("sizes a value: base by default, large when asked", () => {
    grid();
    expect(screen.getByText("About ₹18,300 a month").className).toContain("text-base");
    expect(screen.getByText("Nursing assistant").className).toContain("text-lg");
  });

  it("sits on a raised surface with the card's shadow", () => {
    const { container } = grid();
    const cls = (container.querySelector("dl") as HTMLElement).className;
    expect(cls).toContain("shadow-card");
    expect(cls).toContain("bg-surface");
  });
});
