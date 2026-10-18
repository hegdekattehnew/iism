import { appendFileSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test as base, type Page } from "@playwright/test";

// Playwright transpiles these files as CommonJS (the package is not `"type": "module"`).
const AXE = require.resolve("axe-core/axe.min.js");

/**
 * What `checkPage` collects while a journey runs.
 *
 * Everything here is a fact a real browser knows and jsdom does not: that a request failed, that
 * the CSP blocked something, that a page logged an error, and what the colours actually compute to.
 */
type Seen = {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  badResponses: string[];
};

const watched = new WeakMap<Page, Seen>();

/** Start watching a page. Called once per page by the `page` fixture below. */
export async function watch(page: Page, apiOrigin: string): Promise<void> {
  const seen: Seen = { consoleErrors: [], pageErrors: [], failedRequests: [], badResponses: [] };
  watched.set(page, seen);

  // `securitypolicyviolation` fires for report-only policies and enforced ones alike. In a
  // production build the policy is enforced (Sprint 54), so a violation is also a blocked resource
  // and usually a console error; the listener names *which* directive it was.
  await page.addInitScript(() => {
    (window as unknown as { __csp: string[] }).__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      (window as unknown as { __csp: string[] }).__csp.push(
        `${e.violatedDirective} blocked ${e.blockedURI || "inline"} (${e.disposition})`,
      );
    });

    // Layout shift, the way Chrome scores it for Core Web Vitals: the worst *session window* (shifts
    // less than 1 s apart, a window at most 5 s long), ignoring shifts within 500 ms of a keypress or
    // click, which the person caused. Each shift keeps the element that moved, so a failure names it.
    const w = window as unknown as { __cls: { score: number; moved: string[] } };
    w.__cls = { score: 0, moved: [] };
    let windowScore = 0;
    let windowStart = 0;
    let last = 0;
    const describe = (n: Node | null) => {
      const el = n as Element | null;
      if (!el || !el.tagName) return "?";
      const cls = (el.getAttribute("class") ?? "").split(/\s+/).slice(0, 3).join(".");
      return `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${cls ? "." + cls : ""}`;
    };
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as Array<{ hadRecentInput: boolean; value: number; startTime: number; sources: Array<{ node: Node | null }> }>) {
        if (e.hadRecentInput) continue;
        if (windowScore === 0 || e.startTime - last > 1000 || e.startTime - windowStart > 5000) {
          windowScore = 0;
          windowStart = e.startTime;
        }
        windowScore += e.value;
        last = e.startTime;
        if (windowScore > w.__cls.score) w.__cls.score = windowScore;
        for (const s of e.sources) w.__cls.moved.push(`${describe(s.node)} (${e.value.toFixed(3)})`);
      }
    }).observe({ type: "layout-shift", buffered: true });
  });

  // The loading phase is where layout shifts happen, and on a developer's laptop it lasts a few
  // milliseconds, so a page can look stable here and jump on a phone. Holding every read back a
  // fixed 250 ms makes the loading state something the check always sees, whatever the machine.
  // Writes are not delayed: a journey's own actions should not get slower.
  await page.route(`${apiOrigin}/**`, async (route) => {
    if (route.request().method() === "GET") await new Promise((done) => setTimeout(done, 250));
    await route.continue();
  });

  page.on("console", (m) => {
    if (m.type() === "error") seen.consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => seen.pageErrors.push(e.message));
  page.on("requestfailed", (r) => {
    // A navigation the test itself interrupted is not a failure of the product.
    if (r.failure()?.errorText === "net::ERR_ABORTED") return;
    seen.failedRequests.push(`${r.method()} ${r.url()} ${r.failure()?.errorText}`);
  });
  page.on("response", (r) => {
    const url = r.url();
    // Only our own origins: a 4xx from the API or the app is ours to explain.
    if (r.status() >= 500 || (r.status() >= 400 && (url.startsWith(apiOrigin) || url.startsWith(page.url().split("/").slice(0, 3).join("/"))))) {
      seen.badResponses.push(`${r.status()} ${r.request().method()} ${url}`);
    }
  });
}

