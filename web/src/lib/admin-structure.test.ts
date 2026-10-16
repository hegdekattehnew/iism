import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { DAILY_SECTIONS, FOLDED_SECTIONS } from "@/components/ops/admin-sections";

/**
 * The back office's shape, read from source (Sprint 73, UI-16): jsdom has no layout, so what a
 * restructure must not undo is stated as facts about the files.
 *
 * `/admin` was the route nearest the first-load budget (1,961 bytes of headroom). The four reference
 * panels leave its first load only if nothing imports them statically, so that is held here.
 */
const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (p: string) => readFileSync(join(SRC, p), "utf8");

const PAGE = read("app/[locale]/admin/page.tsx");
const PANELS = read("components/ops/AdminPanels.tsx");
const FOLDED_COMPONENTS = ["ProgrammeDashboard", "DistrictSkillGap", "RoleAliasEditor", "EnrolmentUpload"];

describe("the back office's structure", () => {
  it("gives every daily section its id in the page, and the nav the same list", () => {
    expect(DAILY_SECTIONS.length).toBeGreaterThanOrEqual(4); // found them before judging any
    for (const section of DAILY_SECTIONS) expect(PAGE).toContain(`sectionId("${section}")`);
    expect(PAGE).toContain("<AdminNav />");
  });

  it("gives every folded section its id in the folded panels", () => {
    expect(FOLDED_SECTIONS.length).toBe(4);
    for (const section of FOLDED_SECTIONS) expect(PANELS).toContain(`sectionId("${section}")`);
  });

  it("opens the daily queues on the page and folds only the reference panels", () => {
    for (const component of ["OperatorDashboard", "VerificationQueue", "GrievanceQueue", "ReportQueue"]) {
      expect(PAGE).toContain(`<${component} />`);
    }
    for (const component of FOLDED_COMPONENTS) expect(PAGE).not.toContain(`<${component}`);
  });

  it("loads the folded panels with next/dynamic and never imports them statically", () => {
    expect(PANELS).toContain('from "next/dynamic"');
    for (const component of FOLDED_COMPONENTS) {
      expect(PANELS, component).toMatch(new RegExp(`import\\("\\./${component}"\\)`));
      expect(PANELS, component).not.toMatch(new RegExp(`^import .*${component}`, "m"));
      expect(PAGE, component).not.toMatch(new RegExp(`^import .*${component}`, "m"));
    }
  });
});
