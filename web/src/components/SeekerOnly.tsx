"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { ButtonLink, Card, CardBody } from "@/components/ui";
import { useIsSignedIn } from "@/lib/auth";
import { useMemberships } from "@/lib/org";

/**
 * A job-seeker surface, shown only to someone who signed up to look for work.
 *
 * An organisation-first account has no personal membership. `/matches` and
 * `/profile` used to render for it anyway -- the profile page walked it into
 * the candidate onboarding wizard -- because every candidate surface checked
 * only whether *someone* was signed in. The API now refuses those routes to
 * such an account; this is the interface saying the same thing in words rather
 * than as an error state.
 *
 * Signed out, the children render: they carry their own sign-in prompts.
 * Signed in and still loading, nothing renders, rather than a candidate page
 * that is about to be withdrawn.
 */
export function SeekerOnly({ children }: { children: ReactNode }) {
  const t = useTranslations("seekerOnly");
  const signedIn = useIsSignedIn();
  const { data, isPending, isJobSeeker, organisations } = useMemberships();

  if (!signedIn) return <>{children}</>;
  if (isPending || !data) return null;
  if (isJobSeeker) return <>{children}</>;

  const only = organisations.length === 1 ? organisations[0] : null;
  return (
    <Card>
      <CardBody>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="mt-2 text-sm text-muted">{t("body")}</p>
        {only && (
          <ButtonLink href={`/employer/${only.tenant.slug}`} className="mt-4">
            {t("goToWorkspace")}
          </ButtonLink>
        )}
      </CardBody>
    </Card>
  );
}
