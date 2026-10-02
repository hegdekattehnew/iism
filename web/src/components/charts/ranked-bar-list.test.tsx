import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RankedBarList } from "@/components/charts/ranked-bar-list";
import { renderUi } from "@/test/harness";

describe("RankedBarList", () => {
  it("renders a bar per item with its value", () => {
    renderUi(
      <RankedBarList
        items={[
          { key: "a", label: "Job A", value: 8 },
          { key: "b", label: "Job B", value: 4 },
        ]}
        emptyLabel="Nothing yet"
      />,
    );
    expect(screen.getByText("Job A")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
    expect(screen.getByText("Job B")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
  });

  it("renders the empty state when there are no items", () => {
    renderUi(<RankedBarList items={[]} emptyLabel="Nothing yet" />);
    expect(screen.getByText("Nothing yet")).toBeTruthy();
  });

  it("calls onSelect with the row's key when clicked", () => {
    const onSelect = vi.fn();
    renderUi(
      <RankedBarList
        items={[{ key: "a", label: "Job A", value: 8 }]}
        onSelect={onSelect}
        emptyLabel="Nothing yet"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Job A/ }));
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("renders plain rows, not buttons, when onSelect is omitted", () => {
    renderUi(<RankedBarList items={[{ key: "a", label: "Job A", value: 8 }]} emptyLabel="Nothing yet" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
