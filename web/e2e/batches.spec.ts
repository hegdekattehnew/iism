import { checkPage, expect, test, watch } from "./support/test";
import {
  addCentre,
  authoriseDelivery,
  COLLECT_BLOOD,
  namedSeeker,
  organisation,
  publishedBatch,
  publishedCourse,
  signInAs,
  suffix,
} from "./support/identities";

const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);

/**
 * Journey 9 (Sprint 98, ADR-103). A delivering organisation cannot plan a batch of somebody else's
 * course until that seller authorises it; once it does, the organisation plans a batch at one of its
 * centres, publishes it, and cancels it (asked first). An organisation that only sells courses has no
 * batches page to use.
 */
test("a delivering organisation plans, publishes and cancels a batch of a course it was authorised for", async ({
  page,
  request,
}) => {
  const id = suffix();
  const seller = await organisation(request, "course_provider", `E2E Batch Seller ${id}`, {
    sells_courses: true,
    delivers_training: false,
  });
  const partner = await organisation(request, "course_provider", `E2E Batch Partner ${id}`, {
    sells_courses: false,
    delivers_training: true,
  });
  const title = `Welding ${id}`;
  await publishedCourse(request, seller, title, [COLLECT_BLOOD]);
  await addCentre(request, partner, `Hadapsar ${id}`);
  await signInAs(page, partner.tokens);

  // ---- nothing to teach yet: the page says why and where to go
  await page.goto(`/en/employer/${partner.slug}/batches`);
  await expect(page.getByRole("heading", { name: "Batches", level: 1 })).toBeVisible();
  await expect(page.getByText("No batches yet")).toBeVisible();
  await expect(page.getByText(/no course to teach yet/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Plan a batch" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open delivery" })).toBeVisible();

  // ---- the seller authorises the partner, and the course is on offer
  await authoriseDelivery(request, seller, partner.slug);
  await page.goto(`/en/employer/${partner.slug}/batches`);
  await page.getByRole("button", { name: "Plan a batch" }).first().click();
  await page.getByLabel("Course", { exact: true }).selectOption({ label: `${title} (by E2E Batch Seller ${id})` });
  await page.getByLabel("Centre", { exact: true }).selectOption({ label: `Hadapsar ${id}` });
  await page.getByLabel("Name for this batch").fill("Morning batch");
  await page.getByLabel("First day").fill(inDays(14));
  await page.getByLabel("Last day").fill(inDays(44));
  await page.getByLabel("Seats", { exact: true }).fill("25");
  await page.getByLabel("Fee for this batch (₹)").fill("3500");
  await page.getByRole("button", { name: "Plan batch" }).click();

  // ---- it is a draft, named for both organisations, with the centre's own fee
  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Draft", { exact: true })).toBeVisible();
  await expect(card.getByText(`Course by E2E Batch Seller ${id}`)).toBeVisible();
  await expect(card.getByText(`Delivered by E2E Batch Partner ${id} at Hadapsar ${id}`)).toBeVisible();
  await expect(card.getByText("₹3,500")).toBeVisible();
  await expect(card.getByText("Fee set by the centre")).toBeVisible();
  await checkPage(page, "batches, a draft");

  // ---- publish it: it is open, with every seat free
  await card.getByRole("button", { name: `Publish: ${title}` }).click();
  await expect(card.getByText("Open", { exact: true })).toBeVisible();
  await expect(card.getByText("25 of 25 seats left")).toBeVisible();
  await expect(card.getByRole("button", { name: /^Publish:/ })).toHaveCount(0);

  // ---- cancelling asks first, then it is cancelled and the list can be filtered to it
  await card.locator("summary", { hasText: "More" }).click();
  await card.getByRole("button", { name: `Cancel batch: ${title}` }).click();
  await expect(card.getByText(/Nobody has registered for it/)).toBeVisible();
  await card.getByRole("button", { name: "Yes, cancel it" }).click();
  await expect(card.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(card.getByText("Cancelled by your organisation.")).toBeVisible();
  await page.getByRole("combobox", { name: "Show batches" }).selectOption("open");
  await expect(page.getByText("No batches like this")).toBeVisible();
  await page.getByRole("combobox", { name: "Show batches" }).selectOption("cancelled");
  await expect(page.getByRole("listitem").filter({ hasText: title })).toBeVisible();
});

