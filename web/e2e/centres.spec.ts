import { checkPage, expect, test } from "./support/test";
import { E2E } from "../playwright.config";
import { organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 7 (Sprint 95, ADR-102). A training organisation that delivers training calls out its
 * centres: it adds one, sees it on its own list, closes and reopens it, and a visitor sees the open
 * centre on the organisation's public page. An organisation that only sells courses is offered no
 * centres page at all, and says why.
 */
test("an organisation that delivers training adds a centre and the public sees it", async ({
  page,
  request,
}) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Centres ${id}`, {
    sells_courses: true,
    delivers_training: true,
  });
  await signInAs(page, org.tokens);

  // ---- the header offers Centres, and the page starts empty
  await page.goto(`/en/employer/${org.slug}/centres`);
  await expect(page.getByRole("heading", { name: "Centres", level: 1 })).toBeVisible();
  await expect(page.getByText("No centres yet")).toBeVisible();

  // ---- add one
  await page.getByRole("button", { name: "Add a centre" }).first().click();
  await page.getByLabel("Centre name").fill(`Hadapsar ${id}`);
  await page.getByLabel("Address").fill("12 Main Road");
  await page.getByLabel("State").fill("Maharashtra");
  await page.getByLabel("District").fill("Pune");
  await page.getByRole("button", { name: "Add centre" }).click();
  const card = page.getByRole("listitem").filter({ hasText: `Hadapsar ${id}` });
  await expect(card.getByText("Open", { exact: true })).toBeVisible();
  await expect(card.getByText("Address not checked yet")).toBeVisible();
  await checkPage(page, "centres list");

  // ---- a visitor sees it on the organisation's page
  await page.goto(`/en/providers/${org.slug}`);
  await expect(page.getByText(`Hadapsar ${id}`)).toBeVisible();

  // ---- close it: it leaves the public page; reopen it: it returns
  await page.goto(`/en/employer/${org.slug}/centres`);
  await page.getByRole("button", { name: `Close: Hadapsar ${id}` }).click();
  await expect(card.getByText("Closed", { exact: true })).toBeVisible();
  await page.goto(`/en/providers/${org.slug}`);
  await expect(page.getByText(`Hadapsar ${id}`)).toHaveCount(0);
  await page.goto(`/en/employer/${org.slug}/centres`);
  await page.getByRole("button", { name: `Reopen: Hadapsar ${id}` }).click();
  await expect(card.getByText("Open", { exact: true })).toBeVisible();
});

test("an organisation that only sells courses has no centres page to use", async ({ page, request }) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Seller ${id}`);
  await signInAs(page, org.tokens);
  await page.goto(`/en/employer/${org.slug}/centres`);
  await expect(page.getByText(/does not deliver training/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Centres" })).toHaveCount(0);
});

test("an organisation asks somebody to run a centre and sees the invitation waiting", async ({
  page,
  request,
}) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Staff ${id}`, {
    sells_courses: true,
    delivers_training: true,
  });
  const created = await request.post(`${E2E.API}/org/${org.slug}/centres`, {
    headers: { authorization: `Bearer ${org.tokens.access_token}` },
    data: { name: `Staffed ${id}`, state: "Maharashtra", district: "Pune" },
  });
  expect(created.ok()).toBeTruthy();
  await signInAs(page, org.tokens);

  await page.goto(`/en/employer/${org.slug}/centres`);
  const card = page.getByRole("listitem").filter({ hasText: `Staffed ${id}` });
  // The staff list is fetched only when the fold is first opened.
  await card.locator("summary", { hasText: "Who runs it" }).click();
  await expect(card.getByText(/Nobody has been asked to run this centre yet/)).toBeVisible();
  await card.getByLabel("Ask somebody to run it").fill(`manager-${id}@iism-fixtures.co.in`);
  await card.getByRole("button", { name: "Send the invitation" }).click();
  await expect(card.getByText(`manager-${id}@iism-fixtures.co.in`)).toBeVisible();
  await expect(card.getByText("Waiting", { exact: true })).toBeVisible();
  await checkPage(page, "centres list with staff");
});
