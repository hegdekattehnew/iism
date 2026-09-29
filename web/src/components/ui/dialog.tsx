"use client";

import * as DialogPrimitive from"@radix-ui/react-dialog";
import type { ReactNode } from"react";

import { cn } from"@/lib/cn";

/**
 * A modal dialog, rendered through a portal.
 *
 * **The portal is not a detail; it is the whole reason this exists.** The
 * previous hand-rolled overlay was a `fixed inset-0` div rendered inside
 * `ContextSwitcher`, which lives inside `Header` -- and `Header` carries
 * `backdrop-blur`. An ancestor with `backdrop-filter` becomes the **containing
 * block for `position: fixed` descendants**, so `inset-0` resolved against the
 * header's box rather than the viewport: measured at 1280x64 against a
 * 1280x800 window. The dialog was clamped into the 64px strip at the top of
 * the page, which is exactly what"stuck to the top and not fully visible"
 * looks like. It was never a styling mistake -- it is a CSS containing-block
 * rule, and no amount of `z-index` or `top` would have fixed it.
 *
 * Three more defects went with it, all of them things a hand-rolled overlay
 * has to remember and this one cannot forget:
 *
 * - **focus never entered the dialog** while it claimed `aria-modal="true"`,
 *   so a keyboard or screen-reader user was left outside it;
 * - **the body still scrolled** behind the overlay;
 * - **Escape did nothing** -- there was no `keydown` handler anywhere in
 *   `web/src`.
 *
 * Radix supplies all four: `Portal` escapes the containing block, and `Root`
 * brings the focus trap, the return of focus to the trigger on close, the
 * scroll lock and the `aria` wiring. Adding the dependency is consistent with
 * this library's stated rule -- a primitive kept *for later* costs a download
 * on every phone, but this one is rendered now.
 *
 * **`max-h` and `overflow-y-auto` on the panel are deliberate.** A dialog
 * taller than a 640px phone screen, centred, is unreachable at both ends; this
 * is the same class of bug as the one above and it is cheaper to prevent here
 * than to find later.
 */

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-overlay" />
        <DialogPrimitive.Content
          className={cn(
            "fixed top-1/2 left-1/2 z-50 w-[calc(100vw-2.5rem)] max-w-sm -translate-x-1/2",
            "-translate-y-1/2 rounded-xl border border-border-token bg-surface p-6 shadow-raised",
            "max-h-[calc(100dvh-2.5rem)] overflow-y-auto",
            className,
          )}
        >
          <DialogPrimitive.Title className="text-base font-semibold">
            {title}
          </DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-1 text-sm text-muted">
              {description}
            </DialogPrimitive.Description>
          ) : (
            // Radix warns when a dialog has no description. Saying"there
            // isn't one" is the documented way to mean it deliberately.
            <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
          )}
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
