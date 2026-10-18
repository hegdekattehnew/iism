import type { ReactNode } from "react";

import { InboxIcon } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/**
 * A list with nothing in it, said kindly (Sprint 80, BL-19.12, ADR-089).
 *
 * An icon in a tinted disc, a sentence that says what is missing, optionally why or what to do, and
 * an `action`. **The first thing is an icon, because illustration art is the Product Owner's** and
 * has not arrived: when it does it is a drop-in, `illustration`, which replaces the icon (a local
 * file: the content security policy blocks remote images, so `<img src="/illustrations/…">`).
 * Nothing about the layout changes when it does.
 *
 * It is plain markup with no hooks, so a server component can render it, and its title is a
 * paragraph, not a heading: it sits under whatever heading the page already has.
 */
export function EmptyState({
  title,
  children,
  action,
  icon: Icon = InboxIcon,
  illustration,
  className,
}: {
  title: string;
  /** Why it is empty, or what to do about it. */
  children?: ReactNode;
  action?: ReactNode;
  icon?: typeof InboxIcon;
  /** Art that replaces the icon: a local image or inline SVG. */
  illustration?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-xl border border-dashed border-border-token bg-surface px-6 py-10 text-center",
        className,
      )}
    >
      <div aria-hidden className="grid h-12 w-12 place-items-center rounded-full bg-accent-tint text-accent-text">
        {illustration ?? <Icon className="h-6 w-6" />}
      </div>
      <p className="mt-4 text-base font-semibold">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
