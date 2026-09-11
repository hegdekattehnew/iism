import { notFound } from "next/navigation";

/**
 * Any path under a locale that matches no route. Without this an unknown URL
 * never reaches `[locale]/not-found.tsx` -- which only catches an explicit
 * `notFound()` -- and falls through to Next's unstyled, untranslated default.
 */
export default function CatchAll() {
  notFound();
}
