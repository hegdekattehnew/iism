import {
  CheckCircleIcon,
  CheckIcon,
  ClockIcon,
  InfoIcon,
  UsersIcon,
  XCircleIcon,
} from "@/components/ui/icons";
import type { BatchPhase } from "@/lib/batches";

/**
 * A batch's phase as a tone and a shape (Sprint 98, ADR-103): six phases, six shapes, so no phase
 * rests on colour alone. Typed over the server's own union, so a new phase is a compile error and not
 * a chip with no shape. **Full is information, not a fault** (a good batch fills), a running batch is
 * the brand's own colour (it is the thing that cannot be stopped), and a cancellation is a warning:
 * it was planned and is not happening. A table of looks that the organisation's list and the
 * learner-facing lists of Sprint 100 both draw is its own module (ADR-097).
 */
export const BATCH_LOOK: Record<
  BatchPhase,
  { tone: "neutral" | "brand" | "good" | "warn" | "info"; icon: typeof ClockIcon }
> = {
  draft: { tone: "neutral", icon: InfoIcon },
  open: { tone: "good", icon: CheckCircleIcon },
  full: { tone: "info", icon: UsersIcon },
  running: { tone: "brand", icon: ClockIcon },
  finished: { tone: "neutral", icon: CheckIcon },
  cancelled: { tone: "warn", icon: XCircleIcon },
};
