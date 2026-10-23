import { checkPage, expect, test, watch } from "./support/test";
import { organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 8 (Sprint 97, ADR-102). A delivering organisation asks a seller to let it deliver the
 * seller's courses, the seller approves in its own browser, and the partner sees the arrangement in
 * force. Neither can do the other's part: the partner has no Approve, and the seller has no way to ask
 * on the partner's behalf.
 */
test("a partner asks a seller to deliver its courses and the seller approves", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const seller = await organisation(request, "course_provider", `E2E Seller ${id}`, {
    sells_courses: true,
    delivers_training: false,
  });
  const partner = await organisation(request, "course_provider", `E2E Partner ${id}`, {
    sells_courses: false,
    delivers_training: true,
  });
  await signInAs(page, partner.tokens);

  // ---- the partner finds the seller by name and asks for every course
  await page.goto(`/en/employer/${partner.slug}/delivery`);
  await expect(page.getByRole("heading", { name: "Courses you deliver for others" })).toBeVisible();
  await expect(page.getByText("Organisations that deliver your courses")).toHaveCount(0);
  await page.getByLabel("Find the organisation that sells the courses").fill(`E2E Seller ${id}`);
  await page.getByRole("button", { name: new RegExp(`E2E Seller ${id}`) }).click();
  await page.getByRole("button", { name: "Send the request" }).click();
  await expect(page.getByText(/nothing changes until they approve/)).toBeVisible();
  const mine = page.getByRole("listitem").filter({ hasText: `E2E Seller ${id}` });
  await expect(mine.getByText("Waiting", { exact: true })).toBeVisible();
  // The partner can withdraw its own request but has no way to approve it.
  await expect(mine.getByRole("button", { name: /^Withdraw:/ })).toBeVisible();
  await expect(mine.getByRole("button", { name: /^Approve:/ })).toHaveCount(0);
  await checkPage(page, "delivery, partner");

  // ---- the seller, in its own browser, sees the request and approves it
  const sellerContext = await browser.newContext({ baseURL: "http://localhost:3100", locale: "en-IN" });
  const sellerPage = await sellerContext.newPage();
  await watch(sellerPage, "http://localhost:8100");
  await signInAs(sellerPage, seller.tokens);
  await sellerPage.goto(`/en/employer/${seller.slug}/delivery`);
  await expect(sellerPage.getByRole("heading", { name: "Organisations that deliver your courses" })).toBeVisible();
  const theirs = sellerPage.getByRole("listitem").filter({ hasText: `E2E Partner ${id}` });
  await theirs.getByRole("button", { name: /^Approve:/ }).click();
  await expect(theirs.getByText("In force", { exact: true })).toBeVisible();
  await checkPage(sellerPage, "delivery, seller");
  await sellerContext.close();

  // ---- the partner sees it in force, and the public page says what it may deliver
  await page.goto(`/en/employer/${partner.slug}/delivery`);
  await expect(mine.getByText("In force", { exact: true })).toBeVisible();
  await page.goto(`/en/providers/${partner.slug}`);
  await expect(page.getByText("Authorised to deliver for other organisations")).toBeVisible();
  await expect(page.getByText(`Every course of E2E Seller ${id}`)).toBeVisible();
});
