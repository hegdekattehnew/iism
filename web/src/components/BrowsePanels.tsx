import { getTranslations } from "next-intl/server";

import { LiveCount } from "@/components/LiveCount";
import { IconTile } from "@/components/ui/icon-tile";
import { AwardIcon, BriefcaseIcon, GraduationCapIcon } from "@/components/ui/icons";
import {
  ButtonLink,
  Card,
  CardBody,
  Section,
  SectionHeading,
} from "@/components/ui";

// An icon per panel (Sprint 85, BL-19.15): the first thing the eye finds in each tile, so the three
// read apart before a word is read. A server component, so the icons cost no JavaScript here.
const PANELS = [
  { key: "jobs", href: "/jobs", icon: BriefcaseIcon },
  { key: "courses", href: "/courses", icon: GraduationCapIcon },
  { key: "skills", href: "/skills", icon: AwardIcon },
] as const;

export async function BrowsePanels() {
  const t = await getTranslations("browse");

  return (
    <Section>
      <SectionHeading title={t("title")} subtitle={t("subtitle")} />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {PANELS.map(({ key, href, icon: Icon }) => (
          <Card key={key}>
            {/* `Card` carries the border; `CardBody` carries the padding.
                Without it the text sits flush against the border. */}
            <CardBody className="flex h-full flex-col">
              <div className="flex items-center gap-3">
                <IconTile>
                  <Icon />
                </IconTile>
                <h3 className="text-lg font-semibold">{t(`${key}Title`)}</h3>
              </div>
              {/* `flex-1` so the description absorbs the slack: without it a
                  two-line body pushes that card's count and button lower than
                  its neighbours', and the row reads as crooked. */}
              <p className="mt-3 flex-1 text-sm leading-relaxed text-muted">
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
