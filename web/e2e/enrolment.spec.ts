import { execFileSync } from "node:child_process";
import path from "node:path";

import { E2E } from "../playwright.config";
import { checkPage, expect, test } from "./support/test";
import {
  CONSENT_VERSION,
  organisation,
  seekerTokens,
  signInAs,
  suffix,
  uniquePhone,
} from "./support/identities";

/**
 * Journey 14 (Sprint 61, BL-14.10). An admin operator enrols an agency's file from the back office:
 * checks it (nothing is written, no number is shown whole), attests the notice was read out, and
 * enrols. A person who had already signed up keeps what they told us and gains only the tag; a
 * repeated number and a bad one are named; running the file again creates nobody. An enrolled
 * person then signs in by phone like anyone and finds the profile the agency gave them, and their
 * own data export says how they came to be in the programme. A support operator is not offered
 * the panel at all.
 */
const REPO = path.resolve(__dirname, "..", "..");
const api = (p: string) => `${E2E.API}${p}`;

function grantStaff(address: string, tier: "support" | "admin"): void {
  execFileSync(
    path.join(REPO, ".venv", "bin", "python"),
    ["scripts/grant_staff.py", address, "--tier", tier, "--apply"],
    {
      cwd: REPO,
      env: {
        ...process.env,
        DATABASE_URL: E2E.database,
        REDIS_URL: E2E.redis,
        ENVIRONMENT: "test",
      },
      stdio: "pipe",
    },
  );
}

test("an operator enrols an agency's file; the people can sign in; nothing is written before the attestation", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const programme = `E2E-AGENCY-${id}`;
  const fresh = uniquePhone();
  const own = uniquePhone();
  const bad = "12345";

  const admin = await organisation(
    request,
    "employer",
    `E2E Enrolment Admin ${id}`,
  );
  grantStaff(admin.email, "admin");
  const support = await organisation(
    request,
    "employer",
    `E2E Enrolment Support ${id}`,
  );
  grantStaff(support.email, "support");

  // Somebody who signed up on their own, and whom the agency's file also names.
  const ownTokens = await seekerTokens(request, own);
  await request.put(api("/me/profile"), {
    headers: { authorization: `Bearer ${ownTokens.access_token}` },
    data: { headline: "My own headline" },
  });

  const file = [
    "phone,full_name,headline,state,district,years_experience",
    `${fresh},Anita Kumari,Home health aide trainee,,,1`,
    `${own},Agency Name,Agency headline,,,0`,
    `${fresh},Anita Again,,,,`,
    `${bad},Nobody,,,,`,
  ].join("\r\n");

  await signInAs(page, admin.tokens);
  await page.goto("/en/admin");
  await expect(
    page.getByRole("heading", { name: "Enrol an agency's file" }),
  ).toBeVisible();

  // ---- nothing can be checked without a name and a file
  const check = page.getByRole("button", { name: "Check the file" });
  await expect(check).toBeDisabled();
  await page.getByLabel("Programme name").fill(programme);
  await page.getByLabel("Choose the CSV file").setInputFiles({
    name: "agency.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(file),
  });
  await expect(check).toBeEnabled();
  await check.click();

  // ---- the check says what would happen, shows no number whole, and has written nothing
  await expect(
    page.getByText(
      new RegExp(
        `${programme}: 1 new, 1 existing and tagged, 0 left alone, 2 with errors`,
      ),
    ),
  ).toBeVisible();
  await expect(page.getByText(/same number as row 2/)).toBeVisible();
  await expect(page.getByText(/not an Indian mobile number/)).toBeVisible();
  const html = await page.content();
  for (const number of [fresh, own, `+91${fresh}`, `+91${own}`])
    expect(html).not.toContain(number);
  const before = (
    await (
      await request.get(api("/ops/enrolment/batches"), {
        headers: { authorization: `Bearer ${admin.tokens.access_token}` },
      })
    ).json()
  ).batches;
  expect(
    before.some((b: { programme: string }) => b.programme === programme),
  ).toBe(false);
  await checkPage(page, "enrolment check");

  // ---- the attestation is what lets the button work
  const enrol = page.getByRole("button", { name: "Enrol 2 people" });
  await expect(enrol).toBeDisabled();
  await page.getByLabel(/privacy notice was read out/).check();
  await expect(enrol).toBeEnabled();
  await enrol.click();
  await expect(page.getByRole("heading", { name: "Enrolled" })).toBeVisible();
  await expect(page.getByText(new RegExp(`Recent enrolments`))).toBeVisible();
  await expect(
    page.getByRole("listitem").filter({ hasText: programme }).first(),
  ).toBeVisible();
  await checkPage(page, "enrolment done");

  // ---- the programme report counts them, and who attested is on the batch
  const opHeaders = { authorization: `Bearer ${admin.tokens.access_token}` };
  const report = await (
    await request.get(api(`/ops/programmes/${programme}`), {
      headers: opHeaders,
    })
  ).json();
  expect(report.enrolled).toBe(2);
  const batches = (
    await (
      await request.get(api("/ops/enrolment/batches"), { headers: opHeaders })
    ).json()
  ).batches;
  const batch = batches.find(
    (b: { programme: string }) => b.programme === programme,
  );
  expect(batch.attested_notice_version).toBe(CONSENT_VERSION);
  expect([batch.created, batch.tagged]).toEqual([1, 1]);

  // ---- the same file again creates nobody
  const again = await request.post(
    api(`/ops/enrolment/apply?programme=${programme}&attest=true`),
    {
      headers: { ...opHeaders, "content-type": "text/csv" },
      data: file,
    },
  );
  const second = await again.json();
  expect([second.new, second.tag, second.already]).toEqual([0, 0, 2]);

  // ---- an apply without the attestation is refused and writes nothing
  const refused = await request.post(
    api(`/ops/enrolment/apply?programme=${programme}-2`),
    {
      headers: { ...opHeaders, "content-type": "text/csv" },
      data: file,
    },
  );
  expect(refused.status()).toBe(422);

  // ---- the person the agency enrolled signs in like anybody and finds what the agency gave them
  const code = (
    await (
      await request.post(api("/auth/otp/request"), { data: { phone: fresh } })
    ).json()
  ).debug_code;
  const signedIn = await request.post(api("/auth/otp/verify"), {
    data: { phone: fresh, code },
  });
  expect(signedIn.status()).toBe(200);
  const enrolled = await signedIn.json();
  const as = { authorization: `Bearer ${enrolled.access_token}` };
  const profile = await (
    await request.get(api("/me/profile"), { headers: as })
  ).json();
  expect(profile.headline).toBe("Home health aide trainee");
  const theirs = await (
    await request.get(api("/me/account/export"), { headers: as })
  ).json();
  expect(theirs.agency_enrolment.programme).toBe(programme);
  expect(theirs.agency_enrolment.account_created_for_you).toBe(true);

  // ---- the person who signed up themselves kept their own words
  const mine = await (
    await request.get(api("/me/profile"), {
      headers: { authorization: `Bearer ${ownTokens.access_token}` },
    })
  ).json();
  expect(mine.headline).toBe("My own headline");

  // ---- a support operator is not offered the panel (the page itself is theirs to see)
  const other = await browser.newContext();
  const supportPage = await other.newPage();
  await signInAs(supportPage, support.tokens);
  await supportPage.goto("/en/admin");
  await expect(
    supportPage.getByRole("heading", { name: "Reported listings" }),
  ).toBeVisible();
  await expect(
    supportPage.getByRole("heading", { name: "Enrol an agency's file" }),
  ).toHaveCount(0);
  await other.close();
});
