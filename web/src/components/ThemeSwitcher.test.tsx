// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";

import { THEME_KEY } from "@/lib/theme";
import messages from "@/messages/en.json";
import { renderUi } from "@/test/harness";

import { ThemeSwitcher } from "./ThemeSwitcher";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeSwitcher", () => {
  it("is a named group of three buttons, light first and pressed by default", () => {
    renderUi(<ThemeSwitcher />);
    expect(screen.getByRole("group", { name: "Appearance" })).toBeTruthy();
    const names = screen.getAllByRole("button").map((b) => b.textContent);
    expect(names).toEqual(["Light", "Dark", "Match device"]);
    expect(screen.getByRole("button", { name: "Light" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("choosing dark puts it on the page, remembers it and marks the button", () => {
    renderUi(<ThemeSwitcher />);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Light" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("choosing light again clears the choice, because light is the default", async () => {
    localStorage.setItem(THEME_KEY, "dark");
    renderUi(<ThemeSwitcher />);
    expect(screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("match device is its own stored choice", () => {
    renderUi(<ThemeSwitcher />);
    fireEvent.click(screen.getByRole("button", { name: "Match device" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("system");
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
  });

  it("every button is at least 44 px tall", () => {
    renderUi(<ThemeSwitcher />);
    for (const b of screen.getAllByRole("button")) expect(b.className).toContain("min-h-11");
  });

  it("is rendered on the server with light pressed, whatever this browser has stored", () => {
    // The server cannot read the browser's storage, so what it draws is the default; the client
    // corrects it on hydration. A server that drew "match device" would flash on every load.
    localStorage.setItem(THEME_KEY, "dark");
    const html = renderToString(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ThemeSwitcher />
      </NextIntlClientProvider>,
    );
    const pressed = [...html.matchAll(/<button[^>]*aria-pressed="(true|false)"[^>]*>(?:<svg.*?<\/svg>)?([^<]*)</g)].map(
      (m) => `${m[2]}:${m[1]}`,
    );
    expect(pressed).toEqual(["Light:true", "Dark:false", "Match device:false"]);
  });
});
