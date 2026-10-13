import { checkPage, expect, test } from "./support/test";
import { CONSENT_VERSION, seekerTokens, signInAs, uniqueEmail, uniquePhone } from "./support/identities";

/**
 * Journey 8 (Sprint 56): never locked out.
 *
 * A one-time code is the only way in, so a code that never arrives, or a number that is lost, is a
 * lost user. Two halves: asking again when the code did not come, and managing the credentials on
 * an account that exists: add an email, change the phone (every other session ends, this one does
 * not), remove the email.
 *
 * The API runs with a four-second wait between two requests for one number (the product's own is
 * 30), so a countdown can be seen and waited out inside a test.
 */
const API = "http://localhost:8100";

test("a code that does not arrive can be asked for again after a short wait", async ({ page }) => {
  const phone = uniquePhone();
  await page.goto("/en/signup/seeker");
  await page.getByLabel("Mobile number").fill(phone);
  await page.getByRole("checkbox", { name: /privacy notice/ }).check();
  await page.getByRole("button", { name: "Send the code" }).click();

  // The control is there, and it is honest: it says how long, and it is not pressable yet.
  const resend = page.getByRole("button", { name: /^Send a new code in \d+s$/ });
  await expect(resend).toBeVisible();
  await expect(resend).toBeDisabled();
  await checkPage(page, "sign-up code step, counting down");

  // After the wait it is an ordinary button, and pressing it sends another code.
  const ready = page.getByRole("button", { name: "Send a new code", exact: true });
  await expect(ready).toBeEnabled({ timeout: 10_000 });
  await ready.click();
  await expect(page.getByRole("button", { name: /^Send a new code in \d+s$/ })).toBeVisible();

  // The new code is the one that works.
  const notice = await page.getByText(/Development only — your code is \d{6}/).innerText();
  await page.getByLabel("Six-digit code").fill(notice.match(/\d{6}/)![0]);
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await expect(page.getByRole("heading", { name: "About you" }).first()).toBeVisible();
});

test("add an email, change the phone, remove the email: every other session ends and this one stays", async ({
  page,
  request,
}) => {
  const phone = uniquePhone();
  const tokens = await seekerTokens(request, phone);
  await signInAs(page, tokens);

  // A second device signs in with the same number (after the wait: the same rule applies to us).
  await page.waitForTimeout(4_500);
  const second = await (
    await request.post(`${API}/auth/otp/verify`, {
      data: {
        phone,
        code: (await (await request.post(`${API}/auth/otp/request`, { data: { phone } })).json()).debug_code,
        consent_version: CONSENT_VERSION,
      },
    })
  ).json();

  await page.goto("/en/account");
  const section = page.locator("section", { hasText: "How you sign in" });
  await expect(section.getByText("Add an email address too")).toBeVisible();
  await checkPage(page, "account, phone only");

  const codeFromScreen = async () => {
    const text = await section.getByText(/Development only — your code is \d{6}/).innerText();
    return text.match(/\d{6}/)![0];
  };

  // ---- add an email
  const email = uniqueEmail("creds");
  await section.locator("li", { hasText: "Email" }).getByRole("button", { name: "Add" }).click();
  await section.getByLabel("Email address").fill(email);
  await section.getByRole("button", { name: "Send the code" }).click();
  await section.getByLabel("Six-digit code").fill(await codeFromScreen());
  await section.getByRole("button", { name: "Verify and add" }).click();
  const emailRow = section.locator("li", { hasText: "Email" });
  await expect(emailRow.getByText(email)).toBeVisible();
  await expect(emailRow.getByText("Verified")).toBeVisible();
  await expect(section.getByText("Add an email address too")).toHaveCount(0);
  await checkPage(page, "account, both credentials");

  // ---- change the phone
  const newPhone = uniquePhone();
  const phoneRow = section.locator("li", { hasText: "Phone" });
  await phoneRow.getByRole("button", { name: "Change" }).click();
  await section.getByLabel("Phone number").fill(newPhone);
  await section.getByRole("button", { name: "Send the code" }).click();
  await section.getByLabel("Six-digit code").fill(await codeFromScreen());
  await section.getByRole("button", { name: "Confirm" }).click();
  // The fact, not the click: the row shows the new number while the form is still asking for the
  // code ("We sent a code to ..."), so wait for the form to be gone, which only the answer does.
  await expect(phoneRow.getByRole("button", { name: "Change" })).toBeVisible();
  await expect(phoneRow.getByText(new RegExp(newPhone.slice(-10)))).toBeVisible();

  // The other device is signed out; this one is not.
  const stale = await request.post(`${API}/auth/refresh`, { data: { refresh_token: second.refresh_token } });
  expect(stale.status(), "the other device's session ended").toBe(401);
  await page.reload();
  await expect(section.getByText(email)).toBeVisible();
  await checkPage(page, "account, phone changed");

  // ---- remove the email: asked twice, then it is gone and the phone is the only way in
  await emailRow.getByRole("button", { name: "Remove" }).click();
  await expect(section.getByText(/Remove your email address\?/)).toBeVisible();
  await section.getByRole("button", { name: "Yes, remove it" }).click();
  await expect(emailRow.getByText("Not added")).toBeVisible();
  await expect(section.getByText("Add an email address too")).toBeVisible();
  await expect(section.getByRole("button", { name: "Remove" })).toHaveCount(0);
  await checkPage(page, "account, email removed");
});