test("an organisation that only sells courses has no batches page to use", async ({ page, request }) => {
  const id = suffix();
  const org = await organisation(request, "course_provider", `E2E Seller Only ${id}`);
  await signInAs(page, org.tokens);
  await page.goto(`/en/employer/${org.slug}/batches`);
  await expect(page.getByText(/does not deliver training/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Batches" })).toHaveCount(0);
});

/**
 * Journey 10 (Sprint 99, BL-18.8). A delivering organisation plans two batches from a spreadsheet:
 * the file is checked (one row names a course it may not deliver), drafts are made, and publishing is
 * its own confirmed step. Its batches page leads with the figures, and the seller sees counts of how
 * its course is being run and no learner.
 */
test("a delivering organisation plans batches from a file, publishes them, and the seller sees counts", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const seller = await organisation(request, "course_provider", `E2E File Seller ${id}`, {
    sells_courses: true,
    delivers_training: false,
  });
  const partner = await organisation(request, "course_provider", `E2E File Partner ${id}`, {
    sells_courses: false,
    delivers_training: true,
  });
  const title = `Fitting ${id}`;
  const course = await publishedCourse(request, seller, title, [COLLECT_BLOOD]);
  await addCentre(request, partner, `Kothrud ${id}`);
  await authoriseDelivery(request, seller, partner.slug);
  await signInAs(page, partner.tokens);

  const csv = [
    "course,centre,starts_on,ends_on,seats,mode,label,schedule,fee_inr",
    `${course},Kothrud ${id},${inDays(30)},${inDays(60)},25,hybrid,Morning,Mon to Fri,3500`,
    `${title},Kothrud ${id},${inDays(31)},${inDays(61)},15,,Evening,,`,
    `no-such-course,Kothrud ${id},${inDays(32)},${inDays(62)},10`,
  ].join("\r\n");

  await page.goto(`/en/employer/${partner.slug}/batches`);
  await page.getByRole("link", { name: "Add many from a file" }).click();
  await expect(page.getByRole("heading", { name: "Plan batches from a file", level: 1 })).toBeVisible();
  await page.getByLabel("A CSV file, up to 2 MB").setInputFiles({
    name: "batches.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await expect(page.getByText("2 ready, 0 to look at, 1 with a problem, 0 already planned.")).toBeVisible();
  await expect(page.getByText(/No course you may deliver is called that/)).toBeVisible();
  await checkPage(page, "batches upload, checked");

  // The problem row has to be acknowledged before anything is made.
  await expect(page.getByRole("button", { name: "Make 2 draft batches" })).toBeDisabled();
  await page.getByLabel(/1 row has a problem and will not be made/).check();
  await page.getByRole("button", { name: "Make 2 draft batches" }).click();
  await expect(page.getByText("2 draft batches made.")).toBeVisible();

  // Publishing is a separate, confirmed act.
  await page.getByRole("button", { name: "Publish these 2" }).click();
  await expect(page.getByText("Publish 2 batches?")).toBeVisible();
  await page.getByRole("button", { name: "Yes, publish" }).click();
  await expect(page.getByText("2 published, 0 not published.")).toBeVisible();

  // The list leads with the figures, and both batches are open.
  await page.goto(`/en/employer/${partner.slug}/batches`);
  await expect(page.getByText("Seats still free in batches starting within two weeks")).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: title }).getByText("Open", { exact: true })).toHaveCount(2);
  await checkPage(page, "batches, from a file");

  // The seller sees counts for its course, and the delivering organisation, and nothing else.
  const sellerContext = await browser.newContext({ baseURL: "http://localhost:3100", locale: "en-IN" });
  const sellerPage = await sellerContext.newPage();
  await watch(sellerPage, "http://localhost:8100");
  await signInAs(sellerPage, seller.tokens);
  await sellerPage.goto(`/en/employer/${seller.slug}/delivery`);
  await expect(sellerPage.getByRole("heading", { name: "How your courses are being run" })).toBeVisible();
  const row = sellerPage.getByRole("listitem").filter({ hasText: `Delivered by E2E File Partner ${id}` });
  await expect(row.getByText("2 batches")).toBeVisible();
  await expect(row.getByText("2 open")).toBeVisible();
  await sellerContext.close();
});

