/**
 * What makes a **release** build refuse to start (ADR-077).
 *
 * The defaults in `config.ts` are the development machine: plain HTTP, `localhost`, an emulator's
 * `10.0.2.2`. A release build that fell back to one of them would ship an app that cannot reach
 * anything (Android blocks cleartext traffic in release builds; Apple's App Transport Security
 * refuses it), and it would look like an outage on the very first day. So a release build with no
 * origin, an `http://` origin or a local one says so on screen instead of calling a server that is
 * not there. Pure: no React Native import, and the build kind is passed in.
 */

export type ConfigProblem = "api-missing" | "api-insecure" | "api-local" | "web-missing" | "web-insecure" | "web-local";

const LOCAL_HOST = /^(localhost|127\.\d+\.\d+\.\d+|10\.0\.2\.2|0\.0\.0\.0|\[::1\]|[^.]+\.localhost)$/i;

function parse(value: string | undefined): URL | null {
  if (!value) return null;
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

export function configProblems({
  apiBaseUrl,
  webBaseUrl,
  release,
}: {
  apiBaseUrl: string | undefined;
  webBaseUrl: string | undefined;
  release: boolean;
}): ConfigProblem[] {
  if (!release) return [];
  const problems: ConfigProblem[] = [];
  const api = parse(apiBaseUrl);
  if (!api) problems.push("api-missing");
  else {
    if (api.protocol !== "https:") problems.push("api-insecure");
    if (LOCAL_HOST.test(api.hostname)) problems.push("api-local");
  }
  // The website is where the privacy notice lives; a missing one is as wrong as a local one.
  const web = parse(webBaseUrl);
  if (!web) problems.push("web-missing");
  else if (web.protocol !== "https:") problems.push("web-insecure");
  else if (LOCAL_HOST.test(web.hostname)) problems.push("web-local");
  return problems;
}
