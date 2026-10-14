/**
 * What the phone remembers for offline reading, and the rule that nothing about a person is in it.
 *
 * The website's service worker has a DENY list ("`/me/`, `/auth/`, `/employer/`... are never
 * cached", ADR-023). On a phone the rule is **stricter than a deny list**: an ALLOW list. A query is
 * kept only if its key starts with `"public"`, so a new query about a person is not stored by
 * default, and forgetting to add it to a list is the safe mistake.
 *
 * - A query is kept if it **has data**, whatever happened last. A failed background refetch leaves a
  query in the `error` state *with its data still in it*, and that is exactly the moment the person
  is offline and wants to read it: keeping only `status === "success"` emptied the stored cache on
  the first offline reload (found by running the screens in a browser). A query that never had data
  is not worth keeping.
 * - **No mutation is ever kept.** A mutation's variables are what a person typed: a phone number, a
 *   code. The library's default keeps paused mutations; this refuses them all.
 * - Twenty-four hours, then it is gone (`MAX_AGE_MS`): a vacancy that closed yesterday must not look
 *   open for a week.
 * - Signing out wipes it (`wipePersistedCache`), so a shared phone shows the next person nothing of
 *   the last one, even though none of it was personal.
 *
 * No React Native import: this file is tested in Node.
 */

export const PUBLIC_KEY = "public";
export const CACHE_STORAGE_KEY = "iism.public-cache";
export const MAX_AGE_MS = 24 * 60 * 60 * 1000;

export const isPublicKey = (queryKey: readonly unknown[]): boolean => queryKey[0] === PUBLIC_KEY;

type Dehydratable = { queryKey: readonly unknown[]; state: { data: unknown } };

export const dehydrateOptions = {
  shouldDehydrateQuery: (query: Dehydratable): boolean =>
    query.state.data !== undefined && isPublicKey(query.queryKey),
  shouldDehydrateMutation: (): boolean => false,
};

export type KeyValueStorage = { removeItem: (key: string) => Promise<void> };

export async function wipePersistedCache(storage: KeyValueStorage): Promise<void> {
  try {
    await storage.removeItem(CACHE_STORAGE_KEY);
  } catch {
    // A storage that cannot be cleared is not a reason for signing out to fail.
  }
}
