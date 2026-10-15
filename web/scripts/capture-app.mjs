/**
 * Capture the phone app's main screens through its browser build (Sprint 68, the UI review).
 *
 *     APP=http://localhost:8081 node scripts/capture-app.mjs ../docs/design/screens
 *
 * The app is Expo / React Native; `react-native-web` renders the same screens in Chromium. It is a
 * **browser rendering, not a phone**: no native fonts, no Hermes, no safe areas. Tokens live in
 * memory on the web (no secure store), so this signs in through the real sign-in screen with the
 * development code and moves by **tapping** (a reload would sign out). It uses a seeded
 * demonstration candidate, never the golden `+919000000001`-`005` and never a real number.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import { chromium } from "@playwright/test";

const APP = process.env.APP ?? "http://localhost:8081";
const OUT = path.resolve(process.argv[2] ?? "screens");
const PHONE = process.env.PHONE ?? "9000000006";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, locale: "en-IN", colorScheme: "light", isMobile: true });
let page = await context.newPage();
const shots = [];
const settle = () => page.waitForTimeout(1200);
async function shot(name) {
  await settle();
  await page.screenshot({ path: path.join(OUT, `app-${name}.light.en.jpg`), type: "jpeg", quality: 50 });
  shots.push(name);
}
// The Me tab's name carries the unread count ("Me, 3 new updates"), so a tab is matched by its first word.
const tab = (name) => page.getByRole("tab", { name: new RegExp(`^${name}\\b`) }).first();

await page.goto(`${APP}/`);
await shot("home-signed-out");
await tab("Jobs").click();
await shot("jobs");
await page.getByRole("button").filter({ hasText: /./ }).nth(0).waitFor();
// The first card is a pressable with the job's title as its name.
await page.locator('[role="button"]').filter({ hasText: /NSQF|Full time|full_time|years/i }).first().click().catch(() => undefined);
await shot("job-detail");

// A fresh context for the signed-in half: the signed-out browsing above must not leave history behind.
await context.close();
const signedIn = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, locale: "en-IN", colorScheme: "light", isMobile: true });
page = await signedIn.newPage();
await page.goto(`${APP}/sign-in`);
await page.getByLabel("Mobile number").fill(PHONE);
await page.getByRole("button", { name: "Send code" }).click();
const code = (await page.getByText(/your code is \d{6}/).textContent())?.match(/\d{6}/)?.[0];
await page.getByLabel("6-digit code").fill(code ?? "");
await page.getByRole("button", { name: "Verify and continue" }).click();
await settle();
await shot("home-signed-in");
await tab("Matches").click();
await shot("matches");
await tab("Me").click();
await shot("me");
await page.getByRole("button", { name: "My applications" }).click();
await shot("applications");
await page.goBack();
await tab("Me").click();
await settle();
await page.getByText("My profile", { exact: true }).first().click();
await shot("profile");
await page.goBack();
await tab("Me").click();
await settle();
await page.getByText("Where you could move next", { exact: true }).first().click();
await shot("careers");
// Last, because a detail opened earlier left the history somewhere the Me screen did not expect.
await page.goBack();
await tab("Matches").click();
await settle();
await page.locator('[role="button"]').filter({ hasText: /match/i }).first().click().catch(() => undefined);
await shot("match-detail");
await browser.close();
console.log(`${shots.length} app captures -> ${OUT}: ${shots.join(", ")}`);
