/**
 * What the person would pay for a course, in whole rupees (ADR-068, ADR-078).
 *
 * **Held on the phone and nowhere else.** It is sent as `?budget_inr=` on the three reads that
 * suggest courses and is never stored on the profile: a profile column would be personal data
 * needing export and erasure (ADR-055), and a number somebody typed once to see a different order
 * is not a fact about them. It is **cleared when the session ends**, so a shared phone does not
 * carry the last person's figure. The store takes the storage as an argument, which is what makes
 * it testable in Node and keeps the native module in its one file.
 *
 * No React Native import: this file is tested in Node.
 */

export const BUDGET_MAX = 10_000_000;

export type ParsedBudget = { ok: true; value: number | null } | { ok: false };

/** Blank means "no budget" (`null`); anything else must be a whole number of rupees in range. */
export function parseBudget(text: string): ParsedBudget {
  const trimmed = text.replace(/[\s,]/g, "");
  if (trimmed === "") return { ok: true, value: null };
  if (!/^\d{1,8}$/.test(trimmed)) return { ok: false };
  const value = Number(trimmed);
  return value <= BUDGET_MAX ? { ok: true, value } : { ok: false };
}

/** The query the three reads take: nothing at all when there is no budget, never `budget_inr=null`. */
export function budgetQuery(value: number | null): { budget_inr?: number } {
  return value === null ? {} : { budget_inr: value };
}

type KeyValueStore = {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
};

export const BUDGET_STORAGE_KEY = "iism.course-budget";

export type BudgetStore = {
  get: () => number | null;
  set: (value: number | null) => void;
  /** Reads what was kept at the last launch; an unreadable or out-of-range value is "no budget". */
  restore: () => Promise<void>;
  /** The session ended: forget it in memory and on disk. */
  clear: () => Promise<void>;
  subscribe: (listener: () => void) => () => void;
};

export function createBudgetStore(storage: KeyValueStore): BudgetStore {
  let current: number | null = null;
  const listeners = new Set<() => void>();
  const announce = () => listeners.forEach((l) => l());

  return {
    get: () => current,
    set(value) {
      current = value !== null && Number.isInteger(value) && value >= 0 && value <= BUDGET_MAX ? value : null;
      announce();
      // Not remembered if storage refuses: the change still applies for this visit.
      const write =
        current === null ? storage.removeItem(BUDGET_STORAGE_KEY) : storage.setItem(BUDGET_STORAGE_KEY, String(current));
      void write.catch(() => undefined);
    },
    async restore() {
      try {
        const saved = await storage.getItem(BUDGET_STORAGE_KEY);
        const parsed = saved === null ? ({ ok: true, value: null } as const) : parseBudget(saved);
        current = parsed.ok ? parsed.value : null;
      } catch {
        current = null;
      }
      announce();
    },
    async clear() {
      current = null;
      announce();
      try {
        await storage.removeItem(BUDGET_STORAGE_KEY);
      } catch {
        // Nothing to forget on disk if the disk cannot be reached.
      }
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
