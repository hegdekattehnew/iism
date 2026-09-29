import { useTranslations } from "next-intl";

import { ButtonLink, Card, CardBody } from "@/components/ui";

/**
 * "You are signed out" — said out loud, where a panel used to say nothing.
 *
 * Access tokens last fifteen minutes. Before this, every organisation screen
 * treated an expired one exactly as it treats a genuine permission failure:
 * `OrgSettings` said "no access", `EmployerWorkspace` said "no access", and
 * `DeleteOrganisation` rendered **nothing at all**. So somebody who left a tab
 * open over lunch came back to a console that appeared to have quietly
 * revoked their own rights, with no way to tell that signing in again was all
 * it needed.
 *
 * `variant="inline"` for a panel that sits inside a page that is otherwise
 * fine; the default card for a screen whose whole content is gone.
 */
export function SessionExpired({
  variant = "card",
}: {
  variant?: "card" | "inline";
}) {
  const t = useTranslations("auth");

  const body = (
    <>
      <p className="text-sm text-muted">{t("sessionExpired")}</p>
      <ButtonLink href="/signin" size="sm" className="mt-3">
        {t("signInAgain")}
      </ButtonLink>
    </>
  );

  if (variant === "inline") return <div className="mt-8">{body}</div>;
  return (
    <Card>
      <CardBody>{body}</CardBody>
    </Card>
  );
}
