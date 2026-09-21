"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

/** Appended to a landing path when a signup turned out to be a sign-in. */
export const WELCOME_BACK = "welcome=back";

/**
 * "You already had an account."
 *
 * Signing up with a number or address that is already registered sends a code
 * and signs you in -- deliberately, because telling the caller "this user
 * exists" at request time would let anyone test which numbers are registered
 * (ADR-038). But the interface then said nothing at all, so a returning user
 * who thought they were creating an account was dropped somewhere with no
 * explanation. This says it, and only after the code has proved the number is
 * theirs.
 */
export function ReturningNotice() {
  // `useSearchParams` in a statically rendered page needs a boundary, or the
  // build bails the whole route out of prerendering.
  return (
    <Suspense fallback={null}>
      <Notice />
    </Suspense>
  );
}

function Notice() {
  const t = useTranslations("returning");
  const params = useSearchParams();
  if (params.get("welcome") !== "back") return null;
  return (
    <p
      role="status"
      className="mb-6 rounded-lg border border-border-token bg-accent-soft px-4 py-3 text-sm"
    >
      {t("back")}
    </p>
  );
}
