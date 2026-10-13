"use client";

import { useSyncExternalStore } from "react";

/**
 * What the person would pay for a course, in rupees (Sprint 58, BL-14.6, ADR-068).
 *
 * **Per viewer, in the browser, and nowhere else.** It is sent as `?budget_inr=` on the three
 * requests that suggest courses and is never stored on the profile: a profile column would be
 * personal data needing export and erasure treatment (ADR-055), and a number somebody typed once to
 * see a different ordering is not a fact about them. Storage can be empty, blocked or throw
 * (a private window, cleared site data); every access is guarded and the page works without it.
 */
const KEY = "iism:course-budget";
export const BUDGET_MAX = 10_000_000;

const listeners = new Set<() => void>();

function read(): number | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw === null) return null;
    const n = Number(raw);
    return Number.isInteger(n) && n >= 0 && n <= BUDGET_MAX ? n : null;
  } catch {
    return null;
  }
}

/** Nothing to remember on the server, and the first client render must match it. */
const server = (): number | null => null;

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function setCourseBudget(value: number | null): void {
  try {
    if (value === null) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, String(value));
  } catch {
    // Not remembered; the change still applies to this session through the listeners.
  }
  memory = value;
  listeners.forEach((l) => l());
}

// Used when storage refuses, so the control still does something this visit.
let memory: number | null | undefined;

export function useCourseBudget(): number | null {
  return useSyncExternalStore(
    subscribe,
    () => (memory !== undefined ? memory : read()),
    server,
  );
}
