"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Card, Skeleton } from "@/components/ui";
import { ChevronRightIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { recentContexts } from "@/lib/context";
import { useMemberships } from "@/lib/org";

/**
 * The home page's right-hand card: "I'm here to…" for a visitor, "Welcome back" for somebody
 * signed in (Sprint 91, B22.1).
 *
 * The designer's review found a signed-in provider offered "Find work / Hire / Publish courses" on
 * the front page, as though they had never been here: the home forgot who you are outside the
 * workspace. A signed-in person gets their own doors instead (their matches if they look for work,
 * each organisation they run), and the sign-up chooser comes back only for a visitor, or when the
 * stored sign-in turns out to be dead (`/auth/me` failed), which is a visitor in all but name.
 *
 * **No flash, and no jump.** The chooser is server-rendered and is what a visitor gets with no
 * JavaScript. For a browser that holds a sign-in, `globals.css` hides it before the first paint
 * (`html[data-auth]`, set by the head script) at the height this card starts at, so neither a
 * chooser flickers in nor the page below moves much when this card arrives.
 */

/** Organisations listed on the card. The rest are in the header's workspace menu. */
const SHOWN = 3;

const ROW =
  "flex items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-surface-muted focus-visible:-outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand";

export function HomeAccess({ children }: { children: ReactNode }) {
  const t = useTranslations("chooser");
  const signedIn = useIsSignedIn();
  const { organisations, isJobSeeker, isPending, isError } = useMemberships();

  if (!signedIn) return <div data-home-chooser>{children}</div>;
  // A sign-in that `/auth/me` refuses is not a person to welcome back; show what a visitor sees.
  if (isError) return <div data-home-chooser data-shown>{children}</div>;
  if (isPending) {
    return (
      <Card className="min-h-44 overflow-hidden" aria-busy>
        <Skeleton className="h-44 w-full rounded-none" />
      </Card>
    );
  }

  const recent = recentContexts();
  const rank = (slug: string) => {
    const seen = recent.indexOf(slug);
    return seen === -1 ? Number.MAX_SAFE_INTEGER : seen;
  };
  const ordered = [...organisations].sort(
    (a, b) =>
      rank(a.tenant.slug) - rank(b.tenant.slug) ||
      a.tenant.name.localeCompare(b.tenant.name, undefined, { sensitivity: "base" }),
  );
  const shown = ordered.slice(0, SHOWN);
  const more = ordered.length - shown.length;

  return (
    <Card className="min-h-44 overflow-hidden">
      <h2 id="role-chooser-title" className="border-b border-border-token px-5 py-4 text-sm font-semibold">
        {t("welcomeTitle")}
      </h2>
      <ul aria-labelledby="role-chooser-title">
        {isJobSeeker && (
          <li className="border-t border-border-token first:border-t-0">
            <Link href="/matches" className={ROW}>
              <span className="min-w-0">
                <span className="block text-base font-semibold">{t("welcomeSeekerLabel")}</span>
                <span className="mt-0.5 block text-xs text-muted">{t("welcomeSeekerMeta")}</span>
              </span>
              <ChevronRightIcon className="h-4 w-4 shrink-0 text-muted" />
            </Link>
          </li>
        )}
        {shown.map((m) => (
          <li key={m.tenant.slug} className="border-t border-border-token first:border-t-0">
            <Link href={`/employer/${m.tenant.slug}`} className={ROW}>
              <span className="min-w-0">
                <span className="block text-base font-semibold">{m.tenant.name}</span>
                <span className="mt-0.5 block text-xs text-muted">
                  {t(`welcomeOrgMeta.${m.tenant.tenant_type === "course_provider" ? "course_provider" : "employer"}`)}
                </span>
              </span>
              <ChevronRightIcon className="h-4 w-4 shrink-0 text-muted" />
            </Link>
          </li>
        ))}
      </ul>
      <p className="border-t border-border-token bg-surface-muted px-5 py-3 text-xs text-muted">
        {more > 0 ? t("welcomeMore", { count: more }) : t("welcomeNote")}
      </p>
    </Card>
  );
}
