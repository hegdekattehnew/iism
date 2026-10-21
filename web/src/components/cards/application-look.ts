import {
  AlertTriangleIcon,
  AwardIcon,
  CheckCircleIcon,
  InboxIcon,
  XCircleIcon,
} from "@/components/ui/icons";
import type { components } from "@/lib/api-schema";

// From the generated client, never restated: a hand-written copy let `completed` and `no_show` reach
// this screen with no colour and no compile error.
export type ApplicationStatus = components["schemas"]["ApplicationOut"]["status"];

type Look = { tone: "neutral" | "good" | "warn"; icon: typeof InboxIcon };

/**
 * One row of tokens a status: its tone and its shape. A table over every status the server can say
 * (typed by `Record`, so a new one is a compile error here and not a chip with no shape).
 */
export const APPLICATION_LOOK: Record<ApplicationStatus, Look> = {
  applied: { tone: "neutral", icon: InboxIcon },
  shortlisted: { tone: "good", icon: CheckCircleIcon },
  hired: { tone: "good", icon: AwardIcon },
  rejected: { tone: "neutral", icon: XCircleIcon },
  withdrawn: { tone: "warn", icon: XCircleIcon },
  completed: { tone: "good", icon: CheckCircleIcon },
  no_show: { tone: "warn", icon: AlertTriangleIcon },
};

