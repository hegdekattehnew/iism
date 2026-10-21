import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOTICE_TEMPLATES_WITH_ICONS, NoticeTile } from "@/components/NoticeTile";

/** Sprint 87, BL-19.17: what kind of news a notice is, as a shape that is never the only signal. */
const shapeOf = (template: string, unread = true) => {
  const { container } = render(<NoticeTile template={template} unread={unread} />);
  return container.querySelector("svg")!.innerHTML;
};

describe("NoticeTile", () => {
  it("is hidden from a screen reader: the words are the notice", () => {
    const { container } = render(<NoticeTile template="job_alert" unread />);
    const tile = container.firstElementChild as HTMLElement;
    expect(tile.getAttribute("aria-hidden")).toBe("true");
    expect(tile.querySelector("svg")).toBeTruthy();
  });

  it("gives every kind of notice the words are written for its own shape", () => {
    const source = readFileSync(join(__dirname, "../lib/notice-text.ts"), "utf8");
    const written = [...source.matchAll(/case "([a-z_]+)":/g)].map((m) => m[1]);
    expect(written.length).toBeGreaterThanOrEqual(7);
    for (const template of written) expect(NOTICE_TEMPLATES_WITH_ICONS, template).toContain(template);
  });

  it("draws the kinds apart", () => {
    const shapes = NOTICE_TEMPLATES_WITH_ICONS.map((t) => shapeOf(t));
    expect(new Set(shapes).size).toBe(NOTICE_TEMPLATES_WITH_ICONS.length);
  });

  it("falls back to the bell for a kind nobody has drawn yet, and the bell is nobody's own", () => {
    const bell = shapeOf("something_new");
    expect(bell).toBeTruthy();
    for (const t of NOTICE_TEMPLATES_WITH_ICONS) expect(shapeOf(t)).not.toBe(bell);
  });

  it("is brand when new and neutral once read", () => {
    const fresh = render(<NoticeTile template="job_alert" unread />).container.firstElementChild as HTMLElement;
    const read = render(<NoticeTile template="job_alert" unread={false} />).container.firstElementChild as HTMLElement;
    expect(fresh.className).toContain("bg-accent-soft");
    expect(read.className).toContain("bg-surface-muted");
  });
});
