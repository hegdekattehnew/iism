import { cva } from "class-variance-authority";

/** Button styling, deliberately in its own module with no `"use client"`.
 *
 * Server components render buttons too (the hero's search form is one), and a
 * style function exported from a client module cannot be called during
 * prerender — Next fails the build with "attempted to call buttonVariants()
 * from the server". Styles are shared; only the interactive component is client.
 */
export const buttonVariants = cva(
  // focus-visible rather than focus: a mouse user should not see a ring, a
  // keyboard user must.
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium " +
    "transition-colors disabled:pointer-events-none disabled:opacity-50 " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand " +
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-brand text-brand-contrast hover:bg-brand-strong",
        secondary:
          "border border-border-token bg-surface text-foreground hover:bg-surface-muted",
        ghost: "text-muted hover:bg-surface-muted hover:text-foreground",
        danger:
          "border border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100 " +
          "dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300",
      },
      size: {
        sm: "px-3 py-1.5 text-sm",
        md: "px-4 py-2.5 text-sm",
        lg: "px-5 py-3 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);
