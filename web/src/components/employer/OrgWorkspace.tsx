"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";

import { ButtonLink, Card, CardBody, Skeleton } from "@/components/ui";
import { useMemberships, useOrgType } from "@/lib/org";

/**
 * **Neither workspace is in the route's first load** (Sprint 88, BL-19.18). The page used to import
 * both, so every organisation downloaded the other kind's screen too, and once the workspaces gained
 * status shapes and dashboard tiles the route went past the 700 KB ceiling (703,701 bytes). A visit
 * needs exactly one, and only after the memberships say which: each is a `next/dynamic` chunk at module
 * level, and the placeholder is the same `Skeleton` the memberships wait shows, in the same place, so
 * nothing moves when the real screen arrives. `workspace-structure.test.ts` fails on a static import.
 */
const loading = () => <Skeleton className="h-64 w-full rounded-xl" />;
const EmployerWorkspace = dynamic(
  () => import("@/components/employer/EmployerWorkspace").then((m) => m.EmployerWorkspace),
  { loading },
);
const ProviderWorkspace = dynamic(
  () => import("@/components/employer/ProviderWorkspace").then((m) => m.ProviderWorkspace),
  { loading },
);

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
