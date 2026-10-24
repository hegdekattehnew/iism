import type { ReactElement } from "react";

import { IconTile } from "@/components/ui/icon-tile";
import {
  AlertTriangleIcon,
  AwardIcon,
  BellIcon,
  BookOpenIcon,
  BriefcaseIcon,
  CalendarIcon,
  InboxIcon,
  InfoIcon,
  TargetIcon,
} from "@/components/ui/icons";

/**
 * What kind of news a notice is, as a shape (Sprint 87, BL-19.17). One table over the templates the
 * outbox writes (`lib/notice-text` is the words; this is the picture), with the bell for any a
 * later sprint adds before it is given one. **The words are the notice**: the tile is hidden from a
 * screen reader and never carries meaning alone; a new notice is also marked "New" in words.
 *
 * Here and not in `lib/notice-text`: that module is imported by more than the two lists that show
 * a notice, and an icon import there would put the icon factory on routes that never draw one.
 */
const ICONS: Record<string, ReactElement> = {
  application_status_changed: <BriefcaseIcon />,
  application_status_message: <InboxIcon />,
  job_alert: <TargetIcon />,
  vacancy_closed: <AlertTriangleIcon />,
  course_interest_status_changed: <BookOpenIcon />,
  sponsor_offer: <AwardIcon />,
  batch_cancelled: <CalendarIcon />,
  grievance_update: <InfoIcon />,
};

/** The notice kinds that have their own shape (the bell is every other). A test holds this equal to the words' switch. */
export const NOTICE_TEMPLATES_WITH_ICONS = Object.keys(ICONS);

export function NoticeTile({ template, unread }: { template: string; unread: boolean }) {
  return (
    <IconTile size="sm" tone={unread ? "brand" : "neutral"}>
      {ICONS[template] ?? <BellIcon />}
    </IconTile>
  );
}
