import { getTranslations } from "next-intl/server";

import { ButtonLink, Card, Section, SectionHeading } from "@/components/ui";

const AUDIENCES = [
  { key: "candidate", href: "/signin" },
  { key: "employer", href: "/employers" },
  { key: "provider", href: "/providers" },
] as const;

export async function Audiences() {
  const t = await getTranslations("audiences");

  return (
    <Section className="bg-surface-muted">
      <SectionHeading title={t("title")} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {AUDIENCES.map(({ key, href }) => (
          <Card key={key} className="flex flex-col">
            <h3 className="text-lg font-semibold">{t(`${key}Title`)}</h3>
            <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">
              {t(`${key}Body`)}
            </p>
            <div className="mt-5">
              <ButtonLink href={href} variant="secondary" size="sm">
                {t(`${key}Cta`)}
              </ButtonLink>
            </div>
          </Card>
        ))}
      </div>
    </Section>
  );
}
