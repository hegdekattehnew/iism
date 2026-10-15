/**
 * The key of every query about the signed-in person. **They all start with `"me"`**, which is what
 * makes two rules cheap to keep:
 *
 * - `persist.ts` keeps only keys starting `"public"`, so nothing here can reach the disk by accident;
 * - signing out removes everything under `"me"` (the root layout), so on a shared phone the next
 *   person to sign in is never shown the last one's profile, applications or interests.
 *
 * A query about a person that is not keyed here is a defect. No React Native import.
 */

export const ME_KEY = "me" as const;

export const meKeys = {
  all: [ME_KEY] as const,
  account: [ME_KEY, "account"] as const,
  profile: [ME_KEY, "profile"] as const,
  matches: [ME_KEY, "matches"] as const,
  match: (slug: string) => [ME_KEY, "match", slug] as const,
  applications: [ME_KEY, "applications"] as const,
  saved: [ME_KEY, "saved"] as const,
  interests: [ME_KEY, "interests"] as const,
  notices: [ME_KEY, "notices"] as const,
  unread: [ME_KEY, "unread"] as const,
  messages: [ME_KEY, "messages"] as const,
  deletion: [ME_KEY, "deletion"] as const,
  roles: (q: string) => [ME_KEY, "roles", q] as const,
  roleStandards: (slug: string) => [ME_KEY, "role-standards", slug] as const,
};

export const isMeKey = (key: readonly unknown[]): boolean => key[0] === ME_KEY;
