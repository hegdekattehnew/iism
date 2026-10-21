import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, XCircleIcon } from "@/components/ui/icons";

/**
 * Where a vacancy or a course stands on its owner's list, as a tone and a shape (Sprint 88, BL-19.18).
 * Four states, not two: a closed vacancy is still published (its page is there), so "published" would
 * call it open when it is not, and an operator's takedown is its own state with its own colour.
 * The words stay the page's (`removed`, `draft`, `published`, `closed_*`); this is the picture.
 */
export type ListingState = "removed" | "draft" | "live" | "closed";

export const LISTING_LOOK: Record<
  ListingState,
  { tone: "bad" | "warn" | "good" | "neutral"; icon: typeof ClockIcon }
> = {
  removed: { tone: "bad", icon: AlertTriangleIcon },
  draft: { tone: "warn", icon: ClockIcon },
  live: { tone: "good", icon: CheckCircleIcon },
  closed: { tone: "neutral", icon: XCircleIcon },
};

/** The state of a vacancy, from the fields the owner's list carries. A takedown wins, then a draft, then closed. */
export function jobState(job: { taken_down_at?: string | null; status: string; is_open?: boolean }): ListingState {
  if (job.taken_down_at) return "removed";
  if (job.status !== "published") return "draft";
  return job.is_open ? "live" : "closed";
}

/** The state of a course: it has no "closed". */
export function courseState(course: { taken_down_at?: string | null; status: string }): Exclude<ListingState, "closed"> {
  if (course.taken_down_at) return "removed";
  return course.status === "published" ? "live" : "draft";
}
