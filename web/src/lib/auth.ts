"use client";

/**
 * Client-side token storage.
 *
 * localStorage, not a cookie, because the API is a separate origin and this is
 * a client-rendered PWA. That means tokens are readable by any script on the
 * page, so the mitigations that matter are the short access-token lifetime and
 * refresh rotation — both enforced server-side. Moving to httpOnly cookies is
 * the right change once the API is served from the same origin.
 */

const ACCESS = "iism.access_token";
const REFRESH = "iism.refresh_token";

export type Tokens = { access_token: string; refresh_token: string };

// Lets the header react to sign-in/out without a page reload or a prop drill.
const CHANGED = "iism:auth-changed";

function safe<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    // Private browsing and blocked site data both throw on access.
    return fallback;
  }
}

export const getAccessToken = () =>
  safe(() => localStorage.getItem(ACCESS), null);

export const getRefreshToken = () =>
  safe(() => localStorage.getItem(REFRESH), null);

export function setTokens(tokens: Tokens): void {
  safe(() => {
    localStorage.setItem(ACCESS, tokens.access_token);
    localStorage.setItem(REFRESH, tokens.refresh_token);
  }, undefined);
  window.dispatchEvent(new Event(CHANGED));
}

export function clearTokens(): void {
  safe(() => {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  }, undefined);
  window.dispatchEvent(new Event(CHANGED));
}

export function onAuthChange(handler: () => void): () => void {
  window.addEventListener(CHANGED, handler);
  window.addEventListener("storage", handler); // other tabs
  return () => {
    window.removeEventListener(CHANGED, handler);
    window.removeEventListener("storage", handler);
  };
}

export const authHeaders = (): Record<string, string> => {
  const token = getAccessToken();
  return token ? { authorization: `Bearer ${token}` } : {};
};

// --- React binding -----------------------------------------------------------
// useSyncExternalStore is the correct primitive for subscribing to state that
// lives outside React (localStorage plus our change event). It also gives a
// server snapshot, so SSR renders the signed-out shell without an effect.

import { useSyncExternalStore } from "react";

function subscribe(cb: () => void): () => void {
  return onAuthChange(cb);
}

const getSnapshot = () => Boolean(getAccessToken());
const getServerSnapshot = () => false;

/** null is never returned; `false` on the server and first paint. */
export function useIsSignedIn(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