type Options = {
  /** Responses that are the journey's own doing (a deliberate 409, a 401 before sign-in). */
  allowResponses?: RegExp[];
  /** Console lines that are the journey's own doing: the browser reports a deliberate 404 as an error. */
  allowConsole?: RegExp[];
  /** Skip the dark-mode contrast pass: for a page that is checked light-only on purpose. */
  light?: boolean;
  /** Skip the flush-border check on a page where a bordered box genuinely holds bare text. */
  flush?: boolean;
  /** Skip the touch-target check (Sprint 69, UI-11) on a page with no header and footer. */
  targets?: boolean;
  /**
   * Hold the page to its recorded count of controls under 44 px (Sprint 78, BL-19.9): the count may
   * only go down, and a page with no recorded count fails until somebody records one on purpose.
   */
  ratchet?: boolean;
};

/** Core Web Vitals call a layout-shift score up to 0.1 "good"; above 0.25 it is "poor". */
const MAX_LAYOUT_SHIFT = 0.1;

/**
 * Assert the page in front of the browser is healthy: nothing logged, nothing failed, nothing the
 * CSP would have blocked, and no accessibility violation **including colour contrast** in both
 * colour schemes. `color-contrast` is the rule `a11y.test.tsx` has to switch off (jsdom has no
 * layout), so this is the only place it is ever measured.
 */
export async function checkPage(page: Page, label: string, options: Options = {}): Promise<void> {
  const seen = watched.get(page);
  if (!seen) throw new Error("checkPage needs the instrumented `page` fixture from e2e/support/test");

  const csp = await page.evaluate(() => (window as unknown as { __csp?: string[] }).__csp ?? []);
  const allowed = options.allowResponses ?? [];
  const responses = seen.badResponses.filter((r) => !allowed.some((a) => a.test(r)));

  const consoleErrors = seen.consoleErrors.filter((m) => !(options.allowConsole ?? []).some((a) => a.test(m)));
  expect.soft(consoleErrors, `${label}: console errors`).toEqual([]);
  expect.soft(seen.pageErrors, `${label}: uncaught page errors`).toEqual([]);
  expect.soft(seen.failedRequests, `${label}: failed requests`).toEqual([]);
  expect.soft(responses, `${label}: error responses`).toEqual([]);
  expect.soft(csp, `${label}: CSP violations`).toEqual([]);

  // A page that has not finished loading has not finished shifting: without this a list whose
  // data is still on its way passes, and jumps a moment after the test has looked. Polling pages
  // never go idle, so the wait is bounded and its timeout is not a failure.
  await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => undefined);
  await page.waitForTimeout(150);

  const shift = await page.evaluate(() => (window as unknown as { __cls?: { score: number; moved: string[] } }).__cls ?? { score: 0, moved: [] });
  expect.soft(
    shift.score <= MAX_LAYOUT_SHIFT ? [] : [`layout shift ${shift.score.toFixed(3)} > ${MAX_LAYOUT_SHIFT}; moved: ${[...new Set(shift.moved)].slice(0, 4).join(", ")}`],
    `${label}: the page jumped while loading`,
  ).toEqual([]);

  if (options.flush !== false) {
    expect.soft(await flushBorders(page), `${label}: text flush against a border`).toEqual([]);
  }

  if (options.targets !== false) {
    expect.soft(await smallTargets(page), `${label}: header or footer control under 44 px`).toEqual([]);
  }

  if (options.ratchet) {
    const found = await pageTargets(page);
    // A page made for the run has a random id in its slug: the record is for the page, not the run.
    const key = label.replace(/\b[0-9a-f]{8}\b/g, "<id>");
    // A run that is recording writes what it saw and checks nothing; `scripts/merge_target_baseline.py`
    // folds the log into the baseline, keeping the lower number for a page already there.
    if (process.env.TARGETS_LOG) {
      appendFileSync(process.env.TARGETS_LOG, `${JSON.stringify({ label: key, count: found.length })}\n`);
    } else {
      const allowed = targetBaseline()[key];
      expect.soft(
        allowed,
        `${label}: no recorded count of small controls (record one with TARGETS_LOG, see scripts/merge_target_baseline.py)`,
      ).not.toBeUndefined();
      if (allowed !== undefined) {
        expect.soft(
          found.length <= allowed ? [] : found.slice(0, 8),
          `${label}: ${found.length} controls under 44 px, was ${allowed}; fix the new one, or lower the record if you fixed old ones`,
        ).toEqual([]);
      }
    }
  }

  // Colours fade (`transition-colors`), and axe samples the computed value: measured the instant
  // the scheme flips it reads the *old* scheme's colour against the new background -- a contrast
  // failure that exists for 150 ms and in no one's eyes. Freeze the transitions, then measure.
  await page.addStyleTag({ content: "*,*::before,*::after{transition:none!important;animation:none!important}" });

  const schemes = options.light ? (["light"] as const) : (["light", "dark"] as const);
  for (const scheme of schemes) {
    await page.emulateMedia({ colorScheme: scheme });
    const violations = await axe(page);
    expect.soft(violations, `${label}: accessibility (${scheme})`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: null });
}

