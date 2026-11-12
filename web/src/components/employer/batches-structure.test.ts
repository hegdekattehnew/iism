import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Sprint 100: who registered interest in a batch is fetched the first time the fold is opened, so the
 * workspace route does not carry it in its first load (`/employer/[org]` has about 35 KB of room).
 * jsdom cannot measure bytes; this is a source guard in the shape of `workspace-structure.test.ts`.
 */
const source = readFileSync(join(__dirname, "BatchesPanel.tsx"), "utf8");

describe("BatchesPanel keeps the learners out of the route's first load", () => {
  it("does not import BatchLearners statically", () => {
    expect(source).not.toMatch(/^import \{[^}]*\bBatchLearners\b[^}]*\} from/m);
  });

  it("loads it with next/dynamic, at module level, from its own file, behind a Skeleton", () => {
    expect(source).toMatch(/^import dynamic from "next\/dynamic";/m);
    expect(source).toMatch(
      /^const BatchLearners = dynamic\(\s*\(\) => import\("@\/components\/employer\/BatchLearners"\)/m,
    );
    expect(source).toMatch(/loading: \(\) => <Skeleton/);
  });

  it("mounts it only after the fold has been opened, and not for a draft", () => {
    expect(source).toMatch(/\{opened && \(/);
    expect(source).toMatch(/batch\.status !== "draft" && !editing && <LearnersFold/);
  });

  it("and the guard can fail: a static import is found by its pattern", () => {
    const bad = 'import { BatchLearners } from "@/components/employer/BatchLearners";\n';
    expect(/^import \{[^}]*\bBatchLearners\b[^}]*\} from/m.test(bad)).toBe(true);
  });
});
