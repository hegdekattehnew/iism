import { getTranslations } from "next-intl/server";

import { StatsBand } from "@/components/StatsBand";
import { ButtonLink, Card, CardBody, CardTitle } from "@/components/ui";

/**
 * A real content page for one audience.
 *
 * Replaces `PlaceholderPage` on the three routes a visitor is most likely to
 * open first. Everything it claims is something the product does today; where a
 * surface is a demonstration rather than a product, it says so on the page
 * rather than in a footnote.
 */
export async function AudiencePage({
  namespace,
  points,
  showStats = false,
  primaryHref,
  secondaryHref,
}: {
  namespace: string;
  points: string[];
  showStats?: boolean;
  primaryHref: string;
  secondaryHref?: string;
}) {
  const t = await getTranslations(namespace);

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-14 sm:py-20">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        {t("title")}
      </h1>
      <p className="mt-4 max-w-2xl text-base text-muted">{t("lede")}</p>

      <div className="mt-8 flex flex-wrap gap-3">
        <ButtonLink href={primaryHref}>{t("primaryCta")}</ButtonLink>
        {secondaryHref && (
          <ButtonLink href={secondaryHref} variant="secondary">
            {t("secondaryCta")}
          </ButtonLink>
        )}
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {points.map((key) => (
          <Card key={key}>
            <CardBody>
              <CardTitle>{t(`${key}.title`)}</CardTitle>
              <p className="mt-2 text-sm text-muted">{t(`${key}.body`)}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      {showStats && (
        <div className="mt-12">
          <StatsBand />
        </div>
      )}

      {/* Said plainly, and on the page. A surface that is a demonstration and
          does not say so is the one thing this sprint must not ship. */}
      <p className="mt-12 rounded-xl border border-border-token bg-surface-muted px-4 py-3 text-sm text-muted">
        {t("status")}
      </p>
    </div>
  );
}
