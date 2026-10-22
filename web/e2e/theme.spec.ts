import { checkPage, expect, test } from "./support/test";

/**
 * Journey 15 (Sprint 78, ADR-087, BL-19.8; light by default since Sprint 92). The page is light
 * whatever the device says; a person can choose dark or "match device" from the footer; the choice is
 * on the page before the first paint on the next load, the address bar follows, and choosing light
 * forgets the choice.
 */
const BACKGROUND = { light: "rgb(248, 249, 250)", dark: "rgb(17, 20, 23)" } as const;

type Page = import("@playwright/test").Page;

const backgroundOf = (page: Page) => page.evaluate(() => getComputedStyle(document.body).backgroundColor);

/**
 * The control lives in a closed disclosure in the footer (its code is a chunk fetched on first open,
 * to keep the first load flat), so a journey opens it, and waits for the buttons, before choosing.
 */
async function appearance(page: Page) {
  const summary = page.locator("summary", { hasText: "Appearance" });
  const isOpen = await summary.evaluate((el) => (el.parentElement as HTMLDetailsElement).open);
  if (!isOpen) await summary.click(); // a second click would close it again
  const group = page.getByRole("group", { name: "Appearance" });
  await expect(group).toBeVisible();
  return group;
}

test("the page is light on a dark device, a person chooses dark with no flash, and can match the device or go back", async ({
  page,
}) => {
  // Record what <html> says the moment <body> exists: the head script has run by then or never will.
  await page.addInitScript(() => {
    const w = window as unknown as { __themeAtBody?: string | null };
    // An init script runs before <html> exists, so the observer watches the document itself.
    new MutationObserver((_records, observer) => {
      if (document.body) {
        w.__themeAtBody = document.documentElement.getAttribute("data-theme");
        observer.disconnect();
      }
    }).observe(document, { childList: true, subtree: true });
  });

  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/en");
  expect(await backgroundOf(page), "the device is dark and nothing was chosen: the page is light").toBe(BACKGROUND.light);
  await expect(page.locator('meta[name="theme-color"]').first()).toHaveAttribute("content", "#f8f9fa");
  const group = await appearance(page);
  await expect(group.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");

  // Dark, chosen, on a dark device and then after a reload.
  await group.getByRole("button", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await backgroundOf(page)).toBe(BACKGROUND.dark);
  await expect(group.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('meta[name="theme-color"]').first()).toHaveAttribute("content", "#111417");
  await page.reload();
  expect(await page.evaluate(() => (window as unknown as { __themeAtBody?: string | null }).__themeAtBody)).toBe("dark");
  expect(await backgroundOf(page)).toBe(BACKGROUND.dark);
  await checkPage(page, "a chosen dark theme", { light: true });

  // Match the device: dark while the device is dark, light when it changes.
  await (await appearance(page)).getByRole("button", { name: "Match device" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");
  expect(await backgroundOf(page)).toBe(BACKGROUND.dark);
  await page.emulateMedia({ colorScheme: "light" });
  expect(await backgroundOf(page)).toBe(BACKGROUND.light);

  // Light again: the choice is forgotten and the page stays light on a dark device.
  await (await appearance(page)).getByRole("button", { name: "Light" }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  await page.emulateMedia({ colorScheme: "dark" });
  expect(await backgroundOf(page)).toBe(BACKGROUND.light);
  await page.goto("/en/jobs");
  expect(await backgroundOf(page), "and on another page").toBe(BACKGROUND.light);
});
