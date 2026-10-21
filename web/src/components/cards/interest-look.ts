import { AwardIcon, CheckIcon, ClockIcon, XCircleIcon } from "@/components/ui/icons";
import type { components } from "@/lib/api-schema";

// From the generated client, never restated: a hand-written three-value copy let `enrolled` reach this
// screen with no colour and no wording, so a learner who had been enrolled saw a raw message key.
export type InterestStatus = components["schemas"]["InterestOut"]["status"];
type Look = { tone: "neutral" | "good" | "warn"; icon: typeof ClockIcon };

/** A shape and a tone for every state a provider can set (typed by `Record`: a new one fails to compile). */
export const INTEREST_LOOK: Record<InterestStatus, Look> = {
  registered: { tone: "neutral", icon: ClockIcon },
  contacted: { tone: "good", icon: CheckIcon },
  enrolled: { tone: "good", icon: AwardIcon },
  withdrawn: { tone: "warn", icon: XCircleIcon },
};

