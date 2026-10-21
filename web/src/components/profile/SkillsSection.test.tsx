import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SkillsSection } from "@/components/profile/SkillsSection";
import type { Profile } from "@/lib/profile";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const removeSkill = { mutate: vi.fn(), error: null };
vi.mock("@/lib/profile", () => ({
  useProfileMutations: () => ({ addSkill: { mutate: vi.fn(), error: null }, removeSkill }),
}));
vi.mock("@/components/profile/RolePicker", () => ({ RolePicker: () => <div /> }));
vi.mock("@/components/StandardPicker", () => ({ StandardPicker: () => <div /> }));

const profile = {
  skills: [
    { skill: { slug: "hand-hygiene", name: "Hand hygiene" }, proficiency: 4, source: "self_declared" },
    { skill: { slug: "bed-making", name: "Bed making" }, proficiency: 3, source: "certified" },
  ],
} as unknown as Profile;

beforeEach(() => {
  resetWorld();
  removeSkill.mutate.mockReset();
});

/** Sprint 86, BL-19.16: the skill row's remove control was 18 px tall and one of sixty identical names. */
describe("SkillsSection: the remove control", () => {
  it("is named for its skill and contains the visible word", () => {
    renderUi(<SkillsSection profile={profile} />);
    const first = screen.getByRole("button", { name: "Remove: Hand hygiene" });
    expect(first.textContent).toBe("Remove");
    expect(screen.getByRole("button", { name: "Remove: Bed making" })).toBeTruthy();
  });

  it("is 44 px tall", () => {
    renderUi(<SkillsSection profile={profile} />);
    for (const b of screen.getAllByRole("button", { name: /^Remove: / })) expect(b.className).toContain("min-h-11");
  });

  it("removes the skill it belongs to", () => {
    renderUi(<SkillsSection profile={profile} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove: Bed making" }));
    expect(removeSkill.mutate).toHaveBeenCalledWith("bed-making");
  });
});
