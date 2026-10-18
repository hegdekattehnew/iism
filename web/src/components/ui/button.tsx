"use client";

import { Slot } from "@radix-ui/react-slot";
import type { VariantProps } from "class-variance-authority";
import * as React from "react";

import { buttonVariants } from "@/components/ui/button-variants";
import { cn } from "@/lib/cn";

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the child element, so a link can look like a button without
   *  nesting an <a> inside a <button>. */
  asChild?: boolean;
  /** Something is happening: the button is disabled, says it is busy and shows a ring. Not with `asChild`. */
  loading?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  type,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      // `type="button"` by default, inverting the HTML default of "submit".
      // A button inside a form that submits it *unless* told not to is a
      // footgun: the standards picker's Add button silently saved a
      // half-written vacancy instead of adding a standard. Submitting is the
      // special case and every form here already says so explicitly.
      type={asChild ? type : (type ?? "button")}
      className={cn(buttonVariants({ variant, size }), className)}
      {...(asChild ? { disabled } : { disabled: disabled || loading, "aria-busy": loading || undefined })}
      {...props}
    >
      {asChild ? (
        children
      ) : (
        <>
          {/* The spinner's own ring, not its component: `Button` is on every route's first load. */}
          {loading && (
            <span
              aria-hidden
              className="inline-block h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
            />
          )}
          {children}
        </>
      )}
    </Comp>
  );
}
