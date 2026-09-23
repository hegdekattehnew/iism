"use client";

import { useTranslations } from "next-intl";
import { useCallback, useMemo, useRef, useState } from "react";

import { CreateOrgForm } from "@/components/CreateOrgForm";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { useMemberships } from "@/lib/org";
import { recentContexts } from "@/lib/context";
import { useDismiss } from "@/lib/use-dismiss";

/**
 * Which hat the person is wearing, and how to change it.
 *
 * **The context is derived from the URL, never stored.** A path under
 * `/employer/{slug}` *is* that organisation's context; anything else is the
 * job-seeker context. That is ADR-038's own rule — the tenant is named by the
 * request and granted by the membership — applied to the client, and it buys
 * three things: the context is shareable and survives a reload, two tabs can be
 * two organisations at once, and what the interface believes can never drift
 * from what the API will authorise.
 *
 * Without this control `/employer/{slug}` had no inbound link from anywhere a
 * signed-in person could already be. Signing in by phone and clicking "My
 * profile" once left the workspace reachable only by typing its URL.
 *
 * **It has to survive ten organisations, and it did not.** Measured with ten:
 * the panel was 656px tall on a 720px laptop -- 91% of the screen -- and on the
 * 360x640 phone this product targets, the open mobile nav came to 1311px,
 * more than twice the screen, with 355px of scrolling needed to reach the last
 * organisation and the "Create an organisation" button below all of it. Sprint
 * 26 deliberately refused to cap how many organisations one account may hold
 * (a staffing agency legitimately has several), so the control has to cope.
 *
 * Three things make it cope, in order of how much they matter:
 *
 * 1. **The list scrolls inside a bounded box.** The panel can no longer grow
 *    past a fraction of the screen however many organisations there are.
 * 2. **The job-seeker row and "Create an organisation" sit outside that box**,
 *    so neither is ever pushed off the bottom by the list between them.
 * 3. **A filter appears once there are enough to be worth filtering**, and the
 *    order is current first, then recently used, then alphabetical -- so the
 *    two you actually move between are at the top and the rest are scannable.
 */

/** Below this many organisations a filter box is noise: the whole list is
 *  already visible and typing is slower than pointing at it. */
const FILTER_THRESHOLD = 6;

/** The organisation slug the current path is acting in, or null for job seeker. */
export function useActiveOrg(): string | null {
  const pathname = usePathname();
  return pathname.match(/^\/employer\/([^/]+)/)?.[1] ?? null;
}

