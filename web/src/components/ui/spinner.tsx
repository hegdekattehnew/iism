import { cn } from "@/lib/cn";

/**
 * Something is happening and the person should know (Sprint 80, BL-19.12, ADR-089).
 *
 * A ring in the text colour (`currentColor`), so it follows the theme and sits inside a button or
 * beside a sentence. With a `label` (the caller's own message: this component says nothing in any
 * language) it is a status a screen reader announces; **without one it is decoration** and hidden
 * from assistive technology, for a button that already says it is busy. The spin stops under a
 * reduced-motion preference (`globals.css`), leaving a still ring.
 *
 * `placeholder` marks it as standing in for content that has not arrived, as a `Skeleton` does:
 * `globals.css` hides the footer while anything carries `data-loading`, so the footer does not
 * jump when the content lands (ADR-065). Leave it off for a spinner in a button.
 */
export function Spinner({
  label,
  className,
  placeholder = false,
}: {
  label?: string;
  className?: string;
  placeholder?: boolean;
}) {
  return (
    <span
      {...(label ? { role: "status", "aria-label": label } : { "aria-hidden": true })}
      data-loading={placeholder ? "" : undefined}
      className={cn(
        "inline-block h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}
