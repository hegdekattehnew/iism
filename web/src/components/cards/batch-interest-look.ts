import { AwardIcon, CheckIcon, ClockIcon, InboxIcon, XCircleIcon } from "@/components/ui/icons";
import type { BatchInterestStatus } from "@/lib/batches";

/**
 * A learner's interest in a batch as a tone and a shape (Sprint 100, ADR-103): five states, five
 * shapes, so none rests on colour alone. Typed over the server's own union, so a new status is a
 * compile error and not a chip with no shape. **Withdrawn is a warning only because the learner did
 * it and the centre no longer has their details**; waiting is neutral (nobody has done anything
 * wrong), and being enrolled or having attended are the two good ends.
 */
export const BATCH_INTEREST_LOOK: Record<
  BatchInterestStatus,
  { tone: "neutral" | "brand" | "good" | "warn"; icon: typeof ClockIcon }
> = {
  registered: { tone: "neutral", icon: ClockIcon },
  contacted: { tone: "brand", icon: InboxIcon },
  enrolled: { tone: "good", icon: CheckIcon },
  attended: { tone: "good", icon: AwardIcon },
  withdrawn: { tone: "warn", icon: XCircleIcon },
};
