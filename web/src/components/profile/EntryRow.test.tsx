import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EntryRow } from "@/components/profile/fields";

/** Sprint 86, BL-19.16: the row's two buttons are 44 px and each is named for its row. */
function row(over: Partial<Parameters<typeof EntryRow>[0]> = {}) {
  const onEdit = vi.fn();
  const onRemove = vi.fn();
  render(
    <ul>
      <EntryRow
        title="Ward attendant"
        subtitle="Apollo Care"
        meta="2022 to 2024"
        onEdit={onEdit}
        onRemove={onRemove}
        editLabel="Edit"
        removeLabel="Remove"
        {...over}
      />
    </ul>,
  );
  return { onEdit, onRemove };
}

describe("EntryRow", () => {
  it("names each button for its row, and the name contains the visible word", () => {
    row();
    const edit = screen.getByRole("button", { name: "Edit: Ward attendant" });
    const remove = screen.getByRole("button", { name: "Remove: Ward attendant" });
    expect(edit.textContent).toBe("Edit");
    expect(remove.textContent).toBe("Remove");
  });

  it("tells two rows apart by name", () => {
    render(
      <ul>
        <EntryRow title="Ward attendant" onEdit={() => {}} onRemove={() => {}} editLabel="Edit" removeLabel="Remove" />
        <EntryRow title="Phlebotomist" onEdit={() => {}} onRemove={() => {}} editLabel="Edit" removeLabel="Remove" />
      </ul>,
    );
    const names = screen.getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(new Set(names).size).toBe(4);
  });

  it("makes both buttons 44 px tall", () => {
    row();
    for (const name of [/^Edit: /, /^Remove: /]) {
      expect(screen.getByRole("button", { name }).className).toContain("min-h-11");
    }
  });

  it("calls the right handler for each", () => {
    const { onEdit, onRemove } = row();
    fireEvent.click(screen.getByRole("button", { name: /^Remove: / }));
    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onEdit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /^Edit: / }));
    expect(onEdit).toHaveBeenCalledTimes(1);
  });
});