/**
 * Journey 11 (Sprint 100, BL-20.2, BL-20.3, BL-18.7). A learner finds the batch nearest them, is told
 * who will see their details before anything is shared, registers, and sees where it stands; the
 * centre's organisation sees them in its list, marks them enrolled, and a seat is taken.
 * **Written and not run locally (no Chromium); CI's browser job is its first run.**
 */
test("a learner finds a batch, registers interest, and the centre enrols them", async ({
  page,
  request,
  browser,
}) => {
  const id = suffix();
  const seller = await organisation(request, "course_provider", `E2E Learn Seller ${id}`, {
    sells_courses: true,
    delivers_training: false,
  });
  const partner = await organisation(request, "course_provider", `E2E Learn Partner ${id}`, {
    sells_courses: false,
    delivers_training: true,
  });
  const title = `Plumbing ${id}`;
  const course = await publishedCourse(request, seller, title, [COLLECT_BLOOD]);
  const centre = await addCentre(request, partner, `Baner ${id}`);
  await authoriseDelivery(request, seller, partner.slug);
  await publishedBatch(request, partner, { course, centre, startsInDays: 20, seats: 25 });
  const learner = await namedSeeker(request, `Asha ${id}`);
  await signInAs(page, learner);

  // ---- the list names both organisations and says how near it is, and nothing is hidden
  await page.goto(`/en/batches?course=${course}`);
  await expect(page.getByRole("heading", { name: "Batches near you", level: 1 })).toBeVisible();
  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText(`Course by E2E Learn Seller ${id}`)).toBeVisible();
  await expect(card.getByText(`Delivered by E2E Learn Partner ${id} at Baner ${id}`)).toBeVisible();
  await expect(card.getByText("In your district")).toBeVisible();
  await expect(card.getByText("25 of 25 seats left")).toBeVisible();
  await checkPage(page, "batches near you");

  // ---- the consent step names the centre and its organisation before anything is shared
  await card.getByRole("button", { name: `Register interest: ${title}` }).click();
  await expect(card.getByText(new RegExp(`Baner ${id} will see your name`))).toBeVisible();
  await expect(card.getByText(new RegExp(`E2E Learn Partner ${id}, which runs it`))).toBeVisible();
  await card.getByLabel("Anything they should know (optional)").fill("Evenings only");
  await card.getByRole("button", { name: "Register my interest" }).click();
  await expect(card.getByText("Registered", { exact: true })).toBeVisible();
  await expect(card.getByText(/Reply expected by/)).toBeVisible();

  // ---- the learner's own list has it, and says when a reply is expected
  await page.goto("/en/interests");
  await expect(page.getByRole("heading", { name: "Batches you asked about" })).toBeVisible();
  await expect(page.getByText(`Delivered by E2E Learn Partner ${id} at Baner ${id}`)).toBeVisible();
  await checkPage(page, "interests, with a batch");

  // ---- the organisation sees them, marks them enrolled, and a seat is taken
  const orgContext = await browser.newContext({ baseURL: "http://localhost:3100", locale: "en-IN" });
  const orgPage = await orgContext.newPage();
  await watch(orgPage, "http://localhost:8100");
  await signInAs(orgPage, partner.tokens);
  await orgPage.goto(`/en/employer/${partner.slug}/batches`);
  await expect(orgPage.getByText("Learners waiting for a reply")).toBeVisible();
  const row = orgPage.getByRole("listitem").filter({ hasText: title });
  await row.locator("summary", { hasText: "Learners" }).click();
  await expect(row.getByText(`Asha ${id}`)).toBeVisible();
  await expect(row.getByText("Evenings only")).toBeVisible();
  await row.getByRole("button", { name: `Enrolled: Asha ${id}` }).click();
  await expect(row.getByText("Enrolled", { exact: true })).toBeVisible();
  await expect(row.getByText("24 of 25 seats left")).toBeVisible();
  await orgContext.close();

  // ---- and the learner sees where it stands, and withdrawing takes the details back
  await page.goto("/en/interests");
  await expect(page.getByText("Enrolled", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: `Withdraw: ${title}` }).click();
  await expect(page.getByText("Withdrawn", { exact: true })).toBeVisible();
});
