/** Page-structure and brand components.
 *
 * Carried over unchanged from the original `ui.tsx`. These are composition, not
 * interaction — there is no accessibility gap for a Radix primitive to close,
 * so rewriting them would be churn.
 */

import type { ReactNode } from "react";

export function Section({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`px-5 py-14 sm:py-20 ${className}`}>
      <div className="mx-auto w-full max-w-6xl">{children}</div>
    </section>
  );
}

export function SectionHeading({
  title,
  subtitle,
  align = "left",
}: {
  title: string;
  subtitle?: string;
  align?: "left" | "center";
}) {
  return (
    <div className={`mb-10 ${align === "center" ? "text-center" : ""}`}>
      <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h2>
      {subtitle && (
        <p
          className={`mt-2 max-w-2xl text-base text-muted ${
            align === "center" ? "mx-auto" : ""
          }`}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border-token bg-surface p-6 ${className}`}
    >
      {children}
    </div>
  );
}

export function Logo({ withWordmark = true }: { withWordmark?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg viewBox="0 0 64 64" aria-hidden className="h-8 w-8 shrink-0">
        <rect width="64" height="64" rx="14" className="fill-brand" />
        <g fill="none" stroke="var(--brand-contrast)" strokeWidth="3.2" strokeLinecap="round">
          <circle cx="20" cy="20" r="5.5" />
          <circle cx="44" cy="20" r="5.5" />
          <circle cx="32" cy="45" r="5.5" />
          <path d="M25 22.5 39 22.5M23 25 30 40M41 25 34 40" />
        </g>
      </svg>
      {withWordmark && (
        <span className="text-lg font-bold tracking-tight">IISM</span>
      )}
    </span>
  );
}
