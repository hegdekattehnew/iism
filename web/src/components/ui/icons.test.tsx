import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import * as icons from "./icons";

const ALL = Object.entries(icons).filter(([name]) => name.endsWith("Icon")) as [
  string,
  (props: icons.IconProps) => React.ReactElement,
][];

describe("the icon set", () => {
  it("is about thirty icons, found by their exports", () => {
    expect(ALL.length).toBeGreaterThanOrEqual(30);
  });

  it("an icon beside its word is hidden from assistive technology", () => {
    const { container } = render(<icons.SearchIcon />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("role")).toBeNull();
  });

  it("an icon with a title is an image with that name", () => {
    render(<icons.BellIcon title="Updates" />);
    expect(screen.getByRole("img", { name: "Updates" })).toBeTruthy();
  });

  it("every icon draws at least one path in the text colour, on the shared grid", () => {
    for (const [name, Icon] of ALL) {
      const { container, unmount } = render(<Icon />);
      const svg = container.querySelector("svg")!;
      expect(svg.getAttribute("viewBox"), name).toBe("0 0 24 24");
      expect(svg.getAttribute("stroke"), name).toBe("currentColor");
      expect(svg.querySelectorAll("path").length, name).toBeGreaterThan(0);
      unmount();
    }
  });

  it("takes a size from the caller's class", () => {
    const { container } = render(<icons.CheckIcon className="h-3 w-3" />);
    expect(container.querySelector("svg")!.getAttribute("class")).toBe("h-3 w-3");
  });
});

/**
 * The header and footer are in every route's first load, and `/profile` is within a few kilobytes of
 * the 700,000-byte ceiling (CLAUDE.md, "The header's import graph"). The icon module is built so a
 * route pays only for the icons it imports, but its factory is shared, so importing **any** icon from a
 * component every route loads costs every route about 350 bytes plus the icon. Measured when this was
 * tried in `Header` and `ContextSwitcher`: 863 bytes on `/profile`. They keep their inline marks.
 */
describe("the shared header graph", () => {
  const read = (name: string) => readFileSync(join(__dirname, "..", name), "utf8");

  it.each(["Header.tsx", "ContextSwitcher.tsx", "AuthNav.tsx", "LocaleSwitcher.tsx", "ThemeDisclosure.tsx", "QueryProvider.tsx"])(
    "%s does not import the icon module",
    (file) => {
      expect(read(file)).not.toMatch(/components\/ui\/icons|from "\.\/ui\/icons"|from "\.\/icons"/);
    },
  );

  it("the footer reaches the icons only through the lazy switch", () => {
    expect(read("Footer.tsx")).not.toMatch(/ui\/icons/);
    expect(read("ThemeSwitcher.tsx")).toMatch(/ui\/icons/);
  });
});

