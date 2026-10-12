import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const isDev = process.env.NODE_ENV !== "production";
const apiOrigin = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Content Security Policy -- **enforced in a production build** (Sprint 54, ADR-065); report-only
 * under `next dev`.
 *
 * Tokens live in localStorage, where any script on the page can read them, so
 * keeping foreign script out matters more here than on a cookie-session site.
 * Sprint 20 shipped it report-only because a wrong policy silently breaks pages.
 * Sprint 52's browser run made that checkable -- every page, in both languages,
 * on a production build, with a listener on `securitypolicyviolation` -- and
 * Sprints 52 and 53 found none, so it is enforced. The same run is the guard: a
 * page that needs something the policy forbids now fails the suite instead of
 * quietly working. Development stays report-only, because hot reload and React's
 * dev overlay reach for things (eval, websockets) a production page never does.
 *
 * `'unsafe-inline'` for scripts is the honest current state: Next's inline
 * bootstrap carries no nonce on statically rendered pages, and nonces require
 * dynamic rendering (see the CSP guide in node_modules/next/dist/docs). Removing
 * it is a deliberate trade against static rendering, not a header tweak.
 * `'unsafe-eval'` is development-only -- React uses eval there for error stacks.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigin}${isDev ? " ws://localhost:* http://localhost:*" : ""}`,
  "worker-src 'self'",
  "manifest-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: isDev ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  // A browser ignores HSTS over plain HTTP, and pinning localhost to HTTPS
  // would break every other project on this machine. Production only.
  ...(isDev
    ? []
    : [
        {
          key: "Strict-Transport-Security",
          value: "max-age=31536000; includeSubDomains",
        },
      ]),
];

const nextConfig: NextConfig = {
  // The browser tests build into their own directory so a production build never overwrites the
  // `.next` a running `next dev` is serving from (Sprint 52). Unset, it is Next's default.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default withNextIntl(nextConfig);
