import { checkPage, expect, test, watch } from "./support/test";
import { organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 14 (Sprint 75, ADR-085, BL-12.8). A provider says which qualification a course counts
 * toward, in the editor; a learner who is not signed in reads it on the card and on the course
 * page as the provider's statement; the provider can take it back.
 */
test("a provider links a course to a qualification and a learner reads it as the provider's statement", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Qualifying Academy ${id}`);
  const title = `Ward care course ${id}`;
  await signInAs(page, org.tokens);

  await page.goto(`/en/employer/${org.slug}`);
  await page.getByRole("button", { name: "New course" }).click();
  await page.getByLabel("Course title (English)").fill(title);
  await page.getByLabel("Search standards in English, Hindi or transliteration").fill("Collect blood");
  await page.getByRole("button", { name: "Add" }).first().click();

  // The qualification is optional and found by search; the hit says what it is worth (12 credits).
  await page.getByLabel("Qualification (optional)").fill("phlebotomy technician");
  await expect(page.getByText(/12 credits/)).toBeVisible();
  await page.getByRole("button", { name: /Phlebotomy Technician/ }).first().click();
  await expect(page.getByText("Phlebotomy Technician")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();

  const card = page.getByRole("listitem").filter({ hasText: title });
  await card.getByRole("button", { name: "Publish" }).click();
  await expect(card.getByText("Published", { exact: true })).toBeVisible();

  // ---- a visitor with no account: the course page says what it counts toward, and whose word it is
  const slug = (
    await (await request.get(`http://localhost:8100/courses?q=${encodeURIComponent(title)}`)).json()
  ).items[0].slug as string;
  const visitor = await browser.newContext({ baseURL: "http://localhost:3100", locale: "en-IN" });
  const visitorPage = await visitor.newPage();
  await watch(visitorPage, "http://localhost:8100");
  await visitorPage.goto(`/en/courses/${slug}`);
  await expect(visitorPage.getByText("Counts toward")).toBeVisible();
  await expect(visitorPage.getByText("Phlebotomy Technician")).toBeVisible();
  await expect(visitorPage.getByText(/Stated by the provider/)).toBeVisible();
  await checkPage(visitorPage, "course page with a qualification");

  // ---- and on the card, as a small credit chip
  await visitorPage.goto("/en/courses");
  await visitorPage.getByRole("searchbox").first().fill(title);
  const listed = visitorPage.getByRole("link", { name: new RegExp(title) });
  await expect(listed).toBeVisible();
  await expect(listed.getByText("12 credits")).toBeVisible();
  await visitor.close();

  // ---- the provider takes it back: nothing is said about it afterwards
  await page.reload();
  const again = page.getByRole("listitem").filter({ hasText: title });
  await again.getByRole("button", { name: "Edit" }).click();
  await expect(page.getByText("Phlebotomy Technician")).toBeVisible(); // it was saved
  await page.getByRole("button", { name: "Remove qualification" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect
    .poll(async () => {
      const course = await (await request.get(`http://localhost:8100/courses/${slug}`)).json();
      return course.qualification_name;
    })
    .toBeNull();
});
