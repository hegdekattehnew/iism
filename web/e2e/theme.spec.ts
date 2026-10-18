import { checkPage, expect, test } from "./support/test";

/**
 * Journey 15 (Sprint 78, ADR-087, BL-19.8). A person overrides the device's colour scheme from the
 * footer; the choice is on the page before the first paint on the next load, the address bar follows,
 * and returning to "Match device" hands the page back to the device.
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

test("a person chooses a theme against the device, it survives a reload with no flash, and the device can have it back", async ({
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
  expect(await backgroundOf(page), "the device is dark and nothing was chosen").toBe(BACKGROUND.dark);
  const group = await appearance(page);
  await expect(group.getByRole("button", { name: "Match device" })).toHaveAttribute("aria-pressed", "true");

  // Light against a dark device.
  await group.getByRole("button", { name: "Light" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(await backgroundOf(page)).toBe(BACKGROUND.light);
  await expect(group.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator('meta[name="theme-color"]').first()).toHaveAttribute("content", "#f8f9fa");

  // Reloaded: it is the first thing on the page, not a correction after a dark flash.
  await page.reload();
  expect(await page.evaluate(() => (window as unknown as { __themeAtBody?: string | null }).__themeAtBody)).toBe("light");
  expect(await backgroundOf(page)).toBe(BACKGROUND.light);
  await checkPage(page, "a chosen light theme on a dark device", { light: true });

  // Dark against a light device, on another page of the site.
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/en/jobs");
  expect(await backgroundOf(page), "the choice follows the person from page to page").toBe(BACKGROUND.light);
  await (await appearance(page)).getByRole("button", { name: "Dark" }).click();
  expect(await backgroundOf(page)).toBe(BACKGROUND.dark);
  await expect(page.locator('meta[name="theme-color"]').first()).toHaveAttribute("content", "#111417");
  await checkPage(page, "a chosen dark theme on a light device", { light: true });

  // Back to the device: the override is gone and the media query decides again.
  await (await appearance(page)).getByRole("button", { name: "Match device" }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  expect(await backgroundOf(page)).toBe(BACKGROUND.light);
  await page.emulateMedia({ colorScheme: "dark" });
  expect(await backgroundOf(page)).toBe(BACKGROUND.dark);
});
