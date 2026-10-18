import { checkPage, expect, test } from "./support/test";
import { organisation, signInAs, suffix } from "./support/identities";

/**
 * Journey 16 (Sprint 79, ADR-088, BL-19.10). A problem is shown next to the field it is about: when
 * the person leaves the field (in the page's own words, with the number), and, where the server
 * refused, in the server's own words beside the field as well as in the alert at the top.
 */
test("a problem appears next to its field when it is left, and where the server refused, in the server's words", async ({
  page,
  request,
}) => {
  const org = await organisation(request, "employer", `E2E Forms Hospital ${suffix()}`);
  await signInAs(page, org.tokens);
  await page.goto(`/en/employer/${org.slug}`);
  await page.getByRole("button", { name: "New vacancy" }).click();

  const title = page.getByLabel("Job title (English)");
  await expect(title).not.toHaveAttribute("aria-invalid", "true");

  // ---- left too short: the problem, the number, and the field marked invalid
  await title.fill("ab");
  await page.getByLabel("State").click(); // leaving the title
  const problem = page.getByRole("alert").filter({ hasText: "Use at least 3 characters." });
  await expect(problem).toBeVisible();
  await expect(title).toHaveAttribute("aria-invalid", "true");
  // The control is described by it, so a screen reader reads the problem with the field.
  const described = await title.getAttribute("aria-describedby");
  expect(described).toContain((await problem.getAttribute("id")) ?? "missing");
  await checkPage(page, "a vacancy form with a field in error");

  // ---- fixing it clears it as it is fixed
  await title.fill("Phlebotomist");
  await expect(problem).toHaveCount(0);
  await expect(title).not.toHaveAttribute("aria-invalid", "true");

  // ---- the server refuses a value the browser was not asked about (validation switched off here,
  // because the browser would otherwise stop the form first): its words land beside the field
  await page.evaluate(() => {
    document.querySelector("form")!.noValidate = true;
  });
  await title.fill("ab");
  await page.getByRole("button", { name: "Save" }).click();
  const refused = page.getByRole("alert").filter({ hasText: "at least 3 characters" });
  // Once beside the field and once in the summary at the top of the form.
  await expect(refused).toHaveCount(2);
  await expect(title).toHaveAttribute("aria-invalid", "true");
  const own = await title.getAttribute("aria-describedby");
  expect(own).toBeTruthy();

  // ---- editing the field dismisses the server's message about it
  await title.fill("Phlebotomist");
  await expect(refused).toHaveCount(1); // the summary stays until the next save
  await expect(title).not.toHaveAttribute("aria-invalid", "true");
});
