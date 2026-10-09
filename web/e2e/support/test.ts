import { expect, test as base, type Page } from "@playwright/test";

// Playwright transpiles these files as CommonJS (the package is not `"type": "module"`).
const AXE = require.resolve("axe-core/axe.min.js");

/**
 * What `checkPage` collects while a journey runs.
 *
 * Everything here is a fact a real browser knows and jsdom does not: that a request failed, that
 * the report-only CSP *would have* blocked something (it blocks nothing, so nobody notices
 * otherwise), that a page logged an error, and what the colours actually compute to.
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

  // `securitypolicyviolation` fires for report-only policies too, which is the point: the header
  // ships report-only, so a violation blocks nothing and is otherwise invisible.
  await page.addInitScript(() => {
    (window as unknown as { __csp: string[] }).__csp = [];
    document.addEventListener("securitypolicyviolation", (e) => {
      (window as unknown as { __csp: string[] }).__csp.push(
        `${e.violatedDirective} blocked ${e.blockedURI || "inline"} (${e.disposition})`,
      );
    });
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
};

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
  expect.soft(csp, `${label}: CSP violations (report-only, so nothing was blocked)`).toEqual([]);

  if (options.flush !== false) {
    expect.soft(await flushBorders(page), `${label}: text flush against a border`).toEqual([]);
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
