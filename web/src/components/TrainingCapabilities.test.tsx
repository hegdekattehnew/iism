import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_CAPABILITIES,
  TrainingCapabilities,
  doesSomething,
} from "@/components/TrainingCapabilities";
import { renderUi } from "@/test/harness";

/** Sprint 94, ADR-102: the two capabilities of a training organisation, one control everywhere. */
describe("TrainingCapabilities", () => {
  it("is a named group of two boxes, each with the sentence that says what it means", () => {
    renderUi(<TrainingCapabilities value={DEFAULT_CAPABILITIES} onChange={() => {}} />);
    expect(screen.getByRole("group", { name: "What does your organisation do?" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: /Sells courses/ })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: /Delivers training/ })).toBeTruthy();
    expect(screen.getByText(/learners register interest with you/)).toBeTruthy();
    expect(screen.getByText(/other providers authorise you to deliver/)).toBeTruthy();
  });

  it("starts where every provider was before it existed: selling, not delivering", () => {
    expect(DEFAULT_CAPABILITIES).toEqual({ sells: true, delivers: false });
  });

  it("reports each change with the other one unchanged", () => {
    const onChange = vi.fn();
    renderUi(<TrainingCapabilities value={{ sells: true, delivers: false }} onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /Delivers training/ }));
    expect(onChange).toHaveBeenLastCalledWith({ sells: true, delivers: true });
    fireEvent.click(screen.getByRole("checkbox", { name: /Sells courses/ }));
    expect(onChange).toHaveBeenLastCalledWith({ sells: false, delivers: false });
  });

  it("says so, and only then, when neither is chosen", () => {
    const a = renderUi(<TrainingCapabilities value={{ sells: true, delivers: false }} onChange={() => {}} />);
    expect(screen.queryByRole("alert")).toBeNull();
    a.unmount();
    renderUi(<TrainingCapabilities value={{ sells: false, delivers: false }} onChange={() => {}} />);
    expect(screen.getByRole("alert").textContent).toBe("Choose at least one.");
  });

  it("gives each box a 44 px target", () => {
    renderUi(<TrainingCapabilities value={DEFAULT_CAPABILITIES} onChange={() => {}} />);
    for (const box of screen.getAllByRole("checkbox")) {
      expect(box.closest("label")!.className).toContain("min-h-11");
    }
  });

  it("can be switched off as a whole while something saves", () => {
    renderUi(<TrainingCapabilities value={DEFAULT_CAPABILITIES} onChange={() => {}} disabled />);
    expect(screen.getByRole("group").hasAttribute("disabled")).toBe(true);
  });

  it("knows what 'does something' means", () => {
    expect(doesSomething({ sells: false, delivers: true })).toBe(true);
    expect(doesSomething({ sells: true, delivers: false })).toBe(true);
    expect(doesSomething({ sells: false, delivers: false })).toBe(false);
  });
});
