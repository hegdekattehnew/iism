import { getTranslations } from "next-intl/server";

import {
  ButtonLink,
  Card,
  CardBody,
  Section,
  SectionHeading,
} from "@/components/ui";

// The *argument*, not the router. These pointed at `/signup/{type}` -- the
// same three hrefs `RoleChooser` now offers in the hero, about 900px higher on
// the same page. A visitor meeting the identical three destinations twice in
// different clothes learns nothing the second time, and no amount of restyling
// fixes that.
//
// So the two are split by what the visitor is asking. The hero chooser answers
// "where do I go?"; this section answers "why would I?", and sends each side to
// the page that argues the case. `/employers` and `/providers` are real content
// pages that the homepage did not link to at all -- only the header nav did.
const AUDIENCES = [
  { key: "candidate", href: "/#how-it-works" },
  { key: "employer", href: "/employers" },
  { key: "provider", href: "/providers" },
] as const;

export async function Audiences() {
  const t = await getTranslations("audiences");

  return (
    <Section className="bg-surface-muted">
      <SectionHeading title={t("title")} subtitle={t("subtitle")} />

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
