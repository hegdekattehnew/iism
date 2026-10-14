import { readFileSync } from "node:fs";

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
 * Journey 13 (Sprint 60). Hiring that finishes: an employer shortlists with an interview time and
 * keeps a private note; the candidate reads the message on their application, sees an unread count
 * in the header, opens the notification page and reads it; the employer takes the applicants into
 * a spreadsheet where a withdrawn applicant is blank and a formula is not one. The note is the
 * employer's: the candidate's screens never show it, the person's own data export does.
 */
const MESSAGE = "Interview on Tuesday 14 October at 11 am, Kothrud clinic. Ask for Mr Rao.";
const NOTE = "Strong on infection control. Call back before Friday.";

test("an employer messages and annotates an applicant, exports them, and the candidate reads it all", async ({
  page,
  browser,
  request,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Clinic ${id}`);
  const title = `Phlebotomist ${id}`;
  const jobSlug = await publishedJob(request, employer, title, [
    { skill_slug: COLLECT_BLOOD, importance: 4, is_mandatory: true },
  ]);

  const candidate = await seekerTokens(request);
  const withdrawer = await seekerTokens(request);
  const joker = await seekerTokens(request);
  await applyTo(request, candidate, jobSlug);
  await applyTo(request, withdrawer, jobSlug);
  // A covering note that is a spreadsheet formula.
  await request.post(`${E2E.API}/me/applications`, {
    headers: { authorization: `Bearer ${joker.access_token}` },
    data: { job_slug: jobSlug, message: "=HYPERLINK(\"http://example.invalid\")" },
  });
  const mine = await (
    await request.get(`${E2E.API}/me/applications`, {
      headers: { authorization: `Bearer ${withdrawer.access_token}` },
    })
  ).json();
  await request.post(`${E2E.API}/me/applications/${mine[0].id}/withdraw`, {
    headers: { authorization: `Bearer ${withdrawer.access_token}` },
  });

  // ---- the employer answers one applicant with a message and keeps a note
  await signInAs(page, employer.tokens);
  await page.goto(`/en/employer/${employer.slug}/jobs/${jobSlug}/applications`);
  const rows = page.getByRole("listitem").filter({ hasText: "Message for this person" });
  await expect(rows).toHaveCount(2); // the withdrawn applicant cannot be messaged

  // The candidate we will follow is the one whose contact shows their own phone; find them by it.
  const me = await (
    await request.get(`${E2E.API}/auth/me`, { headers: { authorization: `Bearer ${candidate.access_token}` } })
  ).json();
  const row = page.getByRole("listitem").filter({ hasText: me.phone });
  await row.getByLabel(/Message for this person/).fill(MESSAGE);
  await row.getByLabel("Your private note").fill(NOTE);
  await row.getByRole("button", { name: "Save note" }).click();
  await row.getByRole("button", { name: "Shortlist" }).click();
  await expect(row.getByText(MESSAGE)).toBeVisible(); // "You told them"
  await expect(row.getByLabel(/Message for this person/)).toHaveValue("");
  await checkPage(page, "employer inbox with a message and a note");
  await page.reload();
  await expect(row.getByLabel("Your private note")).toHaveValue(NOTE);

  // ---- the spreadsheet: a withdrawn applicant is blank, a formula is not one
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download as spreadsheet" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe(`applicants-${jobSlug}.csv`);
  const csv = readFileSync(await download.path(), "utf8");
  const lines = csv.replace(/^﻿/, "").trim().split(/\r?\n/);
  expect(lines[0]).toContain("your_private_note");
  expect(lines).toHaveLength(4);
  const withdrawn = lines.find((l) => l.includes(",withdrawn,"))!;
  expect(withdrawn.startsWith("C-")).toBeTruthy();
  expect(withdrawn).not.toContain("+91");
  expect(csv).toContain(NOTE);
  expect(csv).toContain("'=HYPERLINK");
  expect(csv).not.toMatch(/(^|,)=HYPERLINK/m);

  // ---- the candidate: the message on the application, a count, the page, read one
  const seeker = await (await browser.newContext()).newPage();
  await watch(seeker, E2E.API);
  await signInAs(seeker, candidate);
  await seeker.goto("/en/applications");
  await expect(seeker.getByText(MESSAGE)).toBeVisible();
  await expect(seeker.getByText(/A message from E2E Clinic/)).toBeVisible();
  await expect(seeker.getByText(NOTE)).toHaveCount(0);
  await expect(seeker.getByRole("link", { name: "Updates 1 unread" })).toBeVisible();
  await checkPage(seeker, "my applications with the employer's message");

  await seeker.getByRole("link", { name: "Updates 1 unread" }).click();
  await expect(seeker.getByText(/left you a message/)).toBeVisible();
  await expect(seeker.getByText(MESSAGE)).toHaveCount(0); // the notice says there is one, not what it says
  await checkPage(seeker, "notification page with an unread notice");
  await seeker.getByRole("button", { name: "Mark as read" }).click();
  await expect(seeker.getByRole("link", { name: "Updates", exact: true })).toBeVisible();
  await expect(seeker.getByText("Everything read")).toBeVisible();

  // ---- the person's own export carries what was said to them and written about them
  const exported = await (
    await request.get(`${E2E.API}/me/account/export`, {
      headers: { authorization: `Bearer ${candidate.access_token}` },
    })
  ).json();
  const application = exported.applications.find((a: { vacancy: string }) => a.vacancy === title);
  expect(application.employer_message).toBe(MESSAGE);
  expect(application.employer_notes).toBe(NOTE);
  await seeker.context().close();
});
