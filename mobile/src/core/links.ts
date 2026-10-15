/**
 * Which screen a link opens, and nothing else.
 *
 * A link reaches the app from outside: a tapped `iism://job/<slug>`, a push notification's data, a
 * notice's `path`. **Nothing outside the app is trusted to name a screen**: this is the one table of
 * what a link may open, and anything it does not recognise is `null`, which the caller treats as
 * "stay where you are". A route that is not in the table cannot be reached by a crafted link, which
 * is the whole point of having a table instead of passing a path through.
 *
 * The website's own paths are understood too (`/jobs/<slug>`, `/courses/<slug>`, `/notifications`),
 * because a notice's `path` was written for the website and a shared web link should open the app
 * where one is installed.
 *
 * No React Native import: this file is tested in Node.
 */

/** A slug the API produces: lower-case letters, digits and hyphens. */
const SLUG = /^[a-z0-9][a-z0-9-]{0,199}$/;
/** An invitation token: URL-safe characters only. */
const TOKEN = /^[A-Za-z0-9_-]{8,200}$/;

type Rule = { match: RegExp; to: (m: RegExpExecArray) => string | null };

const bySlug = (prefix: string) => (m: RegExpExecArray) =>
  SLUG.test(m[1]) ? `/${prefix}/${m[1]}` : null;

const RULES: Rule[] = [
  { match: /^\/jobs?\/([^/]+)$/, to: bySlug("job") },
  { match: /^\/courses?\/([^/]+)$/, to: bySlug("course") },
  { match: /^\/skills?\/([^/]+)$/, to: bySlug("skill") },
  { match: /^\/match\/([^/]+)$/, to: bySlug("match") },
  { match: /^\/invite\/([^/]+)$/, to: (m) => (TOKEN.test(m[1]) ? `/invite/${m[1]}` : null) },
  { match: /^\/(matches|applications|saved|interests|profile|account|contact|me)$/, to: (m) => `/${m[1]}` },
  { match: /^\/(notifications|notices)$/, to: () => "/notices" },
  { match: /^\/(grievance|contact)$/, to: () => "/contact" },
  { match: /^\/jobs$/, to: () => "/jobs" },
  { match: /^\/courses$/, to: () => "/courses" },
  { match: /^\/(home)?$/, to: () => "/" },
];

/** `iism://job/x`, `iism:///job/x`, an allowed web host's `https://host/jobs/x`, or a bare path. */
function pathOf(url: string, webHosts: readonly string[]): string | null {
  const trimmed = url.trim();
  const app = /^iism:\/\/\/?(.*)$/i.exec(trimmed);
  let rest: string;
  if (app) {
    rest = `/${app[1]}`;
  } else {
    const web = /^https:\/\/([^/?#]+)(\/[^?#]*)?/i.exec(trimmed);
    if (web) {
      if (!webHosts.map((h) => h.toLowerCase()).includes(web[1].toLowerCase())) return null;
      rest = web[2] ?? "/";
    } else if (trimmed.startsWith("/") && !trimmed.startsWith("//")) {
      rest = trimmed;
    } else {
      return null;
    }
  }
  const clean = rest.split(/[?#]/, 1)[0].replace(/\/+$/, "");
  return clean === "" ? "/" : clean;
}

/**
 * The in-app path a link opens, or `null`. `webHosts` are the domains the website is served from;
 * until there is one (deployment is deferred) only `iism://` and bare in-app paths resolve.
 */
export function resolveLink(url: unknown, webHosts: readonly string[] = []): string | null {
  if (typeof url !== "string" || url.length === 0 || url.length > 2048) return null;
  const path = pathOf(url, webHosts);
  if (path === null) return null;
  for (const rule of RULES) {
    const m = rule.match.exec(path);
    if (m) return rule.to(m);
  }
  return null;
}
