import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CollapsiblePanel } from "@/components/ops/CollapsiblePanel";

const mounted = vi.fn();
function Body() {
  mounted();
  return <h2>{"The panel's own heading"}</h2>;
}

afterEach(() => {
  mounted.mockReset();
  window.location.hash = "";
});

const opened = (container: HTMLElement) => {
  const details = container.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  return details;
};

/** Sprint 73, UI-16: folded panels cost nothing until opened, and an anchor into one opens it. */
describe("a folded reference panel", () => {
  it("is one summary row and mounts nothing while closed", () => {
    render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    expect(screen.getByText("Programme outcomes")).toBeTruthy();
    expect(mounted).not.toHaveBeenCalled();
    expect(screen.queryByText("The panel's own heading")).toBeNull();
  });

  it("mounts the panel the first time it is opened", () => {
    const { container } = render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    opened(container);
    expect(screen.getByText("The panel's own heading")).toBeTruthy();
    expect(mounted).toHaveBeenCalled();
  });

  it("stays mounted when folded again, so nothing typed is lost", () => {
    const { container } = render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    const details = opened(container);
    details.open = false;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByText("The panel's own heading")).toBeTruthy();
  });

  it("keeps the panel's own heading for screen readers and hides it visually (the summary says it)", () => {
    const { container } = render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    opened(container);
    expect(container.querySelector("div.sr-only, div[class*='sr-only']") ?? container.querySelector("[class*='h2:first-of-type']:not(summary)")).toBeTruthy();
  });

  it("opens when the address names it, so an anchor never lands on a closed row", async () => {
    window.location.hash = "#admin-x";
    const { container } = render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    await waitFor(() => expect(container.querySelector("details")!.open).toBe(true));
    await waitFor(() => expect(screen.getByText("The panel's own heading")).toBeTruthy());
  });

  it("stays closed when the address names another section", async () => {
    window.location.hash = "#admin-other";
    const { container } = render(<CollapsiblePanel id="admin-x" title="Programme outcomes" Panel={Body} />);
    expect(container.querySelector("details")!.open).toBe(false);
  });
});
