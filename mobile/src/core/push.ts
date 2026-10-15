/**
 * The decisions behind push notifications that need no phone to make: when to ask, what to send the
 * server, and where a tapped notification goes. The one file that talks to the operating system is
 * `src/push.ts`; everything it decides is here, so it is tested in Node (ADR-075).
 *
 * No React Native import: this file is tested in Node.
 */

import { resolveLink } from "./links";

export type Permission = "undetermined" | "granted" | "denied";

export type AskState = {
  signedIn: boolean;
  isJobSeeker: boolean | undefined;
  permission: Permission;
  /** The person has seen the explanation and chosen: asking again would be nagging. */
  declined: boolean;
};

/**
 * Whether to show the explanation and ask now. **Never at launch and never before there is a reason**:
 * the question is asked where the person is looking at their updates, signed in, as a job seeker,
 * and only while the operating system has not already been told no (it will not ask twice).
 */
export function shouldAsk(state: AskState): boolean {
  return (
    state.signedIn &&
    state.isJobSeeker === true &&
    state.permission === "undetermined" &&
    !state.declined
  );
}

/** Whether to register a token silently: already allowed, so there is nothing to ask. */
export function shouldRegister(state: Pick<AskState, "signedIn" | "isJobSeeker" | "permission">): boolean {
  return state.signedIn && state.isJobSeeker === true && state.permission === "granted";
}

export type DeviceBody = { token: string; platform: "android" | "ios"; locale: string };

export function deviceBody(token: string, platform: "android" | "ios", locale: string): DeviceBody {
  return { token, platform, locale };
}

/** Where a tapped push goes: the in-app path it carries, resolved through the one link table. */
export function pathFromPush(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return null;
  return resolveLink((data as { path?: unknown }).path);
}
