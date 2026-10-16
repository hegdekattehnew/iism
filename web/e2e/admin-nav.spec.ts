import { checkPage, expect, test } from "./support/test";
import { grantStaff, organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 10 (Sprint 73, UI-16): the back office is something you can move around.
 *
 * `/admin` was one scroll of thirty-one screens. Now the three queues an operator works every day
 * are open at the top, four reference panels fold away and load only when opened, and a nav jumps
 * between them. What has to stay true: a folded panel costs no request until it is opened, an
 * anchor into one opens it, and the support tier is offered nothing it cannot use.
 */
const REFERENCE_REQUESTS = /\/ops\/(programmes|districts|role-aliases)/;

test("a folded panel loads only when opened, and the nav opens one", async ({ page, request }) => {
  const id = suffix();
  const operator = await organisation(request, "employer", `E2E Back Office ${id}`);
  grantStaff(operator.email, "admin");
  await signInAs(page, operator.tokens);

  const reference: string[] = [];
  page.on("request", (r) => {
    if (REFERENCE_REQUESTS.test(r.url())) reference.push(r.url());
  });

  await page.goto("/en/admin");
  // The daily work is on the page already: no click first.
  await expect(page.getByRole("heading", { name: "Verification queue" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Grievances", exact: false }).first()).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Back office sections" });
  await expect(nav.getByRole("link")).toHaveCount(8); // admin tier: enrolment is offered
  await page.waitForLoadState("networkidle");
  expect(reference, "a folded panel asked for its data before it was opened").toEqual([]);
  await checkPage(page, "back office, panels folded");

  // The nav lands on the folded panel and opens it, which mounts it and loads its data.
  await nav.getByRole("link", { name: "Aliases" }).click();
  await expect(page).toHaveURL(/#admin-aliases$/);
  await expect(page.getByRole("heading", { name: "Role search aliases" })).toBeVisible();
  await expect.poll(() => reference.some((u) => /role-aliases/.test(u))).toBe(true);
  expect(reference.some((u) => /\/ops\/(programmes|districts)/.test(u))).toBe(false); // only that one

  // A pasted address does the same: an anchor never lands on a closed row.
  await page.goto("/en/admin#admin-programmes");
  await expect(page.locator("details#admin-programmes")).toHaveAttribute("open", "");
  await checkPage(page, "back office, one panel opened by its address");
});

test("a support-tier operator is offered no enrolment, in the nav or the page", async ({ page, request }) => {
  const id = suffix();
  const support = await organisation(request, "employer", `E2E Support Desk ${id}`);
  grantStaff(support.email, "support");
  await signInAs(page, support.tokens);
  await page.goto("/en/admin");
  const nav = page.getByRole("navigation", { name: "Back office sections" });
  await expect(nav.getByRole("link")).toHaveCount(7);
  await expect(nav.getByRole("link", { name: "Enrolment" })).toHaveCount(0);
  await expect(page.locator("details#admin-enrolment")).toHaveCount(0);
});
