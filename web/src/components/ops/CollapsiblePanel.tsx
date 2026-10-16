"use client";

import { type ComponentType, useEffect, useRef, useState } from "react";

/**
 * A reference panel that stays folded until somebody opens it, and is **mounted only then**
 * (Sprint 73, UI-16).
 *
 * Folded, it is one summary row of fixed height, so it cannot move the page and costs no request.
 * Opened for the first time it mounts `Panel`, which the caller loads with `next/dynamic`, so the
 * panel's code leaves the route's first load as well (`/admin` had 1,961 bytes of headroom). Once
 * opened it stays mounted, so folding it again loses nothing the operator typed.
 *
 * A link to `#id` opens it (`AdminNav`, or a pasted address), because an anchor into a folded
 * panel that lands on a closed row would look broken.
 *
 * The panel's own `<h2>` is kept for screen readers and for the specs that name it, and hidden
 * visually: the summary already says the same words.
 */
export function CollapsiblePanel({
  id,
  title,
  Panel,
}: {
  id: string;
  title: string;
  Panel: ComponentType;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const openIfAddressed = () => {
      // Through the element, not state: setting `open` fires `toggle`, which mounts the panel.
      if (window.location.hash === `#${id}` && ref.current) ref.current.open = true;
    };
    openIfAddressed();
    window.addEventListener("hashchange", openIfAddressed);
    return () => window.removeEventListener("hashchange", openIfAddressed);
  }, [id]);

  return (
    <details
      id={id}
      ref={ref}
      className="group scroll-mt-32 rounded-xl border border-border-token bg-surface"
      onToggle={(event) => {
        if (event.currentTarget.open) setMounted(true);
      }}
    >
      <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-5 py-3 text-lg font-semibold focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand [&::-webkit-details-marker]:hidden">
        {title}
        <span aria-hidden className="text-muted transition-transform group-open:rotate-90">
          ›
        </span>
      </summary>
      {mounted ? (
        <div className="px-5 pb-5 [&_h2:first-of-type]:sr-only">
          <Panel />
        </div>
      ) : null}
    </details>
  );
}
