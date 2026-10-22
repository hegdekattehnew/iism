/**
 * Capture the pages a person meets, and measure them (Sprint 68, the UI review).
 *
 *     API=http://localhost:8100 WEB=http://localhost:3100 node scripts/capture-review.mjs ../docs/design/review
 *
 * **Read-only against the product**: it signs in as seeded demonstration people (the same OTP flow
 * a person uses, with the development code the API returns), visits pages and takes pictures. It
 * writes nothing but files. It reads from a **production build** (so dev chrome is not judged) on the
 * demonstration database, never the golden candidates `+919000000001`-`005` and never a real number.
 *
 * Each page is captured at a phone width, and a chosen set again in dark mode and in Hindi. The
 * numbers it collects (`measurements.json`) are the review's evidence for "how long", "how small a
 * tap target" and "how much text is under 12 px"; the pictures are for the eye.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { chromium, request as playwrightRequest } from "@playwright/test";

const API = process.env.API ?? "http://localhost:8100";
const WEB = process.env.WEB ?? "http://localhost:3100";
const OUT = path.resolve(process.argv[2] ?? "review");
const CONSENT = "2026-09-11";
const PHONE = { width: 375, height: 812 };
const DESKTOP = { width: 1280, height: 800 };
/** A picture is capped so the set stays small; page height is measured separately and in full. */
const MAX_PICTURE_HEIGHT = 2400;

mkdirSync(OUT, { recursive: true });
const api = await playwrightRequest.newContext({ baseURL: API });

async function seekerTokens(phone) {
  const asked = await (await api.post("/auth/otp/request", { data: { phone } })).json();
  const verified = await api.post("/auth/otp/verify", { data: { phone, code: asked.debug_code, consent_version: CONSENT } });
  if (!verified.ok()) throw new Error(`seeker ${phone}: ${verified.status()}`);
  return verified.json();
}
async function emailTokens(email) {
  const asked = await (await api.post("/auth/email/otp/request", { data: { email } })).json();
  const verified = await api.post("/auth/email/otp/verify", { data: { email, code: asked.debug_code } });
  if (!verified.ok()) throw new Error(`org ${email}: ${verified.status()}`);
  return verified.json();
}

const who = {
  seeker: await seekerTokens("9000000006"),
  employer: await emailTokens("recruiter@apollo-care.example"),
  provider: await emailTokens("admin@nsdc-healthcare-academy.example"),
  operator: await emailTokens("hiring@apollo-care.example"),
};
const JOB = process.env.JOB ?? "technician-room-air-conditioner-home-appliances-electronics";
const COURSE = process.env.COURSE ?? "general-duty-assistant-certificate";
const EMPLOYER = "apollo-care-hospitals";
// One of the employer's own vacancies, for the applicants and the candidate pool.
const own = await (await api.get(`/org/${EMPLOYER}/jobs`, { headers: { authorization: `Bearer ${who.employer.access_token}` } })).json();
const OWN_JOB = (own.items ?? own)[0]?.slug;
const PROVIDER = "nsdc-healthcare-academy";

/** id, who, path, and which extra variants to take (dark, hindi). The id orders the contact sheet. */
const PAGES = [
  ["home", "none", "", ["dark", "hi"]],
  ["jobs", "none", "/jobs", ["dark", "hi"]],
  ["job-detail", "none", `/jobs/${JOB}`, ["dark", "hi"]],
  ["courses", "none", "/courses", ["hi"]],
  ["course-detail", "none", `/courses/${COURSE}`, ["hi"]],
  ["skills", "none", "/skills", []],
  ["search", "none", "/search?q=nurse", ["hi"]],
  ["signin", "none", "/signin", ["dark", "hi"]],
  ["signup", "none", "/signup", []],
  ["signup-seeker", "none", "/signup/seeker", []],
  ["employers", "none", "/employers", []],
  ["providers", "none", "/providers", []],
  ["about", "none", "/about", []],
  ["contact", "none", "/contact", []],
  ["privacy", "none", "/privacy", []],
  ["matches", "seeker", "/matches", ["dark", "hi"]],
  ["profile", "seeker", "/profile", ["dark", "hi"]],
  ["applications", "seeker", "/applications", ["hi"]],
  ["notifications", "seeker", "/notifications", []],
  ["saved", "seeker", "/saved", []],
  ["interests", "seeker", "/interests", []],
  ["career-paths", "seeker", "/career-paths", ["hi"]],
  ["account", "seeker", "/account", []],
  ["employer-home", "employer", `/employer/${EMPLOYER}`, ["desktop"]],
  ["employer-applicants", "employer", `/employer/${EMPLOYER}/jobs/${OWN_JOB}/applications`, []],
  ["employer-candidates", "employer", `/employer/${EMPLOYER}/candidates/${OWN_JOB}`, []],
  ["employer-team", "employer", `/employer/${EMPLOYER}/team`, []],
  ["employer-upload", "employer", `/employer/${EMPLOYER}/jobs/upload`, []],
  ["provider-home", "provider", `/employer/${PROVIDER}`, ["desktop"]],
  ["provider-upload", "provider", `/employer/${PROVIDER}/courses/upload`, []],
  ["provider-interests", "provider", `/employer/${PROVIDER}/interests`, []],
  ["admin", "operator", "/admin", ["desktop"]],
];

