"use client";

import { useEffect } from "react";

/**
 * Registers the service worker — the thing that makes the app installable.
 *
 * **Production builds only.** In development the worker would cache hashed
 * chunks that hot reload then replaces, producing the "my change isn't
 * showing" class of bug that costs an afternoon each time. Installability is
 * demonstrated from `npm run build && npm start`, which is what a phone would
 * be served anyway.
 */
export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // A failed registration costs offline support, not the app. Nothing
      // here is worth showing a visitor an error about.
    });
  }, []);

  return null;
}
