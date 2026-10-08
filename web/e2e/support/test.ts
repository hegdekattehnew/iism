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
  /** Skip the dark-mode contrast pass: for a page that is checked light-only on purpose. */
  light?: boolean;
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

  expect.soft(seen.consoleErrors, `${label}: console errors`).toEqual([]);
  expect.soft(seen.pageErrors, `${label}: uncaught page errors`).toEqual([]);
  expect.soft(seen.failedRequests, `${label}: failed requests`).toEqual([]);
  expect.soft(responses, `${label}: error responses`).toEqual([]);
  expect.soft(csp, `${label}: CSP violations (report-only, so nothing was blocked)`).toEqual([]);

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
