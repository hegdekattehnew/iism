import { getTranslations } from "next-intl/server";

import {
  ButtonLink,
  Card,
  CardBody,
  Section,
  SectionHeading,
} from "@/components/ui";

// These cards already described the three entities; now they are the way in.
// Every route to an account used to land on the candidate phone form, so an
// employer was two clicks behind a marketing page and a training provider had
// no registration path anywhere in the product.
const AUDIENCES = [
  { key: "candidate", href: "/signup/seeker" },
  { key: "employer", href: "/signup/employer" },
  { key: "provider", href: "/signup/provider" },
] as const;

export async function Audiences() {
  const t = await getTranslations("audiences");

  return (
    <Section className="bg-surface-muted">
      <SectionHeading title={t("title")} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {AUDIENCES.map(({ key, href }) => (
          <Card key={key}>
            {/* `Card` is the border, `CardBody` the padding. `h-full` so the
                three cards match height and their buttons line up. */}
            <CardBody className="flex h-full flex-col">
              <h3 className="text-lg font-semibold">{t(`${key}Title`)}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">
                {t(`${key}Body`)}
              </p>
              <div className="mt-5">
                <ButtonLink href={href} variant="secondary" size="sm">
                  {t(`${key}Cta`)}
                </ButtonLink>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </Section>
  );
}
