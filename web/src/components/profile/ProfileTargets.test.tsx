import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingWizard } from "@/components/profile/OnboardingWizard";
import { TagSection } from "@/components/profile/TagSection";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const finish = { mutate: vi.fn(), isError: false, isPending: false, error: null };
const removeEntry = { mutate: vi.fn() };
vi.mock("@/lib/profile", () => ({
  useProfileMutations: () => ({ addEntry: { mutateAsync: vi.fn(), isPending: false }, removeEntry, finishOnboarding: finish }),
}));
// The wizard's steps are other components' business here.
vi.mock("@/components/profile/AboutSection", () => ({ AboutSection: () => <div /> }));
vi.mock("@/components/profile/SkillsSection", () => ({ SkillsSection: () => <div /> }));
vi.mock("@/components/profile/SectionEditor", () => ({ SectionEditor: () => <div />, useSectionDefs: () => [] }));

beforeEach(() => {
  resetWorld();
  finish.mutate.mockReset();
  removeEntry.mutate.mockReset();
});

/** Sprint 86, BL-19.16: the smallest controls on the profile were a 10 px "x" and a bare "Skip for now". */
describe("TagSection: the remove control", () => {
  const section = () => (
    <TagSection
      collection={"preferred_roles" as never}
      title="Roles you want"
      entries={[{ id: "r1", title: "Ward attendant" }, { id: "r2", title: "Phlebotomist" }] as never[]}
      label="Role title"
      toBody={(a: string) => ({ title: a })}
      render={(e) => String(e.title)}
      maxLength={120}
    />
  );

  it("is a 44 px square on the end of the chip, so the chip is the target", () => {
    renderUi(section());
    const buttons = screen.getAllByRole("button", { name: "Remove" });
    expect(buttons.length).toBe(2);
    for (const b of buttons) {
      expect(b.className).toContain("h-11");
      expect(b.className).toContain("w-11");
    }
  });

  it("removes the entry it belongs to", () => {
    renderUi(section());
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[1]);
    expect(removeEntry.mutate.mock.calls[0][0]).toEqual({ collection: "preferred_roles", id: "r2" });
  });
});

describe("OnboardingWizard: skip", () => {
  it("is a 44 px control and finishes the setup", () => {
    renderUi(<OnboardingWizard profile={null} />);
    const skip = screen.getByRole("button", { name: "Skip for now" });
    expect(skip.className).toContain("min-h-11");
    fireEvent.click(skip);
    expect(finish.mutate).toHaveBeenCalledTimes(1);
  });
});
