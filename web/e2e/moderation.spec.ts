import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E } from "../playwright.config";
import { checkPage, expect, test, watch } from "./support/test";
import {
  COLLECT_BLOOD,
  applyTo,
  organisation,
  publishedJob,
  seekerTokens,
  signInAs,
  suffix,
} from "./support/identities";

/**
 * Journey 12 (Sprint 59, BL-14.4). A candidate reports a vacancy that asks for money. A support
 * operator sees it, masked, and cannot remove anything; an admin removes it with a reason. The
 * organisation is told why and cannot put it back, the applicant who was waiting sees it is gone
 * and is not sent to a dead page, and an admin restores it so the owner can publish again.
 */
const REPO = path.resolve(__dirname, "..", "..");

function grantStaff(address: string, tier: "support" | "admin"): void {
  execFileSync(
    path.join(REPO, ".venv", "bin", "python"),
    ["scripts/grant_staff.py", address, "--tier", tier, "--apply"],
    {
      cwd: REPO,
      env: { ...process.env, DATABASE_URL: E2E.database, REDIS_URL: E2E.redis, ENVIRONMENT: "test" },
      stdio: "pipe",
    },
  );
}

test("a reported vacancy is removed by an admin, the people it touched are told, and it can come back", async ({
  page,
  browser,
  request,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Agency ${id}`);
  const title = `Data entry from home ${id}`;
  const jobSlug = await publishedJob(request, employer, title, [
    { skill_slug: COLLECT_BLOOD, importance: 3, is_mandatory: true },
  ]);
  const job = await (await request.get(`${E2E.API}/jobs/${jobSlug}`)).json();

  const applicant = await seekerTokens(request);
  await applyTo(request, applicant, jobSlug);

  // ---- a candidate reports it, from the vacancy's own page
  const reporter = await seekerTokens(request);
  const reporterPage = await (await browser.newContext()).newPage();
  await watch(reporterPage, E2E.API);
  await signInAs(reporterPage, reporter);
  await reporterPage.goto(`/en/jobs/${jobSlug}`);
  await reporterPage.getByRole("button", { name: "Report this vacancy" }).click();
  await reporterPage.getByLabel("What is wrong?").selectOption("asks_for_money");
  await reporterPage.getByLabel(/Anything else/).fill("They asked for a registration fee on WhatsApp.");
  await checkPage(reporterPage, "report form open");
  await reporterPage.getByRole("button", { name: "Send report" }).click();
  await expect(reporterPage.getByText(/we have your report/i)).toBeVisible();
  await reporterPage.context().close();

  // ---- a stranger cannot (the page says to sign in), and the owner cannot report their own
  await page.goto(`/en/jobs/${jobSlug}`);
  await expect(page.getByRole("link", { name: "Sign in" }).last()).toBeVisible();
  expect(
    (await request.post(`${E2E.API}/jobs/${jobSlug}/report`, {
      headers: { authorization: `Bearer ${employer.tokens.access_token}` },
      data: { reason: "other" },
    })).status(),
  ).toBe(409);

  // ---- a support operator sees the report, masked, and is not offered a removal
  const support = await organisation(request, "employer", `E2E Support Desk ${id}`);
  grantStaff(support.email, "support");
  const supportPage = await (await browser.newContext()).newPage();
  await watch(supportPage, E2E.API);
  await signInAs(supportPage, support.tokens);
  await supportPage.goto("/en/admin");
  const supportRow = supportPage.getByRole("listitem").filter({ hasText: title });
  await expect(supportRow).toContainText("They asked for a registration fee on WhatsApp.");
  await expect(supportRow).toContainText("*"); // the reporter, masked
  await expect(supportRow.getByRole("button", { name: "Dismiss reports" })).toBeVisible();
  await expect(supportRow.getByRole("button", { name: "Take it down" })).toHaveCount(0);
  await supportPage.context().close();

  // ---- an admin removes it, with a reason the organisation will be shown
  const admin = await organisation(request, "employer", `E2E Admin Desk ${id}`);
  grantStaff(admin.email, "admin");
  await signInAs(page, admin.tokens);
  await page.goto("/en/admin");
  const row = page.getByRole("listitem").filter({ hasText: title });
  const takedown = row.getByRole("button", { name: "Take it down" });
  await expect(takedown).toBeDisabled();
  await row.getByLabel(/Note/).fill("It asked applicants to pay a registration fee before any interview.");
  await checkPage(page, "report queue with a report");
  await takedown.click();
  await expect(row).toHaveCount(0);

  // ---- gone from the public, and from the applicant's own list as a link
  expect((await request.get(`${E2E.API}/jobs/${jobSlug}`)).status()).toBe(404);
  const applicantPage = await (await browser.newContext()).newPage();
  await watch(applicantPage, E2E.API);
  await signInAs(applicantPage, applicant);
  await applicantPage.goto("/en/applications");
  await expect(applicantPage.getByText("Removed by our team")).toBeVisible();
  await expect(applicantPage.getByRole("link", { name: title })).toHaveCount(0);
  await checkPage(applicantPage, "my applications with a removed vacancy");
  await applicantPage.context().close();

  // ---- the owner is told, can still edit, and cannot publish
  const ownerPage = await (await browser.newContext()).newPage();
  await watch(ownerPage, E2E.API);
  await signInAs(ownerPage, employer.tokens);
  await ownerPage.goto(`/en/employer/${employer.slug}`);
  const card = ownerPage.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Removed", { exact: true })).toBeVisible();
  await expect(card).toContainText("It asked applicants to pay a registration fee");
  await expect(card.getByRole("button", { name: "Publish" })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Edit" })).toBeVisible();
  await checkPage(ownerPage, "owner workspace with a removed vacancy");
  const refused = await request.post(`${E2E.API}/org/${employer.slug}/jobs/${jobSlug}/publish`, {
    headers: { authorization: `Bearer ${employer.tokens.access_token}` },
  });
  expect(refused.status()).toBe(409);

  // ---- an admin restores it as a draft; the owner publishes it again themselves
  await page.goto("/en/admin");
  await page.getByLabel("Listings", { exact: true }).selectOption("taken_down");
  const removed = page.getByRole("listitem").filter({ hasText: title });
  await expect(removed).toContainText("It asked applicants to pay a registration fee");
  await checkPage(page, "report queue, removed view");
  await removed.getByRole("button", { name: /Restore/ }).click();
  await expect(removed).toHaveCount(0);
  expect((await request.get(`${E2E.API}/jobs/${jobSlug}`)).status()).toBe(404); // a draft again

  await ownerPage.reload();
  await ownerPage.getByRole("listitem").filter({ hasText: title }).getByRole("button", { name: "Publish" }).click();
  await expect.poll(async () => (await request.get(`${E2E.API}/jobs/${jobSlug}`)).status()).toBe(200);
  expect(job.id).toBeTruthy();
});
