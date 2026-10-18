import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChipButton, ChipRow, ChipSelect } from "@/components/ui/chip";

/** Sprint 84, BL-19.15: filters as chips, each a native control with a name and a 44 px target. */
describe("a chip that is a select", () => {
  const draw = (value = "", onChange = vi.fn()) =>
    render(
      <ChipSelect label="Job type" active={value !== ""} value={value} onChange={onChange}>
        <option value="">All types</option>
        <option value="gig">Gig</option>
      </ChipSelect>,
    );

  it("is named by its label, and is a real select (a phone opens its own picker)", () => {
    draw();
    const select = screen.getByRole("combobox", { name: "Job type" }) as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    expect(select.value).toBe("");
  });

  it("tells the page about a choice", () => {
    const onChange = vi.fn();
    draw("", onChange);
    fireEvent.change(screen.getByRole("combobox", { name: "Job type" }), { target: { value: "gig" } });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("is drawn filled when it narrows the list, and plain when it does not", () => {
    const plain = draw("");
    expect((plain.container.firstElementChild as HTMLElement).className).not.toContain("bg-accent-soft");
    plain.unmount();
    const filled = draw("gig");
    expect((filled.container.firstElementChild as HTMLElement).className).toContain("bg-accent-soft");
  });

  it("is 44 px tall, as a whole, and its arrow is decoration", () => {
    const { container } = draw();
    expect((container.firstElementChild as HTMLElement).className).toContain("min-h-11");
    expect((screen.getByRole("combobox") as HTMLElement).className).toContain("min-h-11");
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("a chip that is a button", () => {
  it("presses, and is a button that does not submit a form", () => {
    const onClick = vi.fn();
    render(<ChipButton onClick={onClick}>Clear</ChipButton>);
    const b = screen.getByRole("button", { name: "Clear" });
    expect(b.getAttribute("type")).toBe("button");
    fireEvent.click(b);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(b.className).toContain("min-h-11");
  });
});

describe("the row", () => {
  it("is a named group that scrolls sideways on a phone instead of wrapping", () => {
    render(
      <ChipRow label="Filters">
        <ChipButton>One</ChipButton>
      </ChipRow>,
    );
    const group = screen.getByRole("group", { name: "Filters" });
    expect(group.className).toContain("overflow-x-auto");
    expect(group.className).toContain("sm:flex-wrap");
  });
});
