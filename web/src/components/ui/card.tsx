import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

/**
 * The surface a thing sits on, at one of four levels (Sprint 80, BL-19.11, ADR-089).
 *
 * The page is a light grey and a card is white with a soft shadow, so it reads as a card by more than
 * its border (ADR-086). `level` says how much it stands out, and the levels are the design brief's:
 *
 * - `default`: a card on the page.
 * - `raised`: what floats above the page (a menu, a dialog's panel): the raised surface and shadow.
 * - `inset`: **a box inside a card**. A bordered, shadowed card inside a card was the way a form held
 *   a sub-panel, and two borders and two shadows read as clutter; an inset is the muted surface with
 *   no shadow. Use it, never a `Card` in a `Card`.
 * - `interactive`: a card that is a link or a button: it lifts on hover and takes the brand edge.
 *
 * The default is what `Card` always was (plus the shadow), so no call site changes.
 */
const card = cva("border", {
  variants: {
    level: {
      default: "rounded-xl border-border-token bg-surface shadow-card",
      raised: "rounded-xl border-border-token bg-surface-raised shadow-raised",
      inset: "rounded-lg border-border-token bg-surface-muted",
      interactive:
        "rounded-xl border-border-token bg-surface shadow-card transition-shadow hover:border-brand hover:shadow-raised",
    },
  },
  defaultVariants: { level: "default" },
});

export function Card({
  className,
  level,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof card>) {
  return <div className={cn(card({ level }), className)} {...props} />;
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold", className)} {...props} />;
}
