import { checkPage, expect, test } from "./support/test";
import {
  COLLECT_BLOOD,
  jobSlugByTitle,
  organisation,
  publishedJob,
  seekerTokens,
  signInAs,
  suffix,
} from "./support/identities";

/**
 * Journey 17 (Sprint 81, ADR-090, BL-19.13). A job seeker on a phone has a bottom bar with Jobs,
 * Courses, Matches and Profile, the current one marked; every one of their own pages is a tap away
 * without opening the account menu; signing in has a reduced header; and the bar is for a seeker
 * only, never over the apply bar and never on a laptop.
 */
test("a job seeker's pages are one tap away, with a bottom bar on a phone that is theirs alone", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 640 });
  const seeker = await seekerTokens(request);
  await signInAs(page, seeker);

  // ---- the bar: four tabs, the current one marked
  await page.goto("/en/jobs");
  const bar = page.getByRole("navigation", { name: "Main tabs" });
  await expect(bar).toBeVisible();
  await expect(bar.getByRole("link")).toHaveText(["Jobs", "Courses", "Matches", "Profile"]);
  await expect(bar.locator('[aria-current="page"]')).toHaveText("Jobs");
  await bar.getByRole("link", { name: "Matches" }).click();
  await expect(page).toHaveURL(/\/en\/matches$/);
  await expect(bar.locator('[aria-current="page"]')).toHaveText("Matches");

  // ---- the page keeps room for it from the first paint, and it sits at the bottom of the screen
  const room = await page.evaluate(() => getComputedStyle(document.body).paddingBottom);
  expect(Number.parseFloat(room), "room under the page for the bar").toBeGreaterThanOrEqual(64);
  const box = await bar.boundingBox();
  expect(Math.round(box!.y + box!.height)).toBe(640);
  await checkPage(page, "a job seeker's matches with the bottom bar");

  // ---- their own pages, without the account menu: saved jobs had no way in at all
  await page.goto("/en/saved");
  const strip = page.getByRole("navigation", { name: "Your pages" });
  await expect(strip.locator('[aria-current="page"]')).toHaveText("Saved jobs");
  for (const [name, path] of [
    ["My applications", "/applications"],
    ["Updates", "/notifications"],
    ["Saved jobs", "/saved"],
    ["My matches", "/matches"],
  ] as const) {
    await page.getByRole("navigation", { name: "Your pages" }).getByRole("link", { name }).click();
    await expect(page).toHaveURL(new RegExp(`/en${path}$`));
    await expect(page.getByRole("navigation", { name: "Your pages" }).locator('[aria-current="page"]')).toHaveText(name);
  }

  // ---- the tab for a page inside a section is the section's
  await page.goto("/en/jobs");
  await expect(bar.locator('[aria-current="page"]')).toHaveText("Jobs");

  // ---- a laptop has the header for this: the bar is not there
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(bar).toBeHidden();
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.body).paddingBottom)).toBe("0px");
});

test("the bar never covers the apply bar, is not for an organisation, and signing in has a reduced header", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Tabs Hospital ${id}`);
  await publishedJob(request, employer, `Tabs vacancy ${id}`, [{ skill_slug: COLLECT_BLOOD, importance: 4, is_mandatory: true }]);
  const slug = await jobSlugByTitle(request, employer.tokens, employer.slug, `Tabs vacancy ${id}`);

  // ---- a seeker on a short phone, on a vacancy: the apply bar rests above the tab bar
  await page.setViewportSize({ width: 360, height: 480 });
  await signInAs(page, await seekerTokens(request));
  await page.goto(`/en/jobs/${slug}`);
  const bar = page.getByRole("navigation", { name: "Main tabs" });
  await expect(bar).toBeVisible();
  const apply = page.getByTestId("apply-bar");
  await expect(apply).toBeVisible();
  const barTop = (await bar.boundingBox())!.y;
  const applyBottom = await apply.evaluate((el) => el.getBoundingClientRect().bottom);
  expect(applyBottom, "the apply bar ends where the tab bar begins, not under it").toBeLessThanOrEqual(barTop + 1);

  // ---- an organisation's workspace has no seeker's bar, and no room is kept for one
  const owner = await browser.newContext({ baseURL: "http://localhost:3100", viewport: { width: 360, height: 640 } });
  const ownerPage = await owner.newPage();
  await signInAs(ownerPage, employer.tokens);
  await ownerPage.goto(`/en/employer/${employer.slug}`);
  await expect(ownerPage.getByRole("heading", { name: "Your vacancies" })).toBeVisible();
  await expect(ownerPage.getByRole("navigation", { name: "Main tabs" })).toHaveCount(0);
  expect(await ownerPage.evaluate(() => document.documentElement.hasAttribute("data-auth"))).toBe(false);
  await owner.close();

  // ---- signing in: the logo and the language, and nothing to leave for
  const visitor = await browser.newContext({ baseURL: "http://localhost:3100", viewport: { width: 360, height: 640 } });
  const visitorPage = await visitor.newPage();
  await visitorPage.goto("/en/signin");
  await expect(visitorPage.getByRole("link", { name: "IISM" })).toBeVisible();
  await expect(visitorPage.getByRole("button", { name: "Open menu" })).toHaveCount(0);
  await expect(visitorPage.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await expect(visitorPage.getByRole("navigation", { name: "Main tabs" })).toHaveCount(0);
  await visitor.close();
});
