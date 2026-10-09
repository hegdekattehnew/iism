import { execFileSync } from "node:child_process";
import path from "node:path";

import { request as playwrightRequest, type Page } from "@playwright/test";

import { E2E } from "../playwright.config";
import { checkPage, expect, test } from "./support/test";
import {
  addSkill,
  applyTo,
  COLLECT_BLOOD,
  courseSlugByTitle,
  jobSlugByTitle,
  organisation,
  publishedCourse,
  publishedJob,
  registerInterest,
  saveJob,
  seekerTokens,
  signInAs,
  suffix,
  type Tokens,
} from "./support/identities";

/**
 * Every page, not six journeys.
 *
 * Sprint 52's journeys visited about a third of the app's 42 routes and found five defects no other
 * test could see. This visits the rest -- in both languages, signed out and as each kind of person --
 * and runs the same `checkPage` on every one: console, network, CSP, flush borders, and contrast in
 * light and dark. A page that only fails when somebody looks at it in Hindi, or in dark mode, or
 * with real rows in it, is exactly what the component tests cannot see.
 *
 * Detail pages need a real vacancy, course and organisations; they are made once through the API
 * (set-up, as in the journeys), and the signed-in pages are visited **populated**, because an empty
 * list hides most of what can go wrong (Sprint 52's `<dl>` defect only showed once a figure had a
 * sub-line).
 */
const LOCALES = ["en", "hi"] as const;
const REPO = path.resolve(__dirname, "..", "..");

type World = {
  jobSlug: string;
  courseSlug: string;
  employer: { slug: string; tokens: Tokens };
  provider: { slug: string; tokens: Tokens };
  seeker: Tokens;
  operator: { email: string; tokens: Tokens };
};

let world: World;

test.beforeAll(async () => {
  const request = await playwrightRequest.newContext();
  const id = suffix();
  const employer = await organisation(request, "employer", `Sweep Hospital ${id}`);
  const provider = await organisation(request, "course_provider", `Sweep Academy ${id}`);
  const operator = await organisation(request, "employer", `Sweep Operators ${id}`);
  execFileSync(path.join(REPO, ".venv", "bin", "python"), ["scripts/grant_staff.py", operator.email, "--tier", "admin", "--apply"], {
    cwd: REPO,
    env: { ...process.env, DATABASE_URL: E2E.database, REDIS_URL: E2E.redis, ENVIRONMENT: "test" },
    stdio: "pipe",
  });

  await publishedJob(request, employer, `Sweep vacancy ${id}`, [{ skill_slug: COLLECT_BLOOD, importance: 4, is_mandatory: true }]);
  const jobSlug = await jobSlugByTitle(request, employer.tokens, employer.slug, `Sweep vacancy ${id}`);
  await publishedCourse(request, provider, `Sweep course ${id}`, [COLLECT_BLOOD]);
  const courseSlug = await courseSlugByTitle(request, provider.tokens, provider.slug, `Sweep course ${id}`);

  // A seeker with something on every list: a standard, an application, a saved vacancy, an interest.
  const seeker = await seekerTokens(request);
  await addSkill(request, seeker, COLLECT_BLOOD);
  await applyTo(request, seeker, jobSlug);
  await saveJob(request, seeker, jobSlug);
  await registerInterest(request, seeker, courseSlug);

  world = { jobSlug, courseSlug, employer, provider, seeker, operator };
  await request.dispose();
});

/** Land on the page and wait until its data has arrived: a skeleton is a page not yet worth checking. */
async function visit(page: Page, url: string): Promise<void> {
  await page.goto(url);
  await page.waitForLoadState("load");
  await expect(page.locator(".animate-pulse")).toHaveCount(0, { timeout: 15_000 });
}

const PUBLIC = [
  "/",
  "/about",
  "/careers",
  "/contact",
  "/courses",
  "/employers",
  "/employers/signin",
  "/grievance",
  "/jobs",
  "/privacy",
  "/providers",
  "/search?q=blood",
  "/signin",
  "/signup",
  "/signup/seeker",
  "/signup/employer",
  "/signup/provider",
  "/skills",
  "/terms",
  "/invite/not-a-real-token",
];