const browser = await chromium.launch();
const results = [];

async function measure(page) {
  return page.evaluate(() => {
    const vh = window.innerHeight;
    const visible = (e) => {
      const r = e.getBoundingClientRect();
      const s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    const targets = [...document.querySelectorAll("a[href],button,select,input:not([type=hidden]),textarea,[role=button],[role=link],[role=tab]")].filter(visible);
    const small = targets.filter((e) => {
      const r = e.getBoundingClientRect();
      // A bare skip link is 1x1 on purpose until focused.
      if (r.width <= 1 && r.height <= 1) return false;
      return r.height < 44 || r.width < 44;
    });
    const tiny = [...document.querySelectorAll("body *")].filter((e) => {
      if (![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) return false;
      return visible(e) && parseFloat(getComputedStyle(e).fontSize) < 12;
    });
    const imgs = [...document.images].filter(visible);
    return {
      pageHeight: document.documentElement.scrollHeight,
      screens: Math.round((document.documentElement.scrollHeight / vh) * 10) / 10,
      overflowX: document.documentElement.scrollWidth > window.innerWidth,
      interactive: targets.length,
      smallTargets: small.length,
      smallExamples: small.slice(0, 6).map((e) => `${e.tagName.toLowerCase()} ${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)} ${(e.innerText || e.getAttribute("aria-label") || "").trim().slice(0, 24)}`),
      textUnder12px: tiny.length,
      images: imgs.length,
      svgs: document.querySelectorAll("svg").length,
      headings: [...document.querySelectorAll("h1,h2,h3")].filter(visible).length,
      title: document.title,
    };
  });
}

async function shoot(id, who_, route, variant) {
  const locale = variant === "hi" ? "hi" : "en";
  const viewport = variant === "desktop" ? DESKTOP : PHONE;
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
    colorScheme: variant === "dark" ? "dark" : "light",
    locale: locale === "hi" ? "hi-IN" : "en-IN",
    timezoneId: "Asia/Kolkata",
    isMobile: variant !== "desktop",
  });
  // Light is the default whatever the device says (Sprint 92), so a dark capture chooses dark.
  if (variant === "dark") await context.addInitScript(() => localStorage.setItem("iism-theme", "dark"));
  const tokens = who[who_] ?? null;
  if (tokens) {
    await context.addInitScript(([a, r]) => {
      localStorage.setItem("iism.access_token", a);
      localStorage.setItem("iism.refresh_token", r);
    }, [tokens.access_token, tokens.refresh_token]);
  }
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 140)));
  const url = `${WEB}/${locale}${route}`;
  let status = 0;
  try {
    const response = await page.goto(url, { waitUntil: "load" });
    status = response?.status() ?? 0;
    await page.waitForFunction(() => document.querySelectorAll("[data-loading]").length === 0, null, { timeout: 15000 }).catch(() => undefined);
    // A slow query (the career ladder) can outlast the loading marker: wait for the network to rest too.
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => undefined);
    await page.waitForTimeout(800);
    const m = await measure(page);
    const file = `${id}.${variant}.${locale}.jpg`;
    await page.screenshot({
      path: path.join(OUT, file),
      fullPage: true,
      type: "jpeg",
      quality: 50,
      // A long list is three screens of picture, not forty: its height is in measurements.json.
      clip: { x: 0, y: 0, width: viewport.width, height: Math.min(m.pageHeight, MAX_PICTURE_HEIGHT) },
    }).catch(() => undefined);
    results.push({ id, variant, locale, viewport: `${viewport.width}x${viewport.height}`, who: who_, url: route, status, file, errors, ...m });
  } catch (error) {
    results.push({ id, variant, locale, who: who_, url: route, status, error: String(error).slice(0, 200) });
  }
  await context.close();
}

for (const [id, who_, route, extras] of PAGES) {
  await shoot(id, who_, route, "light");
  for (const variant of extras) await shoot(id, who_, route, variant);
}
await browser.close();
await api.dispose();

writeFileSync(path.join(OUT, "measurements.json"), JSON.stringify({ capturedAgainst: WEB, results }, null, 2) + "\n");
console.log(`${results.length} captures -> ${OUT}`);
for (const r of results) {
  console.log(`${String(r.status).padEnd(3)} ${r.variant.padEnd(7)} ${r.locale} ${r.id.padEnd(20)} ${r.screens ?? "-"} screens, ${r.smallTargets ?? "-"} small targets, ${r.textUnder12px ?? "-"} tiny texts${r.error ? " ERROR " + r.error : ""}`);
}
