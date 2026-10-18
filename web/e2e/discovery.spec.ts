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

  await page.goto("/en/courses");
  await page.getByRole("searchbox").fill(title);
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();
  // the card never says a provider is unverified
  await expect(card.getByText(/verified/i)).toHaveCount(0);
  await expect(card.getByText("₹5,000")).toBeVisible();
  await checkPage(page, "courses list on the new card");
});
