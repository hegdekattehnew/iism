import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SkillBrowser } from "@/components/SkillBrowser";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

const GET = vi.fn();
vi.mock("@/lib/api", () => ({ api: { GET: (...a: unknown[]) => GET(...a) } }));

const row = (n: number, over: Record<string, unknown> = {}) => ({
  slug: `standard-${n}`,
  name: `Standard number ${n}`,
  description: `What standard ${n} says.`,
  skill_type: "technical",
  nsqf_level: 4.5,
  qp_count: 3,
  nos_code: `HSS/N${n}`,
  context: { awarding_body: "Healthcare", sector: "Healthcare", qualification_code: "HSS/Q1", qualification_name: "General Duty Assistant" },
  ...over,
});

beforeEach(() => {
  resetWorld();
  GET.mockReset();
  GET.mockImplementation(async (path: string) => {
    if (path === "/skills/facets") return { data: { types: [], levels: [] } };
    return { data: { items: [row(1), row(2, { skill_type: "core" }), row(3, { name: "Standard number 1" })], total: 3 } };
  });
});

/** Sprint 85, BL-19.15: the standards browser draws the shared card, whole (not the compact search form). */
describe("SkillBrowser", () => {
  it("draws each standard on the shared card, a second-level heading with its kind, level, usage and description", async () => {
    renderUi(<SkillBrowser />);
    expect(await screen.findByRole("heading", { level: 2, name: "Standard number 2" })).toBeTruthy();
    expect(screen.getByText("What standard 2 says.")).toBeTruthy();
    expect(screen.getAllByText("Level 4.5").length).toBe(3);
    expect(screen.getByText("Core").className).toContain("bg-warning-surface");
    expect(screen.getAllByText("3 qualifications").length).toBe(3);
  });

  it("is a link to each standard and flags two that share a name", async () => {
    renderUi(<SkillBrowser />);
    await screen.findByRole("heading", { level: 2, name: "Standard number 2" });
    const links = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.startsWith("/skills/"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/skills/standard-1", "/skills/standard-2", "/skills/standard-3"]);
    expect(screen.getAllByText("Same name as another result — compare the codes").length).toBe(1 + 1);
  });
});
