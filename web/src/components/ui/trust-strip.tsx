import type { ReactNode } from "react";

import { InfoIcon, ShieldCheckIcon } from "@/components/ui/icons";
import { IconTile } from "@/components/ui/icon-tile";

/**
 * Who is behind a listing and what a visitor is not asked to pay (Sprint 85, BL-19.15; the vacancy
 * page has had the words since Sprint 69, the course page since Sprint 84). The icon is the mark
 * of the state, not the state: a shield on a green tile when the organisation is verified, a plain
 * "i" on a neutral one when it is not **yet**, and the sentence beside it says which, so nothing
 * rests on colour. **A list's card never draws the second one**, it would read as a charge against
 * every organisation not yet reached; this strip lives on a listing's own page only.
 */
export function TrustStrip({
  verified,
  statement,
  children,
}: {
  verified: boolean;
  /** "Verified employer" / "Not yet verified", already translated. */
  statement: string;
  /** The lines under it (what is never asked for, the report link). */
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border-token bg-surface p-4 text-sm shadow-card">
      <IconTile tone={verified ? "good" : "neutral"}>
        {verified ? <ShieldCheckIcon /> : <InfoIcon />}
      </IconTile>
      <div className="min-w-0 flex-1">
        <p className={verified ? "font-medium text-success-text" : "text-muted"}>{statement}</p>
        {children}
      </div>
    </div>
  );
}