/**
 * Text that touches the border of the box it sits in.
 *
 * The gap Sprint 52 named: a `<Card>` with no `<CardBody>` renders its text flush against the border,
 * compiles, passes `tsc` and every check above, and shipped on the homepage for four sprints.
 * It is measurable: take every element with a visible border on **all four sides** (a card, not a
 * divider), and ask how far its text starts from the inner edge of the left border. Padding makes
 * that tens of pixels; a missing `CardBody` makes it zero.
 *
 * Skipped, because each carries its own spacing or is not a box of prose: form controls, buttons,
 * links, table parts, images and SVG. The threshold is 6px, which is the smallest padding the design
 * uses on a bordered chip (`px-1.5`).
 */
async function flushBorders(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const SKIP = new Set([
      "HTML", "BODY", "INPUT", "SELECT", "TEXTAREA", "BUTTON", "A", "IMG", "SVG", "PATH", "TABLE",
      "THEAD", "TBODY", "TR", "TD", "TH", "SUMMARY", "LABEL", "OPTION", "IFRAME", "CANVAS",
    ]);
    const MIN = 6;
    const px = (v: string) => Number.parseFloat(v) || 0;
    const visible = (width: string, style: string, colour: string) =>
      px(width) >= 1 && style !== "none" && style !== "hidden" && !/rgba\(.*,\s*0\)$/.test(colour) && colour !== "transparent";
    const found: string[] = [];

    for (const el of document.querySelectorAll("*")) {
      if (SKIP.has(el.tagName.toUpperCase())) continue;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden" || cs.display === "contents") continue;
      const sides = ["Top", "Right", "Bottom", "Left"] as const;
      const boxed = sides.every((side) =>
        visible(cs.getPropertyValue(`border-${side.toLowerCase()}-width`), cs.getPropertyValue(`border-${side.toLowerCase()}-style`), cs.getPropertyValue(`border-${side.toLowerCase()}-color`)),
      );
      if (!boxed) continue;

      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      const inner = box.left + px(cs.borderLeftWidth);

      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let nearest = Number.POSITIVE_INFINITY;
      let sample = "";
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = (node.textContent ?? "").trim();
        if (!text) continue;
        const parent = node.parentElement;
        if (!parent || SKIP.has(parent.tagName.toUpperCase())) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        const r = range.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const gap = r.left - inner;
        if (gap < nearest) {
          nearest = gap;
          sample = text.slice(0, 40);
        }
      }
      if (nearest < MIN) {
        const cls = (el.getAttribute("class") ?? "").split(/\s+/).slice(0, 6).join(".");
        found.push(`${el.tagName.toLowerCase()}.${cls} -- text "${sample}" starts ${nearest.toFixed(1)}px from the border`);
      }
    }
    return found.slice(0, 8);
  });
}

/**
 * Controls in the header and the footer that are smaller than a thumb (Sprint 69, UI-11).
 *
 * The design review measured 15 or more controls under 44 px on every page, and the header and
 * footer are on every page: a menu button at 38, nav links at 32, footer links at the height of their
 * text. Those two regions are asserted, because they are the same markup everywhere and one fix
 * clears them for the whole product; the rest of a page is a count in the review, not a failure
 * here. An inline link inside a sentence is exempt (WCAG 2.5.8 exempts it too), so only `a`s that
 * stand alone in a list or a nav are looked at, and controls that are not drawn are skipped.
 */
