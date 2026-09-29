import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Every write says something when it fails.
 *
 * Sprint 30 found eleven places where a server error reached nobody. The worst
 * were not obscure: `SkillsSection` -- the one control in the whole profile
 * that moves a match score -- had no `error`, `isError` or `onError` anywhere,
 * so hitting the sixty-standard cap produced no chip and no explanation.
 * `Notices` never read `error` at all, and openapi-fetch **resolves** on a
 * non-2xx, so `onSuccess` ran on a 500 and the button did nothing for ever.
 *
 * None of that is visible to `tsc`, to `eslint`, or to a render test that does
 * not think to make the server refuse. It is, however, a property of the
 * source: a mutation is handled when its failure can reach the screen. So this
 * reads the source, exactly as `constraints.test.ts` does for input limits.
 *
 * A mutation counts as handled when any of these is true:
 *
 *   - its `useMutation({...})` declares an `onError`;
 *   - a `.mutate(...)` call passes one;
 *   - the file reads `name.isError` or `name.error` to render something;
 *   - it is awaited as `mutateAsync` inside a `try`/`catch`.
 *
 * What this cannot check is whether the message is any *good* -- whether it is
 * the server's own sentence or a fixed line that is wrong about why. That is
 * what the component tests are for, and they assert on the server's words for
 * exactly that reason.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...sources(full));
    else if (/\.tsx?$/.test(entry) && !entry.includes(".test.")) out.push(full);
  }
  return out;
}

/** The source of the call that starts at `open` (the index of its `(`). */
function callSource(text: string, open: number): string {
  let depth = 0;
  for (let i = open; i < text.length; i += 1) {
    if (text[i] === "(") depth += 1;
    else if (text[i] === ")") {
      depth -= 1;
      if (depth === 0) return text.slice(open, i + 1);
    }
  }
  return text.slice(open);
}

type Found = { file: string; name: string; handled: boolean };

function inspect(file: string): Found[] {
  const text = readFileSync(file, "utf8");
  const rel = relative(SRC, file);

  // Which `const x = useMutation({...})` in this file declare an onError.
  const declares = new Map<string, boolean>();
  for (const m of text.matchAll(/const (\w+) = useMutation\(/g)) {
    const open = (m.index ?? 0) + m[0].length - 1;
    declares.set(m[1], callSource(text, open).includes("onError"));
  }

  const names = new Set(
    [...text.matchAll(/(\w+)\.mutate(?:Async)?\(/g)].map((m) => m[1]),
  );

  return [...names].sort().map((name) => {
    if (declares.get(name)) return { file: rel, name, handled: true };
    if (new RegExp(`\\b${name}\\.(isError|error)\\b`).test(text))
      return { file: rel, name, handled: true };
    for (const m of text.matchAll(new RegExp(`\\b${name}\\.mutate(?:Async)?\\(`, "g"))) {
      const open = (m.index ?? 0) + m[0].length - 1;
      if (callSource(text, open).includes("onError"))
        return { file: rel, name, handled: true };
    }
    // `await x.mutateAsync(...)` inside a try/catch that sets a banner is how
    // `SectionEditor` and `TagSection` report their add and update failures.
    if (text.includes(`${name}.mutateAsync`) && text.includes("catch"))
      return { file: rel, name, handled: true };
    return { file: rel, name, handled: false };
  });
}

const found = [
  ...sources(join(SRC, "components")),
  ...sources(join(SRC, "lib")),
].flatMap(inspect);

describe("every mutation can report its own failure", () => {
  it("found mutations to check in the first place", () => {
    // Without this the whole file passes for ever the day a refactor renames
    // `useMutation` or moves the components -- an empty list satisfies
    // `every()`, which is how a guard becomes decoration.
    expect(found.length).toBeGreaterThan(30);
    expect(new Set(found.map((f) => f.file)).size).toBeGreaterThan(10);
  });

  it("recognises a handled mutation, so the check is not trivially true", () => {
    // Anti-vacuity from the other side: if the matcher marked everything
    // unhandled the list above would be long and this would still pass. These
    // two are handled in different ways -- an `onError` at the call site and
    // an `isError` read at render -- so both arms are exercised.
    const handled = found.filter((f) => f.handled).map((f) => `${f.file}:${f.name}`);
    expect(handled).toContain("components/ApplyPanel.tsx:apply");
    expect(handled).toContain("components/Notices.tsx:markRead");
  });

  it("leaves no write that fails in silence", () => {
    const unhandled = found
      .filter((f) => !f.handled)
      .map((f) => `${f.file} — ${f.name} has no onError and nothing reads its error`);
    expect(unhandled).toEqual([]);
  });
});
