import { resolveLink } from "../src/core/links";
import { WEB_BASE_URL } from "../src/config";

/**
 * Every link that reaches the app from outside passes through here before the router sees it
 * (Expo Router's `redirectSystemPath`). **A link opens only what `resolveLink` recognises**: a
 * vacancy, a course, a standard, a match, the person's own lists, the updates, an invitation (which
 * says it is for the website) or the contact page. Anything else is not followed: a link that is
 * not recognised opens Home when it launched the app, and does nothing when the app was already
 * open, so a crafted link cannot reach a route nobody linked to on purpose.
 */
const WEB_HOSTS = ((): string[] => {
  const host = /^https:\/\/([^/?#]+)/i.exec(WEB_BASE_URL)?.[1];
  return host ? [host] : [];
})();

export function redirectSystemPath({ path, initial }: { path: string; initial: boolean }): string | null {
  return resolveLink(path, WEB_HOSTS) ?? (initial ? "/" : null);
}
