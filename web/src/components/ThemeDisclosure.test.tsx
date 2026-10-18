// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderUi } from "@/test/harness";

import { ThemeDisclosure } from "./ThemeDisclosure";

const read = (name: string) => readFileSync(join(__dirname, name), "utf8");

/** What the footer renders: a summary handed to the client wrapper as its child. */
const Disclosure = () => (
  <ThemeDisclosure>
    <summary className="min-h-11">Appearance</summary>
  </ThemeDisclosure>
);

describe("ThemeDisclosure", () => {
  it("is closed to begin with, and the switch is not in the page until it is opened", () => {
    renderUi(<Disclosure />);
    expect((screen.getByText("Appearance").closest("details") as HTMLDetailsElement).open).toBe(false);
    expect(screen.queryByRole("group", { name: "Appearance" })).toBeNull();
  });

  it("opening it brings in the three choices", async () => {
    renderUi(<Disclosure />);
    const details = screen.getByText("Appearance").closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    await waitFor(() => expect(screen.getByRole("group", { name: "Appearance" })).toBeTruthy());
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual(["Match device", "Light", "Dark"]);
  });

  it("the footer's own summary is a 44 px target", () => {
    expect(read("Footer.tsx")).toMatch(/<summary className="flex min-h-11 /);
  });
});

describe("the first-load budget (a source guard: jsdom cannot measure bytes)", () => {
  it("the footer holds the disclosure, never the switch itself", () => {
    const footer = read("Footer.tsx");
    expect(footer).toContain("ThemeDisclosure");
    expect(footer).not.toMatch(/from "@\/components\/ThemeSwitcher"/);
  });

  it("the disclosure reaches the switch only through a dynamic import", () => {
    const source = read("ThemeDisclosure.tsx");
    expect(source).not.toMatch(/^import .*ThemeSwitcher/m);
    expect(source).toMatch(/import\("\.\/ThemeSwitcher"\)/);
  });
});
