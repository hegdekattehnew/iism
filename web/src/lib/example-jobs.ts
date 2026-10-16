/**
 * One-tap example searches (Sprint 70, UI-01). A first-time visitor who does not know what to type
 * gets four or five jobs people here actually look for. **The query is English and the label is in
 * the visitor's language**: the corpus is English, and a Hindi query resolves to a role only for
 * some of them (a Hindi alias exists for "ward boy", "driver" and "tailor", not for the rest), so a
 * Hindi query would send half the chips to an empty page. Change the list here, in one place; each
 * query must resolve to a role (`/roles/search`), and `first-minute-home.test.ts` holds that every label is
 * translated.
 */
export const EXAMPLE_JOBS = [
  { key: "wardBoy", query: "ward boy" },
  { key: "electrician", query: "electrician" },
  { key: "securityGuard", query: "security guard" },
  { key: "driver", query: "driver" },
  { key: "retailSales", query: "retail sales" },
] as const;

