import type { ComponentType, ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import type { IconProps } from "@/components/ui/icons";

/**
 * Where something stands, as a word with a shape (Sprint 87, BL-19.17): an application's or a course
 * interest's state, drawn the same way everywhere it appears. The word says it, the icon repeats it
 * and the tone is the third signal, so **no state rests on colour alone** (WCAG 1.4.1: "Shortlisted"
 * and "Rejected" are told apart by their words and shapes in a greyscale screenshot). A rejection is
 * neutral and not red: it is the employer's decision about a vacancy, not a fault of the person's.
 *
 * Server-safe and kept out of the `ui` barrel, like every component that draws an icon (ADR-089).
 */
export function StatusChip({
  tone,
  icon: Icon,
  children,
  className,
}: {
  tone: "neutral" | "brand" | "good" | "warn" | "bad" | "info";
  icon: ComponentType<IconProps>;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Badge tone={tone} size="md" className={className}>
      <Icon className="h-4 w-4" />
      {children}
    </Badge>
  );
}
