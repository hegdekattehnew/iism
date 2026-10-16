import { checkPage, expect, test } from "./support/test";
import { seekerTokens, signInAs } from "./support/identities";

/**
 * Journey 9 (Sprint 72): consent you can withdraw without deleting anything.
 *
 * The privacy notice used to say withdrawing consent *was* deleting the account. Now a person pauses
 * it from their Account page, sees what the pause takes back before confirming, finds the account
 * paused wherever they go, and switches it back on by confirming the notice again. The server's own
 * answer is read at each step (the screen saying it is not the same as it being true).
 */
const API = "http://localhost:8100";

test("withdraw consent from the account page, find the account paused, and switch it back on", async ({
  page,
  request,
}) => {
  const tokens = await seekerTokens(request);
  const asked = (path: string) =>
    request.get(`${API}${path}`, { headers: { authorization: `Bearer ${tokens.access_token}` } });
  await signInAs(page, tokens);

  await page.goto("/en/account");
  await expect(page.getByText(/You agreed to the privacy notice of/)).toBeVisible();
  await expect(page.getByText(/This is a pause, not an erasure/)).toBeVisible();
  await checkPage(page, "account, consent given");

  // ---- two steps: what it takes back is shown before the button that does it
  await page.getByRole("button", { name: "Withdraw my consent…" }).click();
  await expect(page.getByText(/No employer or training provider holds your contact/)).toBeVisible();
  await expect(page.getByText(/Employers no longer see you in their candidates/)).toBeVisible();
  expect((await (await asked("/me/account/consent")).json()).withdrawn).toBe(false); // looking changed nothing
  await checkPage(page, "account, withdrawal preview");

  await page.getByRole("button", { name: "Withdraw my consent", exact: true }).click();
  await expect(page.getByText(/You withdrew your consent on/)).toBeVisible();
  await expect.poll(async () => (await (await asked("/me/account/consent")).json()).withdrawn).toBe(true);
  await checkPage(page, "account, withdrawn");

  // ---- paused wherever they go: the notice says so, and the server refuses a new disclosure
  await page.goto("/en/matches");
  await expect(page.getByText("Your account is paused")).toBeVisible();
  const applied = await request.post(`${API}/me/applications`, {
    headers: { authorization: `Bearer ${tokens.access_token}` },
    data: { job_slug: "no-such-vacancy" },
  });
  expect([404, 409]).toContain(applied.status()); // 409 when the vacancy exists; never a 201
  await checkPage(page, "matches, paused");

  // ---- confirm the notice again from the banner: switched back on
  await page.getByRole("button", { name: "Confirm and switch back on" }).click();
  await expect(page.getByText("Your account is paused")).toHaveCount(0);
  await expect.poll(async () => (await (await asked("/me/account/consent")).json()).withdrawn).toBe(false);
  const me = await (await asked("/auth/me")).json();
  expect(me.consent_current).toBe(true);
  expect(me.consent_withdrawn).toBe(false);
});
