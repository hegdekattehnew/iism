import { checkPage, expect, test, watch } from "./support/test";
import {
  addSkill,
  COLLECT_BLOOD,
  courseSlugByTitle,
  organisation,
  seekerTokens,
  signInAs,
  suffix,
  uniquePhone,
} from "./support/identities";

/**
 * Journey 3. A training provider is not an employer: their workspace talks about courses, a course
 * is a draft until they publish it, and a learner's contact reaches them only because the learner
 * asked it to -- the product's second deliberate disclosure, made by the learner.
 */
test("a provider publishes a course and hears from a learner only because the learner asked", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Academy ${id}`);
  const title = `Blood collection course ${id}`;
  await signInAs(page, org.tokens);

  // ---- a provider's workspace speaks of courses, never of vacancies
  await page.goto(`/en/employer/${org.slug}`);
  await expect(page.getByRole("heading", { name: "Your courses" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New course" })).toBeVisible();
  await expect(page.getByRole("button", { name: "New vacancy" })).toHaveCount(0);

  // ---- write a course that teaches a real standard
  await page.getByRole("button", { name: "New course" }).click();
  await page.getByLabel("Course title (English)").fill(title);
  await page.getByLabel("Search standards in English, Hindi or transliteration").fill("Collect blood");
  await page.getByRole("button", { name: "Add" }).first().click();
  await page.getByRole("button", { name: "Save" }).click();

  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Draft")).toBeVisible();
  const published = async () =>
    (await (await request.get(`http://localhost:8100/courses?q=${encodeURIComponent(title)}`)).json()).total as number;
  expect(await published(), "a draft is not on the public list").toBe(0);

  await card.getByRole("button", { name: "Publish" }).click();
  await expect(card.getByText("Published")).toBeVisible();
  expect(await published()).toBe(1);
  await checkPage(page, "provider workspace");

  // ---- a learner finds it and chooses to be contacted (their own browser, their own person)
  const courseSlug = await courseSlugByTitle(request, org.tokens, org.slug, title);
  const phone = uniquePhone();
  const learner = await seekerTokens(request, phone);
  await addSkill(request, learner, COLLECT_BLOOD);
  const learnerContext = await browser.newContext({ baseURL: "http://localhost:3100", locale: "en-IN" });
  const learnerPage = await learnerContext.newPage();
  await watch(learnerPage, "http://localhost:8100");
  await signInAs(learnerPage, learner);

  await learnerPage.goto(`/en/courses/${courseSlug}`);
  await learnerPage.getByRole("button", { name: "I'm interested in this course" }).click();
  // The learner is told, before anything is shared, exactly who will see what.
  await expect(learnerPage.getByText("Before you register")).toBeVisible();
  await expect(learnerPage.getByText(/will see your name, phone number, email and district/)).toBeVisible();
  await learnerPage.getByRole("button", { name: "Register my interest" }).click();
  await expect(learnerPage.getByText("Interest registered")).toBeVisible();
  await checkPage(learnerPage, "learner course page");
  await learnerContext.close();

  // ---- now, and only now, the provider can reach them
  await page.goto(`/en/employer/${org.slug}/courses/${courseSlug}/interests`);
  await expect(page.getByText(`+91${phone}`)).toBeVisible();
  await page.getByRole("button", { name: "Mark as contacted" }).click();
  await expect(page.getByText("Contacted").first()).toBeVisible();
  await checkPage(page, "provider inbox");
});
