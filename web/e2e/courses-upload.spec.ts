import { writeFileSync } from "node:fs";

import { checkPage, expect, test } from "./support/test";
import { courseSlugByTitle, organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 7. The provider's side of Sprint 51's upload screen, which until now had a unit test and
 * a hand-run and nothing in a browser: a spreadsheet of courses becomes drafts, then published
 * courses, a corrected file updates a live course only when asked, and nothing is made twice.
 */
test("a provider uploads courses as drafts, publishes them, and later updates one by reference", async ({
  page,
  request,
}, testInfo) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Training ${id}`);
  await signInAs(page, org.tokens);

  const titles = { listed: `Blood collection ${id}`, byRole: `Phlebotomy basics ${id}`, broken: `Broken course ${id}` };
  const header = "external_ref,title,description,mode,language,duration_hours,fee_inr,nsqf_level,standards,job_role";
  const write = (name: string, fee: string) => {
    const file = testInfo.outputPath(name);
    writeFileSync(
      file,
      [
        header,
        `E2E-${id}-1,${titles.listed},Hands-on,offline,both,100,${fee},4,HC/N0001:4,`,
        `E2E-${id}-2,${titles.byRole},,hybrid,hi,80,,,,Phlebotomy Technician`,
        `E2E-${id}-3,${titles.broken},,offline,both,,,,NOPE/N9999,`,
      ].join("\n") + "\n",
    );
    return file;
  };
  const file = write("courses.csv", "5000");
  const publicCount = async (title: string) =>
    (await (await request.get(`http://localhost:8100/courses?q=${encodeURIComponent(title)}`)).json()).total as number;

  // ---- a provider's workspace offers the upload, and says "courses", never "vacancies"
  await page.goto(`/en/employer/${org.slug}`);
  await page.getByRole("link", { name: "Upload a spreadsheet" }).click();
  await expect(page.getByRole("heading", { name: "Upload courses from a spreadsheet" })).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download the template" }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("courses-template.csv");

  // ---- check: a role expands to its standards, a bad row blocks nothing, nothing is saved
  await page.getByLabel(/Your CSV file/).setInputFiles(file);
  await expect(page.getByText("2 ready, 0 with a warning, 1 with a problem, 0 skipped.")).toBeVisible();
  const roleRow = page.getByRole("row").filter({ hasText: titles.byRole });
  await roleRow.getByText(/standards?$/).click();
  await expect(roleRow.getByText("from the job role").first()).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: titles.broken })).toContainText("NOPE/N9999");
  expect(await publicCount(titles.listed)).toBe(0);
  await checkPage(page, "courses upload review");

  // ---- drafts, then a confirmed publish
  const create = page.getByRole("button", { name: "Create 2 drafts" });
  await expect(create).toBeDisabled();
  await page.getByRole("checkbox", { name: /rows with a problem will be skipped/ }).check();
  await create.click();
  await expect(page.getByText("2 drafts created.")).toBeVisible();
  expect(await publicCount(titles.listed), "drafts are not public").toBe(0);

  await page.getByRole("button", { name: "Publish these 2" }).click();
  await expect(page.getByText(/Publish 2 courses\?/)).toBeVisible();
  expect(await publicCount(titles.listed), "asking is not publishing").toBe(0);
  await page.getByRole("button", { name: "Yes, publish" }).click();
  await expect(page.getByText("2 published, 0 not published.")).toBeVisible();
  expect(await publicCount(titles.listed)).toBe(1);
  expect(await publicCount(titles.byRole)).toBe(1);
  expect(await publicCount(titles.broken)).toBe(0);
  await checkPage(page, "courses upload published");

  // ---- the same file again creates nothing; a corrected one updates a live course only on request
  await page.getByRole("button", { name: "Upload another file" }).click();
  await page.getByLabel(/Your CSV file/).setInputFiles(file);
  await expect(page.getByText("0 ready, 0 with a warning, 1 with a problem, 2 skipped.")).toBeVisible();

  const slug = await courseSlugByTitle(request, org.tokens, org.slug, titles.listed);
  const fee = async () =>
    (await (await request.get(`http://localhost:8100/courses/${slug}`)).json()).fee_inr as number;
  expect(await fee()).toBe(5000);

  await page.getByRole("button", { name: "Upload another file" }).click();
  await page.getByRole("checkbox", { name: /Also update listings I uploaded before/ }).check();
  await page.getByLabel(/Your CSV file/).setInputFiles(write("courses-corrected.csv", "4500"));
  await expect(page.getByText("0 ready, 0 with a warning, 1 with a problem, 1 skipped, 1 to update.")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: titles.listed })).toContainText(/will update .*\(live.*fee_inr/);

  await page.getByRole("checkbox", { name: /rows with a problem will be skipped/ }).check();
  await page.getByRole("checkbox", { name: /of these is live/ }).check();
  await page.getByRole("button", { name: "Update 1" }).click();
  await expect(page.getByText("1 listing updated.")).toBeVisible();
  expect(await fee()).toBe(4500);
  expect(await publicCount(titles.listed), "an update leaves it published").toBe(1);
  await checkPage(page, "courses upload updated");
});
