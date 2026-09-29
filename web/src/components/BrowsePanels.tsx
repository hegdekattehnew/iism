import { getTranslations } from "next-intl/server";

import { LiveCount } from "@/components/LiveCount";
import {
  ButtonLink,
  Card,
  CardBody,
  Section,
  SectionHeading,
} from "@/components/ui";

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
          <Card key={key}>
            {/* `Card` carries the border; `CardBody` carries the padding.
                Without it the text sits flush against the border. */}
            <CardBody className="flex h-full flex-col">
              <h3 className="text-lg font-semibold">{t(`${key}Title`)}</h3>
              {/* `flex-1` so the description absorbs the slack: without it a
                  two-line body pushes that card's count and button lower than
                  its neighbours', and the row reads as crooked. */}
              <p className="mt-2 flex-1 text-sm leading-relaxed text-muted">
                {t(`${key}Body`)}
              </p>

              {/* The label lives inside `LiveCount` now. The jobs panel says
                  how many vacancies are still open under its headline figure,
                  and whether that line appears depends on the numbers -- which
                  this server component never sees. */}
              <LiveCount kind={key} />

              <div className="mt-5">
                <ButtonLink href={href} variant="secondary" size="sm">
                  {t("browseCta")}
                </ButtonLink>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </Section>
  );
}
