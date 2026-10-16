import { checkPage, expect, test } from "./support/test";
import {
  organisation,
  publishedJob,
  seekerTokens,
  signInAs,
  SKILL_STERILE_FIELD,
  suffix,
} from "./support/identities";

/**
 * Journey 13 (Sprint 74, ADR-084): candidate depth. A vacancy says when it was posted, and the
 * career page remembers the role a person confirmed.
 */
test("a vacancy that has just been published says it was posted today, on its card and its page", async ({
  page,
  request,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Posting ${id}`);
  const title = `Posted-today assistant ${id}`;
  const slug = await publishedJob(request, employer, title, [
    { skill_slug: SKILL_STERILE_FIELD, importance: 5, is_mandatory: true },
  ]);

  await page.goto(`/en/jobs?q=${encodeURIComponent(title)}`);
  const card = page.getByRole("link", { name: new RegExp(title) });
  await expect(card).toBeVisible();
  await expect(card.getByText("Posted today")).toBeVisible();
  await checkPage(page, "jobs list with a posted date");

  await page.goto(`/en/jobs/${slug}`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("Posted today")).toBeVisible();
  await checkPage(page, "vacancy with a posted date");
});

test("a person confirms the role they do now, leaves, and finds it still there", async ({
  page,
  request,
}) => {
  const tokens = await seekerTokens(request);
  await signInAs(page, tokens);

  await page.goto("/en/career-paths");
  await page.getByLabel("Your role").fill("ward boy");
  await page.getByRole("button", { name: /^General Duty Assistant/ }).first().click();
  await expect(page.getByText("Starting from")).toBeVisible();
  // A role picked for this visit is not saved until the person says so.
  await expect(page.getByText("Saved as the role you do now.")).toHaveCount(0);

  await page.getByRole("button", { name: "This is my role" }).click();
  await expect(page.getByText("Saved as the role you do now.")).toBeVisible();

  // A fresh page load, with nothing picked: the saved role is where the page starts.
  await page.goto("/en/career-paths");
  await expect(page.getByText("Saved as the role you do now.")).toBeVisible();
  await expect(page.getByText("General Duty Assistant").first()).toBeVisible();
  await checkPage(page, "career paths with a saved role");

  // And it can be forgotten in one tap; the server, not the page, holds the answer.
  await page.getByRole("button", { name: "Forget it" }).click();
  await expect
    .poll(async () => {
      const profile = await request.get("http://localhost:8100/me/profile", {
        headers: { authorization: `Bearer ${tokens.access_token}` },
      });
      return (await profile.json()).current_role_slug;
    })
    .toBeNull();
});
