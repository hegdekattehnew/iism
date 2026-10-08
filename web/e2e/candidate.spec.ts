import { checkPage, expect, test } from "./support/test";
import {
  COLLECT_BLOOD,
  organisation,
  publishedJob,
  SKILL_STERILE_FIELD,
  suffix,
  uniquePhone,
} from "./support/identities";

/**
 * Journey 1, the core loop: a person who has never used the product says what work they do,
 * ticks what they can already do, sees a vacancy ranked with the standard they are missing, and
 * applies -- sharing their contact with that employer for that vacancy only -- then takes it back.
 */
test("a new candidate signs up, names their job, sees a match with its gap, applies and withdraws", async ({
  page,
  request,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Clinic ${id}`);
  const title = `Ward assistant ${id}`;
  // They need the sterile-field standard (mandatory) and ask for blood collection (useful).
  await publishedJob(request, employer, title, [
    { skill_slug: SKILL_STERILE_FIELD, importance: 5, is_mandatory: true },
    { skill_slug: COLLECT_BLOOD, importance: 3, is_mandatory: false },
  ]);

  // ---- sign up with a phone number: a code, consent, no password
  const phone = uniquePhone();
  await page.goto("/en/signup/seeker");
  await page.getByLabel("Mobile number").fill(phone);
  // Consent is asked for first and recorded server-side on verification (DPDP): no tick, no code.
  await page.getByRole("checkbox", { name: /privacy notice/ }).check();
  await page.getByRole("button", { name: "Send the code" }).click();
  const notice = await page.getByText(/Development only — your code is \d{6}/).innerText();
  const code = notice.match(/\d{6}/)![0];
  await page.getByLabel("Six-digit code").fill(code);
  await page.getByRole("button", { name: "Verify and continue" }).click();

  // ---- a new job seeker lands in the profile wizard
  await expect(page.getByRole("heading", { name: "About you" }).first()).toBeVisible();
  await checkPage(page, "profile wizard");

  // ---- name the work in their own words; the national standards behind it appear
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("What work do you do?").fill("ward boy");
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: /^General Duty Assistant/ }).click();

  // Nothing starts ticked: a ticked default would reward acquiescence (it scores as evidence).
  const sterile = page.getByRole("checkbox", { name: /Maintain a sterile field/ });
  await expect(sterile).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Tick at least one" })).toBeDisabled();
  await sterile.check();
  await page.getByRole("button", { name: /^Add \d/ }).click();
  await expect(page.getByText("Self-declared").first()).toBeVisible();
  await checkPage(page, "profile skills");

  // ---- matches: the vacancy is ranked, with the standard they lack named
  await page.goto("/en/matches");
  const match = page.getByRole("listitem").filter({ hasText: title });
  await expect(match).toBeVisible();
  await expect(match.getByText(/\d+% match/)).toBeVisible();
  await expect(match.getByText("Collect blood samples")).toBeVisible();
  await checkPage(page, "matches");

  // ---- apply: told first exactly who will see what
  await match.getByRole("link", { name: "View the job" }).click();
  await page.getByRole("button", { name: "Apply for this job" }).click();
  await expect(page.getByText("Before you apply")).toBeVisible();
  await expect(page.getByText(new RegExp(`sends your name, mobile number and email to E2E Clinic ${id}`))).toBeVisible();
  await page.getByRole("button", { name: "Yes, apply" }).click();
  await expect(page.getByText("Applied", { exact: true })).toBeVisible();
  await checkPage(page, "job detail applied");

  // ---- the employer can now reach them, and only now (the inbox is the employer's own view)
  const seenByEmployer = async () => {
    const r = await request.get(`http://localhost:8100/org/${employer.slug}/jobs`, {
      headers: { authorization: `Bearer ${employer.tokens.access_token}` },
    });
    const jobs = (await r.json()) as { slug: string; title: string }[];
    const slug = jobs.find((j) => j.title === title)!.slug;
    const inbox = await request.get(`http://localhost:8100/org/${employer.slug}/jobs/${slug}/applications`, {
      headers: { authorization: `Bearer ${employer.tokens.access_token}` },
    });
    return (await inbox.json()).items as { contact: { phone: string } | null }[];
  };
  expect((await seenByEmployer())[0].contact?.phone).toBe(`+91${phone}`);

  // ---- withdraw: the contact goes away, the row stays
  await page.getByRole("button", { name: "Withdraw" }).click();
  // Wait for the fact, not for a button to disappear (that is true the instant it is clicked):
  // the screen stops saying "Applied", and the employer's view loses the contact details.
  await expect(page.getByText("Applied", { exact: true })).toHaveCount(0);
  await expect
    .poll(async () => (await seenByEmployer())[0]?.contact, { message: "withdrawing takes their details back" })
    .toBeNull();
  expect(await seenByEmployer(), "the row stays, so the employer's history is not rewritten").toHaveLength(1);

  // ---- their own list tells the truth about where it stands
  await page.goto("/en/applications");
  await expect(page.getByRole("listitem").filter({ hasText: title })).toBeVisible();
  await checkPage(page, "my applications");
});
