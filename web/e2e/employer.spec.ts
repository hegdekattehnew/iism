import { checkPage, expect, test } from "./support/test";
import {
  addSkill,
  applyTo,
  COLLECT_BLOOD,
  jobSlugByTitle,
  organisation,
  seekerTokens,
  signInAs,
  suffix,
  uniquePhone,
} from "./support/identities";

/**
 * Journey 2. An employer is not a job seeker: their workspace says so, a vacancy they write is a
 * draft only they can see until they publish it, and the people who reach them are shown by
 * reference until somebody applies -- the product's one deliberate disclosure.
 */
test("an employer posts, publishes, and meets candidates only by reference until one applies", async ({
  page,
  request,
}) => {
  const id = suffix();
  const org = await organisation(request, "employer", `E2E Hospital ${id}`);
  const title = `Phlebotomist ${id}`;
  await signInAs(page, org.tokens);

  // ---- the workspace is the employer's, not a job seeker's
  await page.goto(`/en/employer/${org.slug}`);
  await expect(page.getByRole("heading", { name: "Your vacancies" })).toBeVisible();
  await expect(page.getByRole("link", { name: "My matches" })).toHaveCount(0);

  // ---- write a vacancy against a real standard
  await page.getByRole("button", { name: "New vacancy" }).click();
  await page.getByLabel("Job title (English)").fill(title);
  await page.getByLabel("State").fill("Karnataka");
  await page.getByLabel("District").fill("Bengaluru");
  await page.getByLabel("Search standards in English, Hindi or transliteration").fill("Collect blood");
  await page.getByRole("button", { name: "Add" }).first().click();
  await page.getByRole("button", { name: "Save" }).click();

  // ---- a draft: on the employer's list, not on the public one
  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Draft")).toBeVisible();
  const publicBefore = await request.get(`http://localhost:8100/jobs?q=${encodeURIComponent(title)}`);
  expect((await publicBefore.json()).total).toBe(0);

  // ---- publish: now it is public
  await card.getByRole("button", { name: "Publish" }).click();
  await expect(card.getByText("Published")).toBeVisible();
  const publicAfter = await request.get(`http://localhost:8100/jobs?q=${encodeURIComponent(title)}`);
  expect((await publicAfter.json()).total).toBe(1);
  await checkPage(page, "employer workspace");

  // ---- a candidate who holds the standard exists, and has not applied
  const jobSlug = await jobSlugByTitle(request, org.tokens, org.slug, title);
  const phone = uniquePhone();
  const seeker = await seekerTokens(request, phone);
  await addSkill(request, seeker, COLLECT_BLOOD);

  // ---- the pool shows them by reference only: no name, number or address (ADR-037)
  await card.getByRole("link", { name: "See candidates" }).click();
  await expect(page.getByText(/C-[0-9A-F]{8}/).first()).toBeVisible();
  const pool = await page.locator("body").innerText();
  expect(pool, "the pool must not carry a phone number").not.toContain(phone);
  expect(pool).not.toMatch(/\+91\d{10}/);

  // ---- they apply; now the employer may reach them, because they chose to be reached
  await applyTo(request, seeker, jobSlug);
  await page.goto(`/en/employer/${org.slug}/jobs/${jobSlug}/applications`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText(`+91${phone}`)).toBeVisible();
  await page.getByRole("button", { name: "Shortlist" }).click();
  await expect(page.getByText("Shortlisted").first()).toBeVisible();
  await checkPage(page, "employer inbox");
});
