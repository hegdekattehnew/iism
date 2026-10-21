import { CheckCircleIcon, ClockIcon, InboxIcon, XCircleIcon } from "@/components/ui/icons";
import type { GrievanceStatus } from "@/lib/grievances";

/**
 * A tone and a shape for every status a message can have (Sprint 89, BL-19.19/19.20), typed by `Record` so
 * a new status fails to compile. **Here, not in the operator's queue**: the person's own list of what
 * they sent (`/grievance`) draws the same chip, and must not import the back office to do it.
 */
export const GRIEVANCE_LOOK: Record<
  GrievanceStatus,
  { tone: "warn" | "brand" | "good" | "neutral"; icon: typeof ClockIcon }
> = {
  open: { tone: "warn", icon: ClockIcon },
  acknowledged: { tone: "brand", icon: InboxIcon },
  resolved: { tone: "good", icon: CheckCircleIcon },
  dismissed: { tone: "neutral", icon: XCircleIcon },
};
