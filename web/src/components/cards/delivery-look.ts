import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, XCircleIcon } from "@/components/ui/icons";
import type { Arrangement } from "@/lib/delivery";

/**
 * An arrangement's state as a tone and a shape (Sprint 97, ADR-102): four states, four shapes, so no
 * state rests on colour alone. A refusal is neutral (it is somebody's decision, not a fault) and an
 * ended arrangement is a warning, because it was in force and is not. Typed over the server's own
 * union, so a new state is a compile error and not a chip with no shape.
 */
export const DELIVERY_LOOK: Record<
  Arrangement["state"],
  { tone: "info" | "good" | "neutral" | "warn"; icon: typeof ClockIcon }
> = {
  requested: { tone: "info", icon: ClockIcon },
  approved: { tone: "good", icon: CheckCircleIcon },
  declined: { tone: "neutral", icon: XCircleIcon },
  revoked: { tone: "warn", icon: AlertTriangleIcon },
};
