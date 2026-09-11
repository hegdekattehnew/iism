"use client";

import fatal from "@/messages/fatal.json";

import "./globals.css";

/**
 * The last resort: the root layout itself failed, so there is no locale, no
 * translation provider and no header. Both languages are shown, because which
 * one the visitor reads cannot be known here.
 *
 * Its strings live in `messages/fatal.json` rather than the full message files,
 * which would add both locales' entire catalogues to the client bundle for a
 * page that should never render.
 */
export default function GlobalError({ retry }: { retry: () => void }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground antialiased">
        <main className="max-w-md">
          <h1 className="text-2xl font-bold">{fatal.en.title}</h1>
          <p className="mt-3 text-muted">{fatal.en.body}</p>
          <h2 lang="hi" className="mt-8 text-2xl font-bold">
            {fatal.hi.title}
          </h2>
          <p lang="hi" className="mt-3 text-muted">
            {fatal.hi.body}
          </p>
          <button
            type="button"
            onClick={() => retry()}
            className="mt-8 rounded-lg bg-brand px-4 py-2 font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {fatal.en.retry} / <span lang="hi">{fatal.hi.retry}</span>
          </button>
        </main>
      </body>
    </html>
  );
}
