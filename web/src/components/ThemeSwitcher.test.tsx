// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { THEME_KEY } from "@/lib/theme";
import { renderUi } from "@/test/harness";

import { ThemeSwitcher } from "./ThemeSwitcher";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeSwitcher", () => {
  it("is a named group of three buttons, the device first and pressed by default", () => {
    renderUi(<ThemeSwitcher />);
    expect(screen.getByRole("group", { name: "Appearance" })).toBeTruthy();
    const names = screen.getAllByRole("button").map((b) => b.textContent);
    expect(names).toEqual(["Match device", "Light", "Dark"]);
    expect(screen.getByRole("button", { name: "Match device" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("choosing dark puts it on the page, remembers it and marks the button", () => {
    renderUi(<ThemeSwitcher />);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Match device" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("coming back to the device clears the override", async () => {
    localStorage.setItem(THEME_KEY, "light");
    renderUi(<ThemeSwitcher />);
    expect(screen.getByRole("button", { name: "Light" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Match device" }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("every button is at least 44 px tall", () => {
    renderUi(<ThemeSwitcher />);
    for (const b of screen.getAllByRole("button")) expect(b.className).toContain("min-h-11");
  });
});
