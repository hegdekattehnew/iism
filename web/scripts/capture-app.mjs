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
 *
 * Since Sprint 78 (BL-19.9, UI-21) it also **scores layout shift** for every screen the way the web's
 * browser sweep does (the worst session window, ignoring shifts within 500 ms of a tap) and prints
 * it beside the capture's name. `CHECK=1` makes a screen above 0.1 fail the run (exit 1); set `API`
 * to the API's origin to hold every read back 250 ms, as the sweep does, so a screen that only
 * jumps while its list is still on the way is seen on a fast machine too. A tap that moves between
 * screens inside one document means the score is the shift **since the previous capture**.
 *
 * `app-layout-shift-baseline.json` is the one place a screen is allowed above 0.1: a screen whose jump
 * is a **known open finding** has its ceiling recorded there, and may only go down (the web's target
 * baseline works the same way). Today that is the signed-in home, whose personal block lands in four
 * pieces above the search box; fixing it is the phone home's design (BL-19.22), not a tolerance.
 */
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { chromium } from "@playwright/test";

const APP = process.env.APP ?? "http://localhost:8081";
const OUT = path.resolve(process.argv[2] ?? "screens");
const PHONE = process.env.PHONE ?? "9000000006";
mkdirSync(OUT, { recursive: true });

const API = process.env.API;
const MAX_LAYOUT_SHIFT = 0.1;
/** Core Web Vitals' session window, run in the page: the worst window of shifts under 1 s apart. */
const observeShift = () => {
  const w = window;
  w.__cls = { score: 0, moved: [] };
  let windowScore = 0;
  let windowStart = 0;
  let last = 0;
  new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      if (e.hadRecentInput) continue;
      if (windowScore === 0 || e.startTime - last > 1000 || e.startTime - windowStart > 5000) {
        windowScore = 0;
        windowStart = e.startTime;
      }
      windowScore += e.value;
      last = e.startTime;
      if (windowScore > w.__cls.score) w.__cls.score = windowScore;
      // What moved, by tag and the first words it holds, so a failure names the thing to look at.
      for (const src of e.sources ?? []) {
        const n = src.node;
        const label = (n?.getAttribute?.("aria-label") ?? n?.textContent ?? "").trim().replace(/\s+/g, " ").slice(0, 28);
        w.__cls.moved.push(`${n?.nodeName ?? "?"}${label ? ` "${label}"` : ""}`);
      }
    }
  }).observe({ type: "layout-shift", buffered: true });
};
async function instrument(ctx) {
  await ctx.addInitScript(observeShift);
  if (API) {
    await ctx.route(`${API}/**`, async (route) => {
      if (route.request().method() === "GET") await new Promise((done) => setTimeout(done, 250));
      await route.continue();
    });
  }
}
const shifts = [];
const known = JSON.parse(readFileSync(new URL("./app-layout-shift-baseline.json", import.meta.url), "utf8"));
const ceilingOf = (name) => Math.max(MAX_LAYOUT_SHIFT, known[name] ?? 0);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, locale: "en-IN", colorScheme: "light", isMobile: true });
await instrument(context);
let page = await context.newPage();
const shots = [];
const settle = () => page.waitForTimeout(1200);
async function shot(name) {
  await settle();
  await page.screenshot({ path: path.join(OUT, `app-${name}.light.en.jpg`), type: "jpeg", quality: 50 });
  shots.push(name);
  const cls = await page.evaluate(() => {
    const seen = window.__cls ?? { score: 0, moved: [] };
    window.__cls = { score: 0, moved: [] };
    return seen;
  });
  shifts.push({ name, score: cls.score, moved: [...new Set(cls.moved)].slice(0, 4) });
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
await instrument(signedIn);
page = await signedIn.newPage();
await page.goto(`${APP}/sign-in`);
await page.getByLabel("Mobile number").fill(PHONE);
await page.getByRole("button", { name: "Send code" }).click();
const code = (await page.getByText(/your code is \d{6}/).textContent())?.match(/\d{6}/)?.[0];
await page.getByLabel("6-digit code").fill(code ?? "");
// The sign-in form is not the screen being scored: start from the moment the person is let in.
await page.evaluate(() => {
  window.__cls = { score: 0, moved: [] };
});
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
await page.getByText("My profile", { exact: true }).last().click();
await shot("profile");
await page.goBack();
await tab("Me").click();
await settle();
await page.getByText("Where you could move next", { exact: true }).last().click();
await shot("careers");
// Last, because a detail opened earlier left the history somewhere the Me screen did not expect.
await page.goBack();
await tab("Matches").click();
await settle();
await page.locator('[role="button"]').filter({ hasText: /match/i }).first().click().catch(() => undefined);
await shot("match-detail");
// Last, because choosing leaves the Me tab scrolled to the control and the steps above start at its top.
// Sprint 78 (BL-19.8): dark against a light phone, which the colours must follow at once.
await page.goBack();
await tab("Me").click();
await settle();
// A tab's screens stay mounted (hidden) in the browser build, so the scroller to move is the visible
// one that holds the control; Playwright's own scroll-into-view does not reach a React Native ScrollView.
await page.evaluate(() => {
  const scrollers = [...document.querySelectorAll('[data-testid="screen-content"]')];
  const mine = scrollers.find((el) => el.offsetParent !== null && /Appearance/.test(el.textContent ?? ""));
  if (mine) mine.scrollTop = mine.scrollHeight;
});
await page.getByRole("button", { name: "Dark", exact: true }).click();
await shot("me-dark-chosen");
await browser.close();
console.log(`${shots.length} app captures -> ${OUT}: ${shots.join(", ")}`);
console.log("layout shift per screen (0.1 is the ceiling):");
for (const { name, score, moved } of shifts) {
  const note = known[name] !== undefined ? `   (known, ceiling ${known[name]})` : "";
  console.log(`  ${score.toFixed(3).padStart(6)}  ${name}${note}${score > MAX_LAYOUT_SHIFT ? `   moved: ${moved.join(", ")}` : ""}`);
}
const over = shifts.filter((s) => s.score > ceilingOf(s.name));
if (process.env.CHECK && over.length > 0) {
  console.error(`${over.length} screen(s) jumped while loading: ${over.map((s) => s.name).join(", ")}`);
  process.exit(1);
}
