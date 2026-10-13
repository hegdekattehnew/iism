import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E } from "../playwright.config";
import { checkPage, expect, test, watch } from "./support/test";
import { organisation, seekerTokens, signInAs, suffix } from "./support/identities";

/**
 * Journey 7 (Sprint 57, BL-14.3). The grievance page promised an answer within 24 hours and had
 * nothing behind it. This sends one the way a person does, and answers it the way an operator
 * does: a stranger and a signed-in person each write in, the operator sees both with the account
 * masked, acknowledges one and resolves it, and the sender sees where it stands.
 */
const REPO = path.resolve(__dirname, "..", "..");

function grantStaff(address: string): void {
  execFileSync(
    path.join(REPO, ".venv", "bin", "python"),
    ["scripts/grant_staff.py", address, "--tier", "admin", "--apply"],
    {
      cwd: REPO,
      env: { ...process.env, DATABASE_URL: E2E.database, REDIS_URL: E2E.redis, ENVIRONMENT: "test" },
      stdio: "pipe",
    },
  );
}

test("a complaint is sent, answered and seen to be answered; a stranger cannot ask about data", async ({
  page,
  browser,
  request,
}) => {
  const id = suffix();
  const strangerNote = `E2E stranger ${id}: the vacancy I applied to named my village in public.`;
  const seekerNote = `E2E sender ${id}: an employer kept my number after I withdrew.`;

  // ---- a stranger writes in: somewhere to reply is required, and a data request needs an account
  await page.goto("/en/grievance");
  await expect(page.getByRole("heading", { name: "Grievance redressal" })).toBeVisible();

  await page.getByLabel(/A request about my data/).check();
  await expect(page.getByText(/has to come from your account/)).toBeVisible();
  await expect(page.getByLabel(/^Your message/)).toHaveCount(0);
  await page.getByLabel(/A complaint/).check();

  const send = page.getByRole("button", { name: "Send" });
  await page.getByLabel(/^Your message/).fill(strangerNote);
  await expect(send).toBeDisabled(); // nothing to reply to
  await page.getByLabel(/^Where can we reply\?/).fill(`stranger-${id}@iism-fixtures.co.in`);
  await checkPage(page, "grievance form");
  await send.click();

  const strangerReference = (await page.getByTestId("grievance-reference").textContent())!;
  expect(strangerReference).toMatch(/^GRV-[A-Z2-9]{6}$/);
  await expect(page.getByText(/^We acknowledge it within 24 hours and aim to resolve it within 15 days/)).toBeVisible();
  await expect(page.getByText(/never send anything automatically/)).toBeVisible();
  await checkPage(page, "grievance sent (signed out)");

  // ---- the API says the same about the account the form cannot reach
  const refused = await request.post(`${E2E.API}/grievances`, {
    data: { kind: "data_request", body: "Show me everything you hold about me.", reply_to: `s-${id}@iism-fixtures.co.in` },
  });
  expect(refused.status()).toBe(401);

  // ---- a bot fills the field nobody sees: it is told it worked, and nothing is kept
  const bot = await request.post(`${E2E.API}/grievances`, {
    data: { kind: "contact", body: `E2E bot ${id} buy cheap things here`, reply_to: `bot-${id}@iism-fixtures.co.in`, website: "http://spam.example" },
  });
  expect(bot.status()).toBe(201);
  const botReference = (await bot.json()).reference as string;

  // ---- a signed-in person writes in: nothing to reply to is asked
  const seeker = await seekerTokens(request);
  const seekerPage = await (await browser.newContext()).newPage();
  const seekerContext = seekerPage.context();
  await watch(seekerPage, E2E.API);
  await signInAs(seekerPage, seeker);
  await seekerPage.goto("/en/grievance");
  await expect(seekerPage.getByLabel(/^Where can we reply\?/)).toHaveCount(0);
  await seekerPage.getByLabel(/^Your message/).fill(seekerNote);
  await seekerPage.getByRole("button", { name: "Send" }).click();
  const seekerReference = (await seekerPage.getByTestId("grievance-reference").textContent())!;
  await expect(seekerPage.getByText(/You will see where it stands/)).toBeVisible();

  // ---- the operator sees both, the account masked, the bot absent
  const operator = await organisation(request, "employer", `E2E Grievance Desk ${id}`);
  grantStaff(operator.email);
  await signInAs(page, operator.tokens);
  await page.goto("/en/admin");
  const strangerRow = page.getByRole("listitem").filter({ hasText: strangerReference });
  const seekerRow = page.getByRole("listitem").filter({ hasText: seekerReference });
  await expect(strangerRow).toContainText(`stranger-${id}@iism-fixtures.co.in`);
  await expect(seekerRow).toContainText("*"); // masked, never the full number
  await expect(seekerRow).not.toContainText(/\+91\d{10}/);
  await expect(page.getByText(botReference)).toHaveCount(0);
  await checkPage(page, "grievance queue with rows");

  // ---- acknowledge, then resolve with a reason: a reason is required
  await seekerRow.getByRole("button", { name: "Acknowledge" }).click();
  await expect(seekerRow.getByText("Acknowledged", { exact: true })).toBeVisible();
  const resolve = seekerRow.getByRole("button", { name: "Resolve" });
  await expect(resolve).toBeDisabled();
  await seekerRow.getByLabel(/Note/).fill("Wrote to the employer; they deleted the number.");
  await expect(resolve).toBeEnabled();
  await resolve.click();
  await expect(seekerRow.getByText("Wrote to the employer; they deleted the number.")).toBeVisible();
  await expect(seekerRow.getByRole("button", { name: "Resolve" })).toHaveCount(0);

  // ---- the sender sees where it stands, never the operator's note
  await seekerPage.reload();
  const mine = seekerPage.getByRole("listitem").filter({ hasText: seekerReference });
  await expect(mine.getByText("Resolved", { exact: true })).toBeVisible();
  await expect(seekerPage.getByText("they deleted the number")).toHaveCount(0);
  await checkPage(seekerPage, "my messages");
  await seekerContext.close();
});
