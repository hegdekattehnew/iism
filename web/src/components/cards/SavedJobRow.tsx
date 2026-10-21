"use client";

import { Avatar } from "@/components/ui/avatar";
import { ChevronRightIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";

/**
 * A saved vacancy: the employer's mark, the title and the employer, and a chevron, **all one link**
 * (Sprint 87, BL-19.17). It holds no button, so the whole card can be the target; a card that holds
 * a button is not a link (ADR-074). Saving tells the employer nothing, and the page says so.
 */
export function SavedJobRow({ slug, title, employer }: { slug: string; title: string; employer: string }) {
  return (
    <Link
      href={`/jobs/${slug}`}
      className="flex min-h-11 items-center gap-3 rounded-xl border border-border-token bg-surface p-4 shadow-card transition-shadow hover:border-brand hover:shadow-raised"
    >
      <Avatar name={employer} />
      <div className="min-w-0 flex-1">
        <p className="text-base font-semibold">{title}</p>
        <p className="text-sm text-muted">{employer}</p>
      </div>
      <ChevronRightIcon className="h-5 w-5 shrink-0 text-muted" />
    </Link>
  );
}
