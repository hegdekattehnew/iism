import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E } from "../playwright.config";
import { checkPage, expect, test } from "./support/test";
import { COLLECT_BLOOD, organisation, publishedJob, signInAs, suffix } from "./support/identities";

/**
 * Journey 4. The back office is reachable only by an operator, and an operator is made by exactly
 * one thing: `scripts/grant_staff.py`, which needs database credentials and refuses to create an
 * account. So this journey grants authority the way production does -- by running the script -- and
 * then does what an operator is for: look at an organisation and give it a badge, with a reason.
 */
const REPO = path.resolve(__dirname, "..", "..");

function grantStaff(address: string): void {
  execFileSync(path.join(REPO, ".venv", "bin", "python"), ["scripts/grant_staff.py", address, "--tier", "admin", "--apply"], {
    cwd: REPO,
    env: { ...process.env, DATABASE_URL: E2E.database, REDIS_URL: E2E.redis, ENVIRONMENT: "test" },
    stdio: "pipe",
  });
}

test("an operator verifies an organisation with a reason; everyone else finds nothing there", async ({
  page,
  request,
}) => {
  const id = suffix();
  const target = await organisation(request, "employer", `E2E Verifiable ${id}`);
  const vacancy = await publishedJob(request, target, `Phlebotomist ${id}`, [
    { skill_slug: COLLECT_BLOOD, importance: 4, is_mandatory: true },
  ]);
  const operator = await organisation(request, "employer", `E2E Operators ${id}`);
  const api = (p: string) => `${E2E.API}${p}`;
  const as = (t: { access_token: string }) => ({ authorization: `Bearer ${t.access_token}` });

  // ---- before the grant, an organisation owner is not an operator, and cannot tell the back
  // office exists: the refusal is byte-identical to a route that does not exist (ADR-042).
  const refused = await request.get(api("/ops/organisations"), { headers: as(operator.tokens) });
  const nowhere = await request.get(api("/ops/definitely-not-a-route"), { headers: as(operator.tokens) });
  expect(refused.status()).toBe(404);
  expect(await refused.text()).toBe(await nowhere.text());

  // ---- the one way to become an operator
  grantStaff(operator.email);
  expect((await request.get(api("/ops/organisations"), { headers: as(operator.tokens) })).status()).toBe(200);

  // ---- the operator looks at the organisation and decides
  await signInAs(page, operator.tokens);
  await page.goto(`/en/admin/${target.slug}`);
  await expect(page.getByRole("heading", { name: `E2E Verifiable ${id}` })).toBeVisible();
  await expect(page.getByText("Not verified").first()).toBeVisible();

  // The note is the only record of why anyone should believe the badge: no reason, no decision.
  const grant = page.getByRole("button", { name: "Verify this organisation" });
  await expect(grant).toBeDisabled();
  await page.getByLabel("What you verified").fill("Checked the registration certificate and the hospital's licence.");
  await expect(grant).toBeEnabled();
  await checkPage(page, "operator review");
  await grant.click();
  await expect(page.getByText("Verified", { exact: true }).first()).toBeVisible();

  // ---- the badge reaches the public listing, and the decision is on the record
  const job = await (await request.get(api(`/jobs/${vacancy}`))).json();
  expect(job.tenant.is_verified).toBe(true);
  await expect(page.getByRole("listitem").filter({ hasText: /Checked the registration certificate/ })).toBeVisible();
  await checkPage(page, "operator decision recorded");
});
