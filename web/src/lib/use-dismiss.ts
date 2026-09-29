"use client";

import { useEffect, type RefObject } from "react";

/**
 * Close a popover when the user presses Escape or clicks away from it.
 *
 * A hook rather than a second Radix package: a dropdown menu is not worth
 * ~12KB on the low-end Android this product targets, and the modal dialog --
 * which genuinely needs a focus trap, a scroll lock and return-focus -- already
 * justifies its own primitive in `ui/dialog.tsx`.
 *
 * Sprint 26 found that **nothing in `web/src` handled a keydown at all**, so
 * every dropdown in the header stayed open until its own toggle was pressed
 * again. Escape is the one interaction people try first.
 *
 * `pointerdown`, not `click`: a `click` listener on the document fires after
 * the target's own handler, so a menu item that navigates would close the menu
 * a frame later, and a control *outside* the menu would receive its click
 * while the menu was still open. It is also the event a touch device delivers
 * first.
 */
export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  onDismiss: () => void,
): void {
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
    };
    const onPointer = (e: PointerEvent) => {
      const el = ref.current;
      if (el && !el.contains(e.target as Node)) onDismiss();
    };

    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [ref, open, onDismiss]);
}
