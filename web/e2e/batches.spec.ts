import { checkPage, expect, test } from "./support/test";
import {
  addCentre,
  authoriseDelivery,
  COLLECT_BLOOD,
  organisation,
  publishedCourse,
  signInAs,
  suffix,
} from "./support/identities";

const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);

/**
 * Journey 9 (Sprint 98, ADR-103). A delivering organisation cannot plan a batch of somebody else's
 * course until that seller authorises it; once it does, the organisation plans a batch at one of its
 * centres, publishes it, and cancels it (asked first). An organisation that only sells courses has no
 * batches page to use.
 */
test("a delivering organisation plans, publishes and cancels a batch of a course it was authorised for", async ({
  page,
  request,
}) => {
  const id = suffix();
  const seller = await organisation(request, "course_provider", `E2E Batch Seller ${id}`, {
    sells_courses: true,
    delivers_training: false,
  });
  const partner = await organisation(request, "course_provider", `E2E Batch Partner ${id}`, {
    sells_courses: false,
    delivers_training: true,
  });
  const title = `Welding ${id}`;
  await publishedCourse(request, seller, title, [COLLECT_BLOOD]);
  await addCentre(request, partner, `Hadapsar ${id}`);
  await signInAs(page, partner.tokens);

  // ---- nothing to teach yet: the page says why and where to go
  await page.goto(`/en/employer/${partner.slug}/batches`);
  await expect(page.getByRole("heading", { name: "Batches", level: 1 })).toBeVisible();
  await expect(page.getByText("No batches yet")).toBeVisible();
  await expect(page.getByText(/no course to teach yet/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Plan a batch" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open delivery" })).toBeVisible();

  // ---- the seller authorises the partner, and the course is on offer
  await authoriseDelivery(request, seller, partner.slug);
  await page.goto(`/en/employer/${partner.slug}/batches`);
  await page.getByRole("button", { name: "Plan a batch" }).first().click();
  await page.getByLabel("Course", { exact: true }).selectOption({ label: `${title} (by E2E Batch Seller ${id})` });
  await page.getByLabel("Centre", { exact: true }).selectOption({ label: `Hadapsar ${id}` });
  await page.getByLabel("Name for this batch").fill("Morning batch");
  await page.getByLabel("First day").fill(inDays(14));
  await page.getByLabel("Last day").fill(inDays(44));
  await page.getByLabel("Seats", { exact: true }).fill("25");
  await page.getByLabel("Fee for this batch (₹)").fill("3500");
  await page.getByRole("button", { name: "Plan batch" }).click();

  // ---- it is a draft, named for both organisations, with the centre's own fee
  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Draft", { exact: true })).toBeVisible();
  await expect(card.getByText(`Course by E2E Batch Seller ${id}`)).toBeVisible();
  await expect(card.getByText(`Delivered by E2E Batch Partner ${id} at Hadapsar ${id}`)).toBeVisible();
  await expect(card.getByText("₹3,500")).toBeVisible();
  await expect(card.getByText("Fee set by the centre")).toBeVisible();
  await checkPage(page, "batches, a draft");

  // ---- publish it: it is open, with every seat free
  await card.getByRole("button", { name: `Publish: ${title}` }).click();
  await expect(card.getByText("Open", { exact: true })).toBeVisible();
  await expect(card.getByText("25 of 25 seats left")).toBeVisible();
  await expect(card.getByRole("button", { name: /^Publish:/ })).toHaveCount(0);

  // ---- cancelling asks first, then it is cancelled and the list can be filtered to it
  await card.locator("summary", { hasText: "More" }).click();
  await card.getByRole("button", { name: `Cancel batch: ${title}` }).click();
  await expect(card.getByText(/Nobody has registered for it/)).toBeVisible();
  await card.getByRole("button", { name: "Yes, cancel it" }).click();
  await expect(card.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(card.getByText("Cancelled by your organisation.")).toBeVisible();
  await page.getByRole("combobox", { name: "Show batches" }).selectOption("open");
  await expect(page.getByText("No batches like this")).toBeVisible();
  await page.getByRole("combobox", { name: "Show batches" }).selectOption("cancelled");
  await expect(page.getByRole("listitem").filter({ hasText: title })).toBeVisible();
});

test("an organisation that only sells courses has no batches page to use", async ({ page, request }) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Seller Only ${id}`);
  await signInAs(page, org.tokens);
  await page.goto(`/en/employer/${org.slug}/batches`);
  await expect(page.getByText(/does not deliver training/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Batches" })).toHaveCount(0);
});
