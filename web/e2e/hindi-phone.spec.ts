import hi from "../src/messages/hi.json";
import { checkPage, expect, test } from "./support/test";

/**
 * Journey 5. The target device is a low-end Android on mobile data, and Hindi is the binding
 * case: `html[lang="hi"] body { line-height: 1.7 }` makes Devanagari ~15% taller, so before
 * Sprint 16 the hero's Search button sat below the fold at 360x640 in Hindi while passing in
 * English. CLAUDE.md says to measure it before adding anything above it; this measures it for you.
 */
test.use({ viewport: { width: 360, height: 640 }, locale: "hi-IN" });

test("the Hindi homepage fits a 360x640 phone: search above the fold, nothing clipped, nothing missing", async ({
  page,
}) => {
  await page.goto("/hi");

  const search = page.getByRole("button", { name: hi.hero.searchButton, exact: true });
  await expect(search).toBeVisible();
  const box = await search.boundingBox();
  expect(box, "the Search button has a box").not.toBeNull();
  expect(box!.y + box!.height, "Search must end above the 640px fold").toBeLessThanOrEqual(640);

  // Nothing wider than the screen: an `overflow-hidden` hero hides a too-wide column without a
  // scrollbar or an error (CLAUDE.md, "two-column hero track"), so also look at the page itself.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "no horizontal scroll").toBeLessThanOrEqual(0);

  // The example searches (Sprint 70): Hindi labels, none clipped, none off the right edge, each a
  // search the corpus can answer (the query is English, the label is Hindi).
  const chips = page.getByRole("list").filter({ has: page.getByRole("link", { name: hi.hero.chip.wardBoy }) }).getByRole("link");
  await expect(chips).toHaveCount(5);
  for (const chip of await chips.all()) {
    const b = await chip.boundingBox();
    expect(b!.x + b!.width, "an example search must not run off the right edge").toBeLessThanOrEqual(360);
    expect(b!.height, "an example search is a 44px target").toBeGreaterThanOrEqual(43.5);
    expect(await chip.getAttribute("href")).toMatch(/\/search\?q=[a-z%0-9]+$/);
  }

  // The band the owner asked to be three across: two across on a phone, six tiles, none clipped.
  // One band now: the framework figures moved to About (Sprint 70).
  await expect(page.getByRole("heading", { name: hi.stats.peopleHeading })).toBeVisible();
  await expect(page.getByRole("heading", { name: hi.stats.heading })).toHaveCount(0);
  const grids = page.locator("dl");
  await expect(grids).toHaveCount(1);
  for (const grid of await grids.all()) {
    await expect(grid.locator("dt")).toHaveCount(6);
    for (const dd of await grid.locator("dd").all()) {
      await dd.scrollIntoViewIfNeeded();
      const b = await dd.boundingBox();
      expect(b!.x + b!.width, "a figure must not run off the right edge").toBeLessThanOrEqual(360);
    }
  }

  // A raw key on screen ("stats.hires") is how a missing translation shows: next-intl returns the
  // key. The count tile is the only dotted text that is legitimately on this page.
  const text = await page.locator("body").innerText();
  expect(text).not.toMatch(/\b(?:stats|hero|nav|auth|jobs|courses)\.[a-zA-Z]+/);

  await checkPage(page, "hindi homepage at 360x640");
});
