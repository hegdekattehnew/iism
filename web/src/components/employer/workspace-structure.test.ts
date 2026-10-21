import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Sprint 88, BL-19.18: `/employer/[org]` is 698,703 bytes before this sprint and the workspaces' new
 * status shapes and tiles took it to 703,701, over the 700,000 ceiling. jsdom cannot measure bytes, so
 * this is a source guard (as `admin-structure.test.ts` is): neither workspace is imported statically by
 * the page's switch, each is a module-level `next/dynamic`, and the placeholder is a `Skeleton`.
 */
const source = readFileSync(join(__dirname, "OrgWorkspace.tsx"), "utf8");

describe("OrgWorkspace keeps both workspaces out of the route's first load", () => {
  it("imports neither workspace statically", () => {
    expect(source).not.toMatch(/^import \{[^}]*\bEmployerWorkspace\b[^}]*\} from/m);
    expect(source).not.toMatch(/^import \{[^}]*\bProviderWorkspace\b[^}]*\} from/m);
  });

  it("loads each with next/dynamic, at module level, from its own file", () => {
    expect(source).toMatch(/^import dynamic from "next\/dynamic";/m);
    expect(source).toMatch(/^const EmployerWorkspace = dynamic\(\s*\(\) => import\("@\/components\/employer\/EmployerWorkspace"\)/m);
    expect(source).toMatch(/^const ProviderWorkspace = dynamic\(\s*\(\) => import\("@\/components\/employer\/ProviderWorkspace"\)/m);
  });

  it("shows a Skeleton while a workspace loads, so nothing moves when it arrives", () => {
    expect(source).toMatch(/const loading = \(\) => <Skeleton className="h-64 w-full rounded-xl" \/>;/);
    expect((source.match(/\{ loading \}/g) ?? []).length).toBe(2);
  });

  it("and the guard can fail: a static import is found by its pattern", () => {
    const bad = 'import { EmployerWorkspace } from "@/components/employer/EmployerWorkspace";\n';
    expect(/^import \{[^}]*\bEmployerWorkspace\b[^}]*\} from/m.test(bad)).toBe(true);
  });
});
