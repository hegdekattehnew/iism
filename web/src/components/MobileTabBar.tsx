"use client";

import { useTranslations } from "next-intl";

import { BookOpenIcon, BriefcaseIcon, TargetIcon, UserIcon } from "@/components/ui/icons";
import { Link, usePathname } from "@/i18n/navigation";
import { TAB_ITEMS, currentHref } from "@/lib/nav";

const ICONS = {
  jobs: BriefcaseIcon,
  courses: BookOpenIcon,
  tabMatches: TargetIcon,
  tabProfile: UserIcon,
} as const;

/**
 * The job seeker's bottom bar on a phone's browser: Jobs, Courses, Matches, Profile (Sprint 81,
 * BL-19.13, ADR-090), the owner's choice and the four the phone app has. Fixed to the bottom of the
 * screen on small screens only (`lg:hidden`: from a laptop's width the header carries these).
 *
 * **It is fixed, so it moves nothing when it arrives**; the room for it under the page is
 * `--tabbar`, set from the first paint by the head script (`lib/auth-hint.ts`). It is a lazily
 * loaded chunk (`SeekerTabs`) because the header graph is on every route's first load and it
 * draws four icons. The current tab is `aria-current="page"` and drawn filled, so it is not told
 * by colour alone.
 */
export function MobileTabBar() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const current = currentHref(
    TAB_ITEMS.map((i) => i.href),
    pathname,
  );

  return (
    <nav
      aria-label={t("tabsLabel")}
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border-token bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      <ul className="mx-auto grid max-w-xl grid-cols-4">
        {TAB_ITEMS.map(({ key, href }) => {
          const Icon = ICONS[key];
          const here = href === current;
          return (
            <li key={key}>
              <Link
                href={href}
                aria-current={here ? "page" : undefined}
                className={`flex min-h-16 flex-col items-center justify-center gap-1 px-1 text-xs font-medium focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                  here ? "text-brand" : "text-muted"
                }`}
              >
                <span
                  className={`grid h-7 w-12 place-items-center rounded-full transition-colors ${here ? "bg-accent-tint" : ""}`}
                >
                  <Icon className="h-5 w-5" />
                </span>
                <span className="max-w-full truncate">{t(key)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
