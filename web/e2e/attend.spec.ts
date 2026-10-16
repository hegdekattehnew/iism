import { E2E } from "../playwright.config";
import { checkPage, expect, test } from "./support/test";
import {
  COLLECT_BLOOD,
  addSkill,
  organisation,
  publishedCourse,
  publishedJob,
  seekerTokens,
  signInAs,
  SKILL_STERILE_FIELD,
  suffix,
} from "./support/identities";

/**
 * Journey 11 (Sprint 58, BL-14.6). A recommendation is only help if the person can act on it. Three
 * courses teach the one standard a candidate in Bengaluru lacks: one in their own district, one in
 * another district of their state, one in another state. They must be listed in that order, each
 * saying where it is, when it starts and what it costs -- and a budget must move the one they cannot
 * afford without removing it.
 */
test("the course you can take comes first, and each says where, when and what it costs", async ({
  page,
  request,
}) => {
  const id = suffix();
  const employer = await organisation(request, "employer", `E2E Hospital ${id}`);
  const provider = await organisation(request, "course_provider", `E2E Academy ${id}`);
  const jobTitle = `Theatre assistant ${id}`;
  await publishedJob(request, employer, jobTitle, [
    { skill_slug: SKILL_STERILE_FIELD, importance: 5, is_mandatory: true },
    { skill_slug: COLLECT_BLOOD, importance: 3, is_mandatory: false },
  ]);

  const local = `Sterile field, Bengaluru ${id}`;
  const sameState = `Sterile field, Kalaburagi ${id}`;
  const far = `Sterile field, Dhubri ${id}`;
  const localSlug = await publishedCourse(request, provider, local, [SKILL_STERILE_FIELD], {
    location_state: "Karnataka",
    location_district: "Bengaluru",
    starts_on: "2099-02-01",
    seats: 20,
    fee_inr: 8000,
  });
  await publishedCourse(request, provider, sameState, [SKILL_STERILE_FIELD], {
    location_state: "Karnataka",
    location_district: "Kalaburagi",
    starts_on: "2099-03-01",
    fee_inr: 3000,
  });
  await publishedCourse(request, provider, far, [SKILL_STERILE_FIELD], {
    location_state: "Assam",
    location_district: "Dhubri",
    starts_on: "2099-04-01",
    fee_inr: 1000,
  });

  // A candidate who lives in Bengaluru and holds one of the two standards.
  const seeker = await seekerTokens(request);
  const put = await request.put(`${E2E.API}/me/profile`, {
    headers: { authorization: `Bearer ${seeker.access_token}` },
    data: { location_state: "Karnataka", location_district: "Bengaluru" },
  });
  expect(put.ok()).toBeTruthy();
  await addSkill(request, seeker, COLLECT_BLOOD);

  await signInAs(page, seeker);
  await page.goto("/en/matches");
  const match = page.getByRole("listitem").filter({ hasText: jobTitle });
  await expect(match).toBeVisible();
  await match.getByRole("button", { name: "See courses that close this" }).click();

  const courseTitles = () =>
    match.getByRole("link", { name: /^Sterile field,/ }).allInnerTexts();
  await expect.poll(courseTitles).toEqual([local, sameState, far]);

  const row = (title: string) => match.getByRole("listitem").filter({ hasText: title });
  await expect(row(local)).toContainText("Bengaluru, Karnataka");
  await expect(row(local)).toContainText("Starts Feb 1, 2099");
  await expect(row(local)).toContainText("₹8,000");
  await expect(row(local)).toContainText("20 seats left");
  await expect(row(local).getByText("In your district")).toBeVisible();
  await expect(row(sameState).getByText("In your state")).toBeVisible();
  await expect(row(far).getByText("Elsewhere")).toBeVisible();
  await checkPage(page, "matches with courses you can attend");

  // A budget moves what they cannot afford down, and removes nothing.
  await match.getByLabel(/What would you pay/).fill("5000");
  await match.getByLabel(/What would you pay/).blur();
  await expect.poll(courseTitles).toEqual([sameState, local, far]);
  await expect(row(local).getByText("Over your budget")).toBeVisible();
  await expect(row(sameState).getByText("Over your budget")).toHaveCount(0);
  await checkPage(page, "matches within a budget");

  // The course's own page says the same, and counts the places.
  await page.goto(`/en/courses/${localSlug}`);
  await expect(page.getByText("Bengaluru, Karnataka")).toBeVisible();
  await expect(page.getByText("Starts February 1, 2099")).toBeVisible();
  await expect(page.getByText("20 seats left")).toBeVisible();
  await checkPage(page, "course page with a place and an intake");
});
