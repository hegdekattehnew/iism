import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Sprint 96: who runs a centre is fetched when the fold is first opened, not with the centres page,
 * and the manager's page does not import the organisation's list to read a table (ADR-097). jsdom
 * cannot measure bytes, so these are source guards, comments stripped first (a doc comment naming
 * `next/dynamic` had kept a mutant alive in Sprint 93).
 */
const strip = (file: string) =>
  readFileSync(join(__dirname, file), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");

const panel = strip("CentresPanel.tsx");
const workspace = strip("CentreWorkspace.tsx");

describe("the centres page and the manager's page keep to their own chunks", () => {
  it("loads who runs a centre with next/dynamic, never statically", () => {
    expect(panel).not.toMatch(/^import \{[^}]*\bCentreStaff\b[^}]*\} from/m);
    expect(panel).toMatch(
      /^const CentreStaff = dynamic\(\s*\(\) => import\("@\/components\/employer\/CentreStaff"\)/m,
    );
  });

  it("mounts it only after the fold has been opened", () => {
    expect(panel).toMatch(/\{opened && \(/);
    expect(panel).toMatch(/onToggle=/);
  });

  it("the manager's page reads the state table from its own module, not from the list", () => {
    expect(workspace).not.toMatch(/from "@\/components\/employer\/CentresPanel"/);
    expect(workspace).toMatch(/from "@\/components\/cards\/centre-look"/);
  });

  it("and the guard can fail: a static import is found by its pattern", () => {
    const bad = 'import { CentreStaff } from "@/components/employer/CentreStaff";\n';
    expect(/^import \{[^}]*\bCentreStaff\b[^}]*\} from/m.test(bad)).toBe(true);
  });
});
