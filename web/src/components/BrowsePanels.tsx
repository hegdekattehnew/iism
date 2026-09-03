import { getTranslations } from "next-intl/server";

import { LiveCount } from "@/components/LiveCount";
import { ButtonLink, Card, Section, SectionHeading } from "@/components/ui";

const PANELS = [
  { key: "jobs", href: "/jobs" },
  { key: "courses", href: "/courses" },
  { key: "skills", href: "/skills" },
] as const;

export async function BrowsePanels() {
  const t = await getTranslations("browse");

  return (
    <Section>
      <SectionHeading title={t("title")} subtitle={t("subtitle")} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {PANELS.map(({ key, href }) => (
          <Card key={key} className="flex flex-col">
            <h3 className="text-lg font-semibold">{t(`${key}Title`)}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              {t(`${key}Body`)}
            </p>

            <div className="mt-6 flex items-baseline gap-2">
              <LiveCount kind={key} />
              <span className="text-xs text-muted">{t("countLabel")}</span>
            </div>

            <div className="mt-5">
              <ButtonLink href={href} variant="secondary" size="sm">
                {t("browseCta")}
              </ButtonLink>
            </div>
          </Card>
        ))}
      </div>
    </Section>
  );
}