export function ContextSwitcher({ stacked = false }: { stacked?: boolean }) {
  const t = useTranslations("context");
  const router = useRouter();
  const signedIn = useIsSignedIn();
  const { organisations, isJobSeeker, isPending } = useMemberships();
  const active = useActiveOrg();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  // Escape and click-away. Until Sprint 26 this menu closed only when its own
  // toggle was pressed again -- there was no keydown handler anywhere in
  // `web/src`, and Escape is the first thing anybody tries.
  useDismiss(
    root,
    open,
    // Clears the filter too: reopening to a list that is already narrowed,
    // with no memory of having typed, reads as "my organisations are missing".
    useCallback(() => {
      setOpen(false);
      setQuery("");
    }, []),
  );

  // Current first, then most recently used, then alphabetical. The last of
  // those is what makes a long tail scannable; the first two are what mean
  // most people never reach the tail at all.
  const ordered = useMemo(() => {
    const recent = recentContexts();
    const rank = (slug: string) => {
      if (slug === active) return -1;
      const seen = recent.indexOf(slug);
      return seen === -1 ? Number.MAX_SAFE_INTEGER : seen;
    };
    return [...organisations].sort((a, b) => {
      const byRank = rank(a.tenant.slug) - rank(b.tenant.slug);
      return byRank !== 0
        ? byRank
        : a.tenant.name.localeCompare(b.tenant.name, undefined, { sensitivity: "base" });
    });
  }, [organisations, active]);

  // Nothing to switch between until there is a second context to offer. The
  // "create an organisation" entry below is why this is not simply hidden for
  // everyone with no organisation.
  if (!signedIn) return null;

  // Until `/auth/me` resolves, `organisations` is empty and `isJobSeeker` is
  // false -- which are the same values an organisation-only account has. Every
  // signed-in job seeker therefore watched their own header read "Switch" and
  // then change to "Job seeker" a moment later. Say nothing rather than
  // something wrong: the fallback below is a real state, not a loading one.
  if (isPending) {
    return (
      <div className={stacked ? "" : "relative"}>
        <div
          aria-hidden
          className="h-[34px] w-32 animate-pulse rounded-lg border border-border-token bg-surface-muted"
        />
      </div>
    );
  }

  const current = organisations.find((m) => m.tenant.slug === active);

  const needle = query.trim().toLowerCase();
  // Matches the name *or* the slug: somebody who knows the URL of the
  // organisation they want should be able to type that.
  const shown = needle
    ? ordered.filter(
        (m) =>
          m.tenant.name.toLowerCase().includes(needle) ||
          m.tenant.slug.toLowerCase().includes(needle),
      )
    : ordered;
  const showFilter = organisations.length >= FILTER_THRESHOLD;
  const label = current
    ? current.tenant.name
    : isJobSeeker
      ? t("jobSeeker")
      : // An organisation-only account standing outside any `/employer/` path
        // genuinely has no current context. This names the thing being chosen;
        // it used to read "Switch", a verb with no object, which said neither
        // where you were nor where you could go.
        t("chooseContext");

  const go = (slug: string | null) => {
    setOpen(false);
    setQuery("");
    // The organisation's root, not a rewritten segment of the current path: a
    // job slug belonging to the organisation being left would 404 under the one
    // being entered.
    router.push(slug ? `/employer/${slug}` : "/matches");
  };

  return (
    <div className={stacked ? "" : "relative"} ref={root}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex w-full items-center gap-2 rounded-lg border border-border-token px-3 py-1.5 text-sm transition-colors hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <span className="max-w-[12rem] truncate">{label}</span>
        <svg
          viewBox="0 0 20 20"
          className="h-3.5 w-3.5 shrink-0 opacity-60"
          aria-hidden
        >
          <path
            d="M5 8l5 5 5-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className={
            stacked
              ? "mt-2 rounded-lg border border-border-token bg-surface p-1"
              : "absolute right-0 z-50 mt-2 w-64 rounded-lg border border-border-token bg-surface p-1 shadow-lg"
          }
        >
          {/* The menu says what it is a menu of. Without it the list reads as
              an account menu, and the job-seeker row looks like a link to a
              page rather than the context you are currently standing in. */}
          <p className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-muted uppercase">
            {t("menuHeading")}
          </p>

          {/* Only for someone who actually asked to look for work. An account
              created as an employer or a provider has no personal workspace,
              and offering it a job-seeker context it never chose is exactly the
              assumption this sprint exists to remove. */}
          {isJobSeeker && (
            <button
              type="button"
              role="menuitem"
              onClick={() => go(null)}
              className={`block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-surface-muted ${
                active === null ? "font-semibold text-brand" : ""
              }`}
            >
              {t("jobSeeker")}
              <span className="block text-xs text-muted">
                {t("jobSeekerHint")}
              </span>
            </button>
          )}

          {showFilter && (
            <div className="px-1 pb-1">
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("filterPlaceholder")}
                aria-label={t("filterLabel")}
                className="w-full rounded-md border border-input-border bg-surface px-2.5 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              />
            </div>
          )}

          {/* **The bounded box.** Everything above and below it stays put;
              only this scrolls. `min()` rather than a fixed height so it is a
              fraction of a small screen and a sensible cap on a large one. */}
          <div className="max-h-[min(50vh,18rem)] overflow-y-auto">
            {shown.length === 0 && (
              <p className="px-3 py-2 text-sm text-muted">{t("filterEmpty")}</p>
            )}
            {shown.map((m) => (
              <button
                key={m.tenant.slug}
                type="button"
                role="menuitem"
                onClick={() => go(m.tenant.slug)}
                className={`block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-surface-muted ${
                  m.tenant.slug === active ? "font-semibold text-brand" : ""
                }`}
              >
                {m.tenant.name}
                {/* The **type**, not just the role. One account may now hold
                    several organisations (Sprint 26 deliberately did not cap
                    that), and two with similar names were indistinguishable in
                    the one control whose whole job is telling them apart. */}
                <span className="block text-xs text-muted">
                  {m.tenant.tenant_type === "course_provider"
                    ? t("typeProviderShort")
                    : t("typeEmployerShort")}
                  {" · "}
                  {t(`role.${m.role}`)}
                </span>
              </button>
            ))}

          </div>

          {/* Outside the scroll box on purpose: with ten organisations this
              button used to sit below all of them, off the bottom of a phone
              screen -- the one action somebody opens this menu to take when
              they cannot find what they are looking for. */}
          <div className="mt-1 border-t border-border-token pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                setQuery("");
                setCreating(true);
              }}
              className="block w-full rounded-md px-3 py-2 text-left text-sm text-brand hover:bg-surface-muted"
            >
              {t("createOrg")}
            </button>
            {organisations.length === 0 && (
              <Link
                href="/employers"
                onClick={() => setOpen(false)}
                className="block rounded-md px-3 py-2 text-xs text-muted hover:bg-surface-muted"
              >
                {t("whatIsThis")}
              </Link>
            )}
          </div>
        </div>
      )}

      {creating && (
        <CreateOrgForm
          onClose={() => setCreating(false)}
          onCreated={(slug) => {
            setCreating(false);
            router.push(`/employer/${slug}`);
          }}
        />
      )}
    </div>
  );
}
