/**
 * The names this browser keeps its sign-in under.
 *
 * Their own module, with no `"use client"`: `lib/auth.ts` is a client module, and a server component
 * (the root layout, which writes the head script that reads these before the first paint) that
 * imported a constant from it would get a client reference, not the string.
 */
export const ACCESS_TOKEN_KEY = "iism.access_token";
export const REFRESH_TOKEN_KEY = "iism.refresh_token";