test.describe("signed out", () => {
  for (const locale of LOCALES) {
    for (const route of PUBLIC) {
      test(`${locale}${route}`, async ({ page }) => {
        await visit(page, `/${locale}${route === "/" ? "" : route}`);
        // An unknown invitation is a refusal the page is meant to show, so its 4xx is its own doing.
        const refused = route.startsWith("/invite/");
        await checkPage(page, `${locale}${route}`, {
          allowResponses: refused ? [/\/invitations\//] : [],
          allowConsole: refused ? [/status of 404/] : [],
        });
      });
    }
  }

  for (const locale of LOCALES) {
    test(`${locale}: a vacancy, a course and a standard`, async ({ page }) => {
      for (const route of [`/jobs/${world.jobSlug}`, `/courses/${world.courseSlug}`, `/skills/collect-blood-samples-hc-n0001`]) {
        await visit(page, `/${locale}${route}`);
        await checkPage(page, `${locale}${route}`);
      }
    });

    test(`${locale}: a page that does not exist is a real 404`, async ({ page }) => {
      const response = await page.goto(`/${locale}/this-page-does-not-exist`);
      expect(response?.status()).toBe(404);
      await checkPage(page, `${locale} 404`, { allowResponses: [/404/], allowConsole: [/status of 404/] });
    });
  }

  test("the development-only pages are not in a production build", async ({ page }) => {
    const status = await page.goto("/en/status");
    expect(status?.status(), "/status is for development only").toBe(404);
  });
});

test.describe("signed in as a job seeker, with something on every list", () => {
  for (const locale of LOCALES) {
    for (const route of ["/profile", "/matches", "/applications", "/saved", "/interests", "/account", "/career-paths"]) {
      test(`${locale}${route}`, async ({ page }) => {
        await signInAs(page, world.seeker);
        await visit(page, `/${locale}${route}`);
        await checkPage(page, `seeker ${locale}${route}`);
      });
    }
  }
});

test.describe("signed in as an employer", () => {
  for (const locale of LOCALES) {
    for (const route of ["", "/settings", "/team", "/jobs/upload"]) {
      test(`${locale}/employer/<org>${route}`, async ({ page }) => {
        await signInAs(page, world.employer.tokens);
        await visit(page, `/${locale}/employer/${world.employer.slug}${route}`);
        await checkPage(page, `employer ${locale}${route || "/"}`);
      });
    }

    test(`${locale}: the applicants and the candidate pool for a vacancy`, async ({ page }) => {
      await signInAs(page, world.employer.tokens);
      for (const route of [`/jobs/${world.jobSlug}/applications`, `/candidates/${world.jobSlug}`]) {
        await visit(page, `/${locale}/employer/${world.employer.slug}${route}`);
        await checkPage(page, `employer ${locale}${route}`);
      }
    });
  }
});

test.describe("signed in as a training provider", () => {
  for (const locale of LOCALES) {
    for (const route of ["", "/settings", "/courses/upload", "/interests"]) {
      test(`${locale}/employer/<provider>${route}`, async ({ page }) => {
        await signInAs(page, world.provider.tokens);
        await visit(page, `/${locale}/employer/${world.provider.slug}${route}`);
        await checkPage(page, `provider ${locale}${route || "/"}`);
      });
    }

    test(`${locale}: who is interested in a course`, async ({ page }) => {
      await signInAs(page, world.provider.tokens);
      await visit(page, `/${locale}/employer/${world.provider.slug}/courses/${world.courseSlug}/interests`);
      await checkPage(page, `provider ${locale} course interests`);
    });
  }
});

test.describe("signed in as an operator", () => {
  for (const locale of LOCALES) {
    test(`${locale}/admin and one organisation's review`, async ({ page }) => {
      await signInAs(page, world.operator.tokens);
      for (const route of ["/admin", `/admin/${world.employer.slug}`]) {
        await visit(page, `/${locale}${route}`);
        await checkPage(page, `operator ${locale}${route}`);
      }
    });
  }
});
