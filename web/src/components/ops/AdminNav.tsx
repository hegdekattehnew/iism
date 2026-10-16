"use client";

import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";
import { useMemberships } from "@/lib/org";

import { ADMIN_SECTIONS, sectionId } from "./admin-sections";

/**
 * A way to jump around a page that was one scroll of thirty-one screens (Sprint 73, UI-16).
 *
 * Plain anchors under the header, scrolling sideways on a phone (and wrapping from `sm` up, where a
 * clipped last label read as a bug): no JavaScript to navigate, no new
 * dependency (`/admin` is the route nearest the first-load budget, and tabs were removed from the
 * component library on purpose). Each link is 44 px tall. **Enrolment is offered only to the admin
 * tier**, matching the server's `OPS_ENROL` and the panel itself; the link is the one thing that
 * arrives after the account does, and it is the last item of a row that scrolls sideways, so it
 * cannot move anything vertically.
 */
export function AdminNav() {
  const t = useTranslations("ops.nav");
  const { data: me } = useMemberships();
  const admin = me?.staff_tier === "admin";
  const sections = ADMIN_SECTIONS.filter((s) => s !== "enrolment" || admin);

  return (
    <nav
      aria-label={t("label")}
      className="sticky top-16 z-30 -mx-5 mb-8 border-b border-border-token bg-background/95 px-5 backdrop-blur"
    >
      <ul className="flex gap-1 overflow-x-auto py-1 sm:flex-wrap sm:overflow-visible">
        {sections.map((section) => (
          <li key={section} className="shrink-0">
            <a
              href={`#${sectionId(section)}`}
              className={cn(
                "inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-medium whitespace-nowrap text-muted transition-colors",
                "hover:bg-surface-muted hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
              )}
            >
              {t(section)}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