async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const MIN = 44;
    const found: string[] = [];
    const controls = document.querySelectorAll(
      "header a[href], header button, header select, header summary, header input, footer a[href], footer button, footer select, footer summary, footer input",
    );
    for (const el of controls) {
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      // A skip link is off-screen until focused.
      if (box.bottom < 0 || box.right < 0) continue;
      // Inline in a sentence: the control sits inside a paragraph with other text.
      const parent = el.parentElement;
      if (el.tagName === "A" && parent && parent.tagName === "P" && (parent.textContent ?? "").trim() !== (el.textContent ?? "").trim()) continue;
      if (box.height < MIN - 0.5 || box.width < MIN - 0.5) {
        const label = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 24);
        found.push(`${el.tagName.toLowerCase()} "${label}" ${Math.round(box.width)}x${Math.round(box.height)}`);
      }
    }
    return found.slice(0, 8);
  });
}

/** The recorded number of controls under 44 px per page (Sprint 78, BL-19.9). It only goes down. */
function targetBaseline(): Record<string, number> {
  return JSON.parse(readFileSync(path.join(__dirname, "target-baseline.json"), "utf8"));
}

/**
 * Every control on the page, not only the header and footer, whose box is under 44 px either way.
 *
 * The header and footer must have none (`smallTargets`, an absolute rule); a page's own controls are
 * held to a **ratchet** because 92 of them exist today across the 52 reviewed pages and the revamp
 * removes them family by family. Exempt, as WCAG 2.5.8 exempts them: a link inside a sentence, and a
 * checkbox or radio whose label (the box a finger lands on) is large enough. Skipped because they
 * are not on screen: hidden controls, a skip link, and the one-pixel `sr-only` clip. The result is
 * one entry per kind of control (tag and label), so a list that grows does not move the count.
 */
async function pageTargets(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const MIN = 44;
    const found: string[] = [];
    const controls = document.querySelectorAll(
      "a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link], [role=tab], [role=menuitem]",
    );
    for (const el of controls) {
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      let box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      if (box.width <= 1 && box.height <= 1) continue;
      if (box.bottom < 0 || box.right < 0) continue;
      if (el instanceof HTMLInputElement && (el.type === "checkbox" || el.type === "radio")) {
        const label = el.closest("label") ?? el.labels?.[0];
        if (label) box = label.getBoundingClientRect();
      }
      if (el.tagName === "A") {
        const parent = el.parentElement;
        const row = parent ? getComputedStyle(parent).display : "";
        const inline = parent && row !== "flex" && row !== "inline-flex" && row !== "grid";
        if (inline && (parent.textContent ?? "").trim() !== (el.textContent ?? "").trim()) continue;
      }
      if (box.height < MIN - 0.5 || box.width < MIN - 0.5) {
        const label = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 24);
        found.push(`${el.tagName.toLowerCase()} "${label}" ${Math.round(box.width)}x${Math.round(box.height)}`);
      }
    }
    // One entry per *kind* of control: a list of five matches has five "Details" buttons, and the
    // number of rows is the data's (other journeys publish vacancies while this one runs), not the
    // page's. The size is dropped from the kind for the same reason: it follows the label's width.
    const kinds = new Map<string, string>();
    for (const entry of found) kinds.set(entry.replace(/ \d+x\d+$/, ""), entry);
    return [...kinds.values()];
  });
}

async function axe(page: Page): Promise<string[]> {
  if (!(await page.evaluate(() => "axe" in window))) await page.addScriptTag({ path: AXE });
  return page.evaluate(async () => {
    const results = await (
      window as unknown as { axe: { run: (c: Document, o: object) => Promise<{ violations: Array<{ id: string; help: string; nodes: Array<{ target: unknown[]; failureSummary?: string }> }> }> } }
    ).axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } });
    return results.violations.map(
      (v) => `${v.id}: ${v.help} -- ${v.nodes.slice(0, 3).map((n) => `${n.target.join(" ")} [${(n.failureSummary ?? "").split("\n").slice(1, 2).join("")}]`).join("; ")}`,
    );
  });
}

export const test = base.extend({
  // The second argument is Playwright's "hand the fixture over" callback, conventionally `use`;
  // that name makes react-hooks/rules-of-hooks think this is a React hook, so it is `provide`.
  page: async ({ page }, provide) => {
    await watch(page, "http://localhost:8100");
    await provide(page);
  },
});

export { expect };
