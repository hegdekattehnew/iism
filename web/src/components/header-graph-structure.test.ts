import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Sprint 93, BL-18.2: the first-load budget has one number that matters, `/profile`, and a modal
 * stack (Radix dialog, focus scope, dismissable layer, remove-scroll, presence) was in every
 * route's first load because the header's `ContextSwitcher` imported the create-organisation form
 * statically. jsdom cannot measure bytes, so this is a source guard (as `workspace-structure.test.ts`
 * is): nothing in the header graph imports `CreateOrgForm` or `ui/dialog`, and the switcher loads
 * the form with `next/dynamic` at module level. `npm run build:e2e && npm run budget` is the measure.
 */
const src = (p: string) => readFileSync(join(__dirname, "..", p), "utf8");
const HEADER_GRAPH = [
  "components/Header.tsx",
  "components/ContextSwitcher.tsx",
  "components/AuthNav.tsx",
  "components/LocaleSwitcher.tsx",
  "components/MobileTabBar.tsx",
];
const STATIC_IMPORT_ANY = /^import [^\n]*from "@\/components\/(CreateOrgForm|ui\/dialog)"/m;

describe("the header's import graph keeps the modal stack out of every route's first load", () => {
  it("finds the files it checks", () => {
    for (const f of HEADER_GRAPH) expect(src(f).length, f).toBeGreaterThan(200);
  });

  it("imports neither the create-organisation form nor the dialog statically", () => {
    for (const f of HEADER_GRAPH) expect(STATIC_IMPORT_ANY.test(src(f)), f).toBe(false);
  });

  it("loads the form with next/dynamic, at module level, with no server render", () => {
    // Comments stripped: the doc comment above the constant names `ssr: false` in prose.
    const s = src("components/ContextSwitcher.tsx").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(s).toMatch(/^import dynamic from "next\/dynamic";/m);
    expect(s).toMatch(/^const CreateOrgForm = dynamic\(\(\) => import\("@\/components\/CreateOrgForm"\)/m);
    expect(s).toMatch(/\{\s*ssr: false,?\s*\}\)/);
  });

  it("and the guard can fail: a static import is found by its pattern", () => {
    expect(STATIC_IMPORT_ANY.test('import { CreateOrgForm } from "@/components/CreateOrgForm";\n')).toBe(true);
    expect(STATIC_IMPORT_ANY.test('import { Dialog } from "@/components/ui/dialog";\n')).toBe(true);
    expect(STATIC_IMPORT_ANY.test('import dynamic from "next/dynamic";\n')).toBe(false);
  });
});
