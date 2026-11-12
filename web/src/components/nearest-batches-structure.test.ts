import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Sprint 101: the nearest-batches block (its query, its types, the card pieces) cost `/matches` and
 * `/applications` about 7 KB when it was imported statically by `SuggestedCourses`, and it is only
 * needed once a gap has courses. jsdom cannot measure bytes, so this is a source guard in the shape
 * of `workspace-structure.test.ts`: a module-level `next/dynamic`, and a placeholder that holds the
 * block's room.
 */
const source = readFileSync(join(__dirname, "SuggestedCourses.tsx"), "utf8");

describe("SuggestedCourses keeps the nearest batches out of the route's first load", () => {
  it("does not import the block or its query statically", () => {
    expect(source).not.toMatch(/^import \{[^}]*\bNearestBatches\b[^}]*\} from/m);
    expect(source).not.toMatch(/from "@\/lib\/batches"/);
  });

  it("loads it with next/dynamic at module level, with the block's own skeleton as its place", () => {
    expect(source).toMatch(/^import dynamic from "next\/dynamic";/m);
    expect(source).toMatch(
      /^const NearestBatches = dynamic\(\s*\(\) => import\("@\/components\/NearestBatches"\)/m,
    );
    expect(source).toMatch(/loading: \(\) => <Skeleton className="mt-3 h-16 w-full rounded-lg" \/>/);
  });

  it("and the guard can fail: a static import is found by its pattern", () => {
    const bad = 'import { NearestBatches } from "@/components/NearestBatches";\n';
    expect(/^import \{[^}]*\bNearestBatches\b[^}]*\} from/m.test(bad)).toBe(true);
  });
});
