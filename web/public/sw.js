/**
 * The service worker, and what it is deliberately not allowed to cache.
 *
 * Chrome will not offer to install a PWA without a fetch handler, so this file
 * is what makes the app installable at all. Everything beyond that exists for
 * one reason: the target device is a low-end Android on mobile data, and the
 * taxonomy should still be readable when the connection stalls.
 *
 * **Personal and computed responses are never cached.** A stale match is worse
 * than no match -- it would show a candidate a gap they have already closed --
 * and cached profile data on a shared phone is the ADR-023 problem this
 * project takes seriously elsewhere. The DENY list below is a security
 * boundary, not an optimisation choice: add to it before adding a route that
 * returns anything about a person.
 */

const VERSION = "v1";
const SHELL = `iism-shell-${VERSION}`;
const ASSETS = `iism-assets-${VERSION}`;
const DATA = `iism-data-${VERSION}`;

// Enough to render something recognisable offline. Not the whole app: a
// precache list that drifts from the build is worse than a small honest one.
const PRECACHE = [
  "/offline.html",
  "/manifest.webmanifest",
  "/icon.svg",
  "/icon-192.png",
  "/icon-512.png",
];

// Never cached, on any origin, under any strategy.
const DENY = [
  "/me/",
  "/auth/",
  "/employer/",
  "/tasks/",
  "/health",
  "/matches",
  "/profile",
  "/signin",
  // Sprint 20: the account page shows consent and deletion state.
  "/account",
];

// Public taxonomy and marketplace reads. Slow-moving, identical for everyone,
// and the part of the app worth having on a stalled connection.
const CACHEABLE_DATA = ["/skills", "/jobs", "/courses", "/marketplace/"];

const denied = (url) => DENY.some((p) => url.pathname.includes(p));

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      // Individually, so one missing file cannot fail the whole install and
      // leave the app permanently uninstallable.
      .then((cache) => Promise.allSettled(PRECACHE.map((u) => cache.add(u))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  const keep = new Set([SHELL, ASSETS, DATA]);
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/** Hashed build output: the filename changes when the content does. */
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

/** Show what we have immediately, and refresh it for next time. */
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  const fetching = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => hit);
  return hit ?? fetching;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // An authenticated request must never touch a cache, whatever its path.
  if (denied(url) || request.headers.has("authorization")) return;

  if (
    url.origin === self.location.origin &&
    url.pathname.startsWith("/_next/static/")
  ) {
    event.respondWith(cacheFirst(request, ASSETS));
    return;
  }

  if (
    CACHEABLE_DATA.some((p) => url.pathname.startsWith(p)) &&
    request.destination === ""
  ) {
    event.respondWith(staleWhileRevalidate(request, DATA));
    return;
  }

  if (request.mode === "navigate") {
    // Network first: a page is cheap to fetch and expensive to serve stale.
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(SHELL).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(async () => {
          const cache = await caches.open(SHELL);
          return (
            (await cache.match(request)) ?? (await cache.match("/offline.html"))
          );
        }),
    );
  }
});
