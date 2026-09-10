"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CreateOrgForm } from "@/components/CreateOrgForm";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { useMemberships } from "@/lib/org";

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
 */

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
    // The organisation's root, not a rewritten segment of the current path: a
    // job slug belonging to the organisation being left would 404 under the one
    // being entered.
    router.push(slug ? `/employer/${slug}` : "/matches");
  };

  return (
    <div className={stacked ? "" : "relative"}>
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

          {organisations.map((m) => (
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
              <span className="block text-xs text-muted">
                {t(`role.${m.role}`)}
              </span>
            </button>
          ))}

          <div className="mt-1 border-t border-border-token pt-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
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
