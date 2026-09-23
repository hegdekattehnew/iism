import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TagSection } from "@/components/profile/TagSection";
import { ApiError } from "@/lib/http";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock(
  "@/i18n/navigation",
  async () => (await import("@/test/harness")).navigationMock,
);

const addEntry = { mutateAsync: vi.fn(), isPending: false };
const removeEntry = { mutate: vi.fn() };
vi.mock("@/lib/profile", () => ({
  useProfileMutations: () => ({ addEntry, removeEntry }),
}));

/**
 * The job seeker's half of the same fault the employer reported: a save that
 * failed said "Could not save. Please check the fields." whatever the server
 * had actually objected to.
 */

const section = () => (
  <TagSection
    collection={"preferred_roles" as never}
    title="Roles you want"
    entries={[]}
    label="Role title"
    toBody={(a: string) => ({ title: a })}
    render={(e) => String(e.title)}
    maxLength={120}
  />
);

beforeEach(() => {
  resetWorld();
  addEntry.mutateAsync.mockReset();
});

describe("TagSection — what it says when a save fails", () => {
  const type = (value: string) =>
    fireEvent.change(screen.getByLabelText("Role title"), { target: { value } });

  it("shows the field and the rule the server named", async () => {
    addEntry.mutateAsync.mockRejectedValue(
      new ApiError(422, "title: String should have at most 120 characters"),
    );
    renderUi(section());
    type("A very long role title");
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));

    expect(
      await screen.findByText("title: String should have at most 120 characters"),
    ).toBeTruthy();
  });

  it("keeps its own sentence for a duplicate, which is clearer than the server's", async () => {
    addEntry.mutateAsync.mockRejectedValue(new ApiError(409, "Already exists"));
    renderUi(section());
    type("Cashier");
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));

    expect(await screen.findByText("That entry already exists.")).toBeTruthy();
  });

  it("falls back to the generic line when the failure carried nothing", async () => {
    addEntry.mutateAsync.mockRejectedValue(new ApiError(500, null));
    renderUi(section());
    type("Cashier");
    fireEvent.click(screen.getByRole("button", { name: /Add/ }));

    expect(await screen.findByText(/Could not save/)).toBeTruthy();
  });

  it("stops the too-long value reaching the server at all", async () => {
    // The limit the server enforces, mirrored on the input: the browser
    // truncates rather than letting a 422 happen.
    renderUi(section());
    const input = screen.getByLabelText("Role title") as HTMLInputElement;
    expect(input.maxLength).toBe(120);
  });
});
