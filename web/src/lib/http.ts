/**
 * Reading a status code back off a failed query.
 *
 * TanStack Query carries whatever the query function threw, so the convention
 * across this app is `throw new Error(String(response.status))` -- which makes
 * the status recoverable at the render site without a custom error class.
 *
 * **This exists because collapsing every failure into one branch misled
 * somebody.** Every organisation panel rendered "no access" -- or nothing at
 * all -- whether the API said 401 or 403, and the two mean opposite things:
 * 403 is "this is not yours", 401 is "you are signed out". An owner following
 * instructions to delete their own organisation found the control simply
 * absent, because their fifteen-minute access token had expired half an hour
 * earlier and the panel hid itself exactly as it hides from a non-owner.
 */

/** The HTTP status a failed query carried, or null if it did not carry one. */
export function statusOf(error: unknown): number | null {
  if (!(error instanceof Error)) return null;
  const code = Number(error.message);
  return Number.isInteger(code) && code >= 100 && code <= 599 ? code : null;
}

/** Whether this failure means "you are signed out", not "this is not yours". */
export function isSignedOut(error: unknown): boolean {
  return statusOf(error) === 401;
}
