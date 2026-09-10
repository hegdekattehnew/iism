"use client";

import { useTranslations } from "next-intl";

import { useActiveOrg } from "@/components/ContextSwitcher";
import { Badge } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useIsSignedIn } from "@/lib/auth";
import { useMemberships } from "@/lib/org";

/**
 * Which workspace this page belongs to, and who is holding it.
 *
 * Signing in landed a job seeker on `/matches` under the heading "Your
 * matches", and nothing anywhere on the page said whose, or which of the
 * contexts this account can hold it was showing. There was no name, no
 * "signed in as", and no avatar anywhere in `web/src` -- the only hint was the
 * switcher in the header, which reads as a control rather than a statement.
 *
 * The target device is a shared phone, so "which account am I looking at" is a
 * real question with a real wrong answer, not polish.
 *
 * Renders nothing when signed out or still loading: the pages below it already
 * handle both states, and a strip that flickered through "Job seeker" on the
 * way to a sign-in prompt would be worse than no strip.
 */
export function WorkspaceIdentity({
  sibling,
}: {
  sibling: "matches" | "profile";
}) {
  const t = useTranslations("workspace");
  const signedIn = useIsSignedIn();
  const { data, organisations, isJobSeeker, isPending } = useMemberships();
  const active = useActiveOrg();

  if (!signedIn || isPending || !data) return null;

  const org = organisations.find((m) => m.tenant.slug === active);
  const context = org ? org.tenant.name : isJobSeeker ? t("jobSeeker") : null;
  // `full_name` is optional and usually unset until someone fills in their
  // profile, so fall back to the credential they actually signed in with.
  const who = data.full_name || data.phone || data.email;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
      {context && <Badge tone="brand">{context}</Badge>}
      {who && <span className="text-muted">{t("signedInAs", { who })}</span>}
      <span aria-hidden className="text-muted opacity-40">
        ·
      </span>
      <Link
        href={sibling === "matches" ? "/matches" : "/profile"}
        className="font-medium text-brand underline-offset-4 hover:underline"
      >
        {t(sibling === "matches" ? "goToMatches" : "goToProfile")}
      </Link>
    </div>
  );
}
