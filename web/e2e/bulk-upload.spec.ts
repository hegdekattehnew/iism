import { writeFileSync } from "node:fs";

import { checkPage, expect, test } from "./support/test";
import { jobSlugByTitle, organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 6, the screen Sprint 51 shipped with a hand-run as its only live proof. A file is
 * checked (nothing written), created as drafts nobody else can see, and published only by a second,
 * confirmed act; a bad row blocks nothing; and uploading the corrected file again creates nothing
 * twice.
 */
test("a spreadsheet becomes drafts, then published vacancies, and re-uploading duplicates nothing", async ({
  page,
  request,
}, testInfo) => {
  const id = suffix();
  const org = await organisation(request, "employer", `E2E Staffing ${id}`);
  await signInAs(page, org.tokens);

  const titles = { listed: `Lab phlebotomist ${id}`, byRole: `Phlebotomy trainee ${id}`, broken: `Broken row ${id}` };
  const file = testInfo.outputPath("vacancies.csv");
  writeFileSync(
    file,
    [
      "external_ref,title,description,state,district,employment_type,standards,job_role",
      `E2E-${id}-1,${titles.listed},Draws blood,Karnataka,Bengaluru,full_time,HC/N0001:4:M,`,
      `E2E-${id}-2,${titles.byRole},,Karnataka,Bengaluru,full_time,,Phlebotomy Technician`,
      `E2E-${id}-3,${titles.broken},,,,,NOPE/N9999,`,
    ].join("\n") + "\n",
  );
  const publicCount = async (title: string) =>
    (await (await request.get(`http://localhost:8100/jobs?q=${encodeURIComponent(title)}`)).json()).total as number;

  await page.goto(`/en/employer/${org.slug}`);
  await page.getByRole("link", { name: "Upload a spreadsheet" }).click();
  await expect(page.getByRole("heading", { name: "Upload vacancies from a spreadsheet" })).toBeVisible();

  // ---- the template is served by the API, so there is one list of columns
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download the template" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("jobs-template.csv");

  // ---- check: the review shows what would happen, and nothing is saved
  await page.getByLabel(/Your CSV file/).setInputFiles(file);
  await expect(page.getByText("Nothing has been saved yet")).toBeVisible();
  await expect(page.getByText("2 ready, 0 with a warning, 1 with a problem, 0 skipped.")).toBeVisible();
  const roleRow = page.getByRole("row").filter({ hasText: titles.byRole });
  await roleRow.getByText(/standards?$/).click();
  await expect(roleRow.getByText("from the job role").first()).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: titles.broken })).toContainText("NOPE/N9999");
  expect(await publicCount(titles.listed)).toBe(0);
  await checkPage(page, "bulk upload review");

  // ---- a file with a problem row needs it acknowledged before anything is created
  const create = page.getByRole("button", { name: "Create 2 drafts" });
  await expect(create).toBeDisabled();
  await page.getByRole("checkbox", { name: /rows with a problem will be skipped/ }).check();
  await create.click();
  await expect(page.getByText("2 drafts created.")).toBeVisible();

  // ---- drafts are invisible to everyone else until published
  expect(await publicCount(titles.listed)).toBe(0);
  expect(await publicCount(titles.byRole)).toBe(0);

  // ---- publishing is its own, confirmed act
  await page.getByRole("button", { name: "Publish these 2" }).click();
  await expect(page.getByText(/visible to everyone straight away/)).toBeVisible();
  expect(await publicCount(titles.listed), "asking is not publishing").toBe(0);
  await page.getByRole("button", { name: "Yes, publish" }).click();
  await expect(page.getByText("2 published, 0 not published.")).toBeVisible();
  expect(await publicCount(titles.listed)).toBe(1);
  expect(await publicCount(titles.byRole)).toBe(1);
  expect(await publicCount(titles.broken)).toBe(0);
  await checkPage(page, "bulk upload published");

  // ---- the same file again: nothing is created twice
  await page.getByRole("button", { name: "Upload another file" }).click();
  await page.getByLabel(/Your CSV file/).setInputFiles(file);
  await expect(page.getByText("0 ready, 0 with a warning, 1 with a problem, 2 skipped.")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: titles.listed })).toContainText(/already exists/);
  expect(await publicCount(titles.listed)).toBe(1);

  // ---- a corrected file may *update* what was uploaded, but only when asked, only by reference,
  // and a live listing is changed only after the person has said they know it is live
  const corrected = testInfo.outputPath("vacancies-corrected.csv");
  writeFileSync(
    corrected,
    [
      "external_ref,title,description,state,district,employment_type,standards,job_role",
      `E2E-${id}-1,${titles.listed},Draws blood and labels every sample,Karnataka,Bengaluru,full_time,HC/N0001:4:M,`,
      `E2E-${id}-2,${titles.byRole},,Karnataka,Bengaluru,full_time,,Phlebotomy Technician`,
      `E2E-${id}-3,${titles.broken},,,,,NOPE/N9999,`,
    ].join("\n") + "\n",
  );
  const slug = await jobSlugByTitle(request, org.tokens, org.slug, titles.listed);
  const description = async () =>
    ((await (await request.get(`http://localhost:8100/jobs/${slug}`)).json()).description as string) ?? "";

  await page.getByRole("button", { name: "Upload another file" }).click();
  await page.getByLabel(/Your CSV file/).setInputFiles(corrected);
  // Without the box ticked a matching reference is still only skipped, and nothing changes.
  await expect(page.getByText("0 ready, 0 with a warning, 1 with a problem, 2 skipped.")).toBeVisible();
  expect(await description()).toBe("Draws blood");

  await page.getByRole("checkbox", { name: /Also update listings I uploaded before/ }).check();
  await expect(page.getByText("0 ready, 0 with a warning, 1 with a problem, 1 skipped, 1 to update.")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: titles.listed })).toContainText(/will update .*\(live/);
  await expect(page.getByRole("row").filter({ hasText: titles.byRole })).toContainText(/unchanged/);
  await checkPage(page, "bulk upload update review");

  const update = page.getByRole("button", { name: "Update 1" });
  await expect(update).toBeDisabled();
  await page.getByRole("checkbox", { name: /rows with a problem will be skipped/ }).check();
  await expect(update, "a live listing needs its own acknowledgement").toBeDisabled();
  await page.getByRole("checkbox", { name: /of these is live/ }).check();
  await update.click();

  await expect(page.getByText("1 listing updated.")).toBeVisible();
  expect(await description()).toBe("Draws blood and labels every sample");
  expect(await publicCount(titles.listed), "an update neither publishes nor unpublishes").toBe(1);
  await checkPage(page, "bulk upload updated");
});
