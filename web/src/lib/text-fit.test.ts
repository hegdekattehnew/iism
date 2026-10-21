import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Text that does not fit is wrapped or broken, never cut off or run off the screen (Sprint 90, BL-19.25).
 *
 * Found by loading every page at 360 px with the root font at 200%, in Hindi and Malay: the layout was
 * right at ordinary size and wrong in six places at twice the size. jsdom has no layout, so these hold
 * the *source* of each fix, and each assertion names what the fix was for. `read` fails on a path that
 * does not exist, and the last test shows the matcher can fail.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (path: string) => readFileSync(join(SRC, path), "utf8");

/** The `className` strings of a source, each with its whole attribute value. */
function classNames(source: string): string[] {
  return [...source.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)].map((m) => m[1] ?? m[2] ?? "");
}

describe("text fits at 360 px and 200% text", () => {
  it("the page breaks a word that would run off it, and lets a flex item shrink below its longest word", () => {
    const css = read("app/globals.css");
    const body = [...css.matchAll(/\nbody \{[^}]*\}/g)].map((m) => m[0]).join("\n");
    expect(body).toContain("overflow-wrap: anywhere");
  });

  it("a chart's label is the information, so it wraps instead of ending in an ellipsis", () => {
    const names = classNames(read("components/charts/ranked-bar-list.tsx"));
    expect(names.length).toBeGreaterThan(3);
    expect(names.some((c) => /\btruncate\b/.test(c))).toBe(false);
  });

  it("the bottom tab bar shows the whole label and its cells may shrink", () => {
    const names = classNames(read("components/MobileTabBar.tsx"));
    expect(names.length).toBeGreaterThan(3);
    expect(names.some((c) => /\btruncate\b/.test(c))).toBe(false);
    const source = read("components/MobileTabBar.tsx");
    expect(source).toContain('<li key={key} className="min-w-0">');
    expect(source).toContain("flex min-h-16 min-w-0 flex-col");
    expect(source).toContain("h-7 w-12 max-w-full");
  });

  it("a match card's score drops under the title when there is no room beside it", () => {
    const source = read("components/MatchBrowser.tsx");
    expect(source).toMatch(/flex flex-wrap items-start justify-between gap-3">\s*<div className="min-w-0 grow basis-40">/);
  });

  it("an applicant's chips wrap inside their own group", () => {
    for (const file of ["components/employer/EmployerInbox.tsx", "components/employer/ProviderInterestSummary.tsx"]) {
      expect(read(file), file).toContain("flex max-w-full shrink-0 flex-wrap items-center gap-2");
    }
  });

  it("a profile row's Edit and Remove wrap, and the confidence label may wrap beside its select", () => {
    expect(read("components/profile/fields.tsx")).toContain("ml-auto flex max-w-full shrink-0 flex-wrap gap-1");
    for (const file of ["components/profile/SkillsSection.tsx", "components/profile/RolePicker.tsx"]) {
      const source = read(file);
      expect(source, file).not.toContain("whitespace-nowrap");
      expect(source, file).toContain("flex flex-wrap items-center gap-2 text-sm");
    }
  });

  it("the language select and the back office's filter never exceed their row", () => {
    expect(read("components/LocaleSwitcher.tsx")).toContain("min-w-0 max-w-full");
    expect(read("components/ops/GrievanceQueue.tsx")).toContain("min-h-11 max-w-full");
  });

  it("the mobile menu's workspace control wraps its label; the header's compact one truncates", () => {
    const source = read("components/ContextSwitcher.tsx");
    expect(source).toContain('stacked ? "min-w-0 text-left" : "max-w-[12rem] truncate"');
  });

  it("the matcher can fail", () => {
    expect(classNames('<p className="a truncate b" />').some((c) => /\btruncate\b/.test(c))).toBe(true);
    expect(classNames('<p className={`a ${x} min-w-0`} />').some((c) => /\bmin-w-0\b/.test(c))).toBe(true);
    expect(classNames("<p />")).toEqual([]);
    expect(() => read("components/does-not-exist.tsx")).toThrow();
  });
});
