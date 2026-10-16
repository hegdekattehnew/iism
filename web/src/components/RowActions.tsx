import type { ReactNode } from "react";

import { buttonVariants } from "@/components/ui/button-variants";
import { cn } from "@/lib/cn";

/**
 * The actions on one row of a workspace list: **one primary, one secondary, the rest behind "More"**
 * (Sprint 73, UI-15).
 *
 * A vacancy row used to end in five text links about 20 px tall, in two colours that did not say
 * which mattered; on a phone `employer-home` had 52 targets under 44 px. The primary is what a person
 * came to this row to do; the secondary is the one other thing they do often; everything else (the
 * undo, the close, the public page) is one tap further. "More" is a native `<details>`: no
 * script, no dependency, and keyboard and screen-reader behaviour for free. Its items are laid out in
 * the flow rather than floated over the card, so nothing is clipped on a narrow screen and a phone
 * target is never covered.
 *
 * Every control passed in is already at the project's 44 px floor (`Button` and `ButtonLink` sizes).
 */
export function RowActions({
  primary,
  secondary,
  more = [],
  moreLabel,
}: {
  primary?: ReactNode;
  secondary?: ReactNode;
  more?: ReactNode[];
  moreLabel: string;
}) {
  const items = more.filter(Boolean);
  return (
    <div className="mt-4 flex flex-wrap items-start gap-2">
      {primary}
      {secondary}
      {items.length > 0 && (
        <details className="group">
          <summary
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "cursor-pointer list-none [&::-webkit-details-marker]:hidden",
            )}
          >
            {moreLabel}
            <span aria-hidden className="transition-transform group-open:rotate-90">
              ›
            </span>
          </summary>
          <ul className="mt-1 flex flex-col items-start gap-1">
            {items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
