/**
 * Runs `onSignedOut` when a session that **was there** ends, and never otherwise.
 *
 * The token store tells its subscribers the state every time it is loaded or changed, including the
 * first load at launch when nobody is signed in. A listener that wiped on every `signedIn === false`
 * therefore wiped the stored public cache on **every launch of a signed-out phone**, which is the
 * phone that most needs it (found by running the screens in a browser with the API switched off:
 * the offline list was empty). A wipe is for the *transition* from signed in to signed out.
 *
 * No React Native import: this file is tested in Node.
 */
export function createSignOutWatch(onSignedOut: () => void): (signedIn: boolean) => void {
  let wasSignedIn = false;
  return (signedIn) => {
    if (wasSignedIn && !signedIn) onSignedOut();
    wasSignedIn = signedIn;
  };
}

/**
 * What ending a session forgets: **every query in memory** (profile, matches, applications,
 * interests, all keyed `"me"`) and the stored public cache. On a shared phone the next person to
 * sign in must never be shown the last one's data, not even for the moment before their own loads:
 * the web's `qc.clear()` on sign-out (Sprint 13).
 */
export function forgetEverything(
  queryClient: { clear: () => void },
  forgetStored: () => Promise<void> | void,
): void {
  queryClient.clear();
  void forgetStored();
}
