import { CheckCircleIcon, XCircleIcon } from "@/components/ui/icons";
import type { Centre } from "@/lib/centres";

/**
 * A centre's state as a tone and a shape (Sprint 95, ADR-102): **open or closed** is the
 * organisation's own doing; the *address checked* mark is an operator's, and is never the
 * organisation's mark. Typed over the server's union, so a new status is a compile error. A table of
 * looks that the organisation's list and the manager's page both draw is its own module (ADR-097), so
 * neither imports the other's screen to read it.
 */
export const CENTRE_STATE_LOOK: Record<
  Centre["status"],
  { tone: "good" | "neutral"; icon: typeof CheckCircleIcon }
> = {
  active: { tone: "good", icon: CheckCircleIcon },
  closed: { tone: "neutral", icon: XCircleIcon },
};
