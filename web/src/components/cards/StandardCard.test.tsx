import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatLevel, lookalikeNames, StandardCard, type StandardRow } from "@/components/cards/StandardCard";
import { renderUi, resetWorld } from "@/test/harness";

vi.mock("@/lib/auth", async () => (await import("@/test/harness")).authMock);
vi.mock("@/lib/org", async () => (await import("@/test/harness")).orgMock);
vi.mock("@/i18n/navigation", async () => (await import("@/test/harness")).navigationMock);

beforeEach(resetWorld);

const ROW: StandardRow = {
  slug: "hss-n5113",
  name: "Clean medical equipment",
  description: "Prepare and clean the equipment a ward uses.",
  skill_type: "technical",
  nsqf_level: 4.5,
  qp_count: 3,
  nos_code: "HSS/N5113",
  context: {
    awarding_body: "Healthcare",
    sector: "Healthcare",
    qualification_code: "HSS/Q5101",
    qualification_name: "General Duty Assistant",
  },
};

/** Sprint 85, BL-19.15: a standard on the same card as a vacancy and a course. */
describe("StandardCard", () => {
  it("is one link to the standard, with a mark that is hidden from a screen reader", () => {
    const { container } = renderUi(<StandardCard row={ROW} lookalike={false} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/skills/hss-n5113");
    const mark = container.querySelector("[aria-hidden='true']") as HTMLElement;
    expect(mark.querySelector("svg")).toBeTruthy();
  });

  it("sits on the card surface with the shared shadow, so it reads as the same card as a vacancy", () => {
    renderUi(<StandardCard row={ROW} lookalike={false} />);
    const cls = screen.getByRole("link").className;
    expect(cls).toContain("shadow-card");
    expect(cls).toContain("bg-surface");
  });

  it("shows the kind and the level as chips, and how many qualifications use it", () => {
    renderUi(<StandardCard row={ROW} lookalike={false} />);
    expect(screen.getByText("Technical").className).toContain("bg-accent-soft");
    expect(screen.getByText("Level 4.5").className).toContain("bg-surface-muted");
    expect(screen.getByText(/3/, { selector: "span.text-muted" })).toBeTruthy();
  });

  it.each([
    ["technical", "bg-accent-soft"],
    ["core", "bg-warning-surface"],
    ["generic", "bg-surface-muted"],
  ] as const)("a %s standard's chip is on the %s token", (type, token) => {
    renderUi(<StandardCard row={{ ...ROW, skill_type: type }} lookalike={false} />);
    const chip = screen.getByText({ technical: "Technical", core: "Core", generic: "Generic" }[type]);
    expect(chip.className).toContain(token);
  });

  it("draws no kind chip for a row that carries no kind (search results may not)", () => {
    renderUi(<StandardCard row={{ ...ROW, skill_type: undefined }} lookalike={false} />);
    expect(screen.queryByText("Technical")).toBeNull();
    expect(screen.getByText("Level 4.5")).toBeTruthy();
  });

  it("names the code and the qualification it belongs to, and a council once", () => {
    renderUi(<StandardCard row={ROW} lookalike={false} />);
    expect(screen.getByText("HSS/N5113")).toBeTruthy();
    expect(screen.getByText("(HSS/Q5101)")).toBeTruthy();
    expect(screen.getByText("Healthcare")).toBeTruthy();
    expect(screen.queryByText("Healthcare · Healthcare")).toBeNull();
  });

  it("says outright that a name is shared, only when it is", () => {
    const on = renderUi(<StandardCard row={ROW} lookalike />);
    expect(screen.getByText("Same name as another result — compare the codes")).toBeTruthy();
    on.unmount();
    renderUi(<StandardCard row={ROW} lookalike={false} />);
    expect(screen.queryByText("Same name as another result — compare the codes")).toBeNull();
  });

  it("shows the description, and says why an alias matched (and not for another kind of match)", () => {
    const alias = renderUi(<StandardCard row={{ ...ROW, match_kind: "alias", matched_on: "ward boy" }} lookalike={false} />);
    expect(screen.getByText("Prepare and clean the equipment a ward uses.")).toBeTruthy();
    expect(screen.getByText(/ward boy/)).toBeTruthy();
    alias.unmount();
    renderUi(<StandardCard row={{ ...ROW, match_kind: "exact", matched_on: "ward boy" }} lookalike={false} />);
    expect(screen.queryByText(/ward boy/)).toBeNull();
  });

  it("is a second-level heading by default and a third under a band of its own", () => {
    const a = renderUi(<StandardCard row={ROW} lookalike={false} />);
    expect(screen.getByRole("heading", { level: 2, name: "Clean medical equipment" })).toBeTruthy();
    a.unmount();
    renderUi(<StandardCard row={ROW} lookalike={false} heading="h3" />);
    expect(screen.getByRole("heading", { level: 3, name: "Clean medical equipment" })).toBeTruthy();
  });

  it("leaves out the description and the usage count when compact, and keeps the rest", () => {
    renderUi(<StandardCard row={ROW} lookalike={false} compact />);
    expect(screen.queryByText("Prepare and clean the equipment a ward uses.")).toBeNull();
    expect(screen.queryByText(/qualifications?$/, { selector: "span.text-muted" })).toBeNull();
    expect(screen.getByText("Technical")).toBeTruthy();
    expect(screen.getByText("Level 4.5")).toBeTruthy();
    expect(screen.getByText("HSS/N5113")).toBeTruthy();
  });

  it("draws no level chip and no usage line for a standard without them", () => {
    renderUi(<StandardCard row={{ ...ROW, nsqf_level: null, qp_count: 0 }} lookalike={false} />);
    expect(screen.queryByText(/^Level/)).toBeNull();
    expect(screen.queryByText(/qualification/i, { selector: "span.text-muted" })).toBeNull();
  });
});

describe("formatLevel and lookalikeNames", () => {
  it("drops the point from a whole level and keeps a half", () => {
    expect(formatLevel(4)).toBe("4");
    expect(formatLevel(4.5)).toBe("4.5");
  });

  it("finds names that repeat as a reader would, ignoring case and stray spaces", () => {
    expect([...lookalikeNames([{ name: "Bed Making" }, { name: " bed making" }, { name: "Hand hygiene" }])]).toEqual(["bed making"]);
  });
});
