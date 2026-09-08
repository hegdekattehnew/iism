"use client";

import { useTranslations } from "next-intl";

import { EmployerWorkspace } from "@/components/employer/EmployerWorkspace";
import { ProviderWorkspace } from "@/components/employer/ProviderWorkspace";
import { ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { useMemberships, useOrgType } from "@/lib/org";

/**
 * The right workspace for the kind of organisation this is.
 *
 * Nothing in `web/src` read `tenant_type` before, which is why a training
 * provider was handed an employer's screen: a heading about vacancies, and a
 * primary button that returned 403 into a mutation with no error handler.
 */
export function OrgWorkspace({ orgSlug }: { orgSlug: string }) {
  const t = useTranslations("employerWorkspace");
  const tp = useTranslations("providerWorkspace");
  const me = useMemberships();
  const type = useOrgType(orgSlug);

  if (me.isError) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{t("signInPrompt")}</p>
          <ButtonLink href="/signin" className="mt-4">
            {t("signIn")}
          </ButtonLink>
        </CardBody>
      </Card>
    );
  }

  if (me.isPending) return <Skeleton className="h-64 w-full rounded-xl" />;

  // Resolved from memberships, so a slug the caller does not belong to lands
  // here rather than in whichever workspace happened to be the default.
  if (type === null) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-muted">{t("noAccess")}</p>
        </CardBody>
      </Card>
    );
  }

  const provider = type === "course_provider";
  return (
    <>
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          {provider ? tp("title") : t("title")}
        </h1>
        <p className="mt-2 max-w-2xl text-base text-muted">
          {provider ? tp("subtitle") : t("subtitle")}
        </p>
      </header>
      {provider ? (
        <ProviderWorkspace orgSlug={orgSlug} />
      ) : (
        <EmployerWorkspace orgSlug={orgSlug} />
      )}
    </>
  );
}
