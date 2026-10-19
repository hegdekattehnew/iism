import { checkPage, expect, test } from "./support/test";
import {
  addSkill,
  organisation,
  publishedCourse,
  publishedJob,
  seekerTokens,
  signInAs,
  SKILL_STERILE_FIELD,
  suffix,
} from "./support/identities";

/**
 * Journey 18 (Sprint 84, BL-19.15): the lists on the new card, the filters as a row of chips, a
 * signed-in seeker's own score on a vacancy, and a trust strip on a course. At 360x640, the phone the
 * product is for, and through `checkPage` (no console error, contrast in both themes, no layout shift).
 */
test("a visitor sees the card and the chips; a seeker sees their own score on it", async ({ page, request }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Card ${id}`);
  const title = `Scored assistant ${id}`;
  await publishedJob(request, employer, title, [
    { skill_slug: SKILL_STERILE_FIELD, importance: 5, is_mandatory: true },
  ]);

  // ---- a visitor: the card, the chips, and no score (they have none)
  await page.goto(`/en/jobs?q=${encodeURIComponent(title)}`);
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();
  await expect(card.getByText(/% match/)).toHaveCount(0);
  // the pay and the place are chips with an icon each
  await expect(card.getByText("Bengaluru, Karnataka")).toBeVisible();
  expect(await card.locator("svg").count()).toBeGreaterThanOrEqual(2);

  const filters = page.getByRole("group", { name: "Filters" });
  await expect(filters).toBeVisible();
  for (const name of ["All types", "All locations", "Sort by"]) {
    const chip = filters.getByRole("combobox", { name });
    const box = await chip.boundingBox();
    expect(box!.height, `${name} is a 44 px target`).toBeGreaterThanOrEqual(43.5);
  }
  // the filters take about one row, not a column: the first result is on the first screen
  const first = await card.boundingBox();
  expect(first!.y, "the first result starts on the first screen").toBeLessThan(640);
  await checkPage(page, "jobs list as a visitor, on the new card");

  // ---- the same list, signed in as a seeker who holds the standard: their score is on the card
  const seeker = await seekerTokens(request);
  await addSkill(request, seeker, SKILL_STERILE_FIELD);
  await signInAs(page, seeker);
  await page.goto(`/en/jobs?q=${encodeURIComponent(title)}`);
  await expect(page.getByRole("link", { name: new RegExp(title) }).getByText(/^\d+% match$/)).toBeVisible();
  await checkPage(page, "jobs list as a job seeker, with a score on the card");
});

test("a course says who is behind it and what registering costs, and where to report it", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 640 });
  const id = suffix();
  const provider = await organisation(request, "course_provider", `E2E Academy ${id}`);
  const title = `Trust strip course ${id}`;
  const slug = await publishedCourse(request, provider, title, [SKILL_STERILE_FIELD]);

  await page.goto(`/en/courses/${slug}`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  // a provider nobody has verified yet is said to be so on its own page (never on a card)
  await expect(page.getByText("Provider not yet verified")).toBeVisible();
  await expect(page.getByText(/Registering interest is free/)).toBeVisible();
  const report = page.getByRole("link", { name: "Report this course if it asks you for money." });
  const box = await report.boundingBox();
  expect(box!.height, "the report link is a 44 px target").toBeGreaterThanOrEqual(43.5);
  await report.click();
  await expect(page).toHaveURL(/#report$/);
  await checkPage(page, "course page with its trust strip");

  // The page as it loads, checked untouched: typing a search into it moves the list on purpose, and a
  // check that began before the typing would score the person's own filtering as the page jumping.
  await page.goto("/en/courses");
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  await checkPage(page, "courses list on the new card");

  await page.getByRole("searchbox").fill(title);
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();
  // the card never says a provider is unverified
  await expect(card.getByText(/verified/i)).toHaveCount(0);
  await expect(card.getByText("₹5,000")).toBeVisible();
});

/**
 * Journey 19 (Sprint 85, BL-19.15 second half): the home's icon tiles, the vacancy and course pages
 * on facts and a trust strip, search with a mark on each band, and the standards cards. At 360x640,
 * and through `checkPage` (contrast in both themes, no layout shift, targets, no console error).
 */
test("the home leads each tile with an icon, and nothing about the order of the steps is lost", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await page.goto("/en");
  await expect(page.getByRole("heading", { name: "Explore the marketplace" })).toBeVisible();
  for (const name of ["Jobs", "Courses", "Skills"]) {
    const heading = page.getByRole("heading", { level: 3, name, exact: true });
    const tile = heading.locator("xpath=..").locator("svg");
    await expect(tile, `${name} panel has its icon`).toHaveCount(1);
    const box = await tile.boundingBox();
    expect(box!.width, `${name} icon is drawn`).toBeGreaterThan(10);
  }
  const steps = page.locator("#how-it-works ol > li");
  await expect(steps).toHaveCount(4);
  for (let i = 0; i < 4; i++) {
    await expect(steps.nth(i).locator("svg")).toHaveCount(1);
    await expect(steps.nth(i).getByText(String(i + 1), { exact: true })).toBeVisible();
  }
  await checkPage(page, "home with icon tiles");
});

test("a vacancy and a course show their facts with icons, and the trust strip's link is a 44 px target", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 640 });
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Facts ${id}`);
  const jobSlug = await publishedJob(request, employer, `Facts assistant ${id}`, [
    { skill_slug: SKILL_STERILE_FIELD, importance: 5, is_mandatory: true },
  ]);
  const provider = await organisation(request, "course_provider", `E2E Facts Academy ${id}`);
  const courseSlug = await publishedCourse(request, provider, `Facts course ${id}`, [SKILL_STERILE_FIELD], {
    fee_inr: 5000,
    seats: 10,
  });

  await page.goto(`/en/jobs/${jobSlug}`);
  await expect(page.getByRole("heading", { level: 1, name: `Facts assistant ${id}` })).toBeVisible();
  const facts = page.locator("dl").first();
  await expect(facts.locator("dt svg")).toHaveCount(2);
  const report = page.getByRole("link", { name: "Report this vacancy if it asks you for money." });
  expect((await report.boundingBox())!.height, "the report link is a 44 px target").toBeGreaterThanOrEqual(43.5);
  const requirement = page.getByRole("link", { name: /Must have/ }).first();
  expect((await requirement.boundingBox())!.height, "a required standard is a 44 px row").toBeGreaterThanOrEqual(43.5);
  await checkPage(page, "vacancy page on facts and a trust strip");

  await page.goto(`/en/courses/${courseSlug}`);
  await expect(page.getByRole("heading", { level: 1, name: `Facts course ${id}` })).toBeVisible();
  await expect(page.locator("dl").first().locator("dt svg").first()).toBeVisible();
  expect(await page.locator("dl").first().locator("dt svg").count()).toBeGreaterThanOrEqual(3);
  await checkPage(page, "course page on facts and a trust strip");
});

test("search puts a mark on each band, and a standard reads the same on the browser and in search", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await page.goto("/en/search?q=nurse");
  await expect(page.getByRole("heading", { level: 2, name: /Standards/i })).toBeVisible();
  const bands = page.locator("section > div > h2");
  expect(await bands.count()).toBe(3);
  for (let i = 0; i < 3; i++) await expect(bands.nth(i).locator("svg")).toHaveCount(1);
  await checkPage(page, "search with a mark on each band");

  await page.goto("/en/skills");
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  const card = page.locator("ul > li > a[href*='/skills/']").first();
  await expect(card.locator("svg")).toHaveCount(1);
  await checkPage(page, "standards browser on the new card");
});
