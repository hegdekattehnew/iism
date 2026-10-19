"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { IconTile } from "@/components/ui/icon-tile";
import { AwardIcon } from "@/components/ui/icons";
import { Link } from "@/i18n/navigation";

export type StandardRow = {
  slug: string;
  name: string;
  description?: string | null;
  skill_type?: "technical" | "core" | "generic";
  nsqf_level?: number | null;
  qp_count?: number;
  nos_code?: string | null;
  context?: {
    awarding_body?: string | null;
    sector?: string | null;
    qualification_code?: string | null;
    qualification_name?: string | null;
  } | null;
  matched_on?: string | null;
  match_kind?: "exact" | "prefix" | "alias" | "text";
};

/**
 * What tells a standard apart from another with the same name.
 *
 * A quarter of the corpus shares its name with another standard -- searching
 * "General Duty Assistant" returned two cards both titled "Broad Functions of
 * General Duty Assistant", identical until opened. The code and the
 * qualification each belongs to are what differ, so every card shows them.
 */
export function StandardOrigin({ row, lookalike }: { row: StandardRow; lookalike: boolean }) {
  const t = useTranslations("skillsPage");
  const c = row.context;
  return (
    <>
      {row.nos_code && <p className="mt-1 font-mono text-xs text-muted">{row.nos_code}</p>}
      {c?.qualification_name && (
        <p className="mt-1.5 text-xs text-muted">
          {t("partOf", { name: c.qualification_name })}
          {c.qualification_code && <span className="ml-1 font-mono text-xs">({c.qualification_code})</span>}
        </p>
      )}
      {(c?.awarding_body || c?.sector) && (
        <p className="mt-0.5 text-xs text-muted">
          {/* A Sector Skill Council is often stored under its sector's own
              name ("Healthcare"), which printed "Healthcare · Healthcare". */}
          {[...new Set([c.awarding_body, c.sector].filter(Boolean))].join(" · ")}
        </p>
      )}
      {lookalike && <p className="mt-2 text-xs text-warning-text">{t("lookalike")}</p>}
    </>
  );
}

/** Names that appear more than once on the page, compared as a reader would. */
export function lookalikeNames(rows: { name: string }[]): Set<string> {
  const seen = new Map<string, number>();
  for (const r of rows) {
    const key = r.name.trim().toLowerCase();
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }
  return new Set([...seen].filter(([, n]) => n > 1).map(([k]) => k));
}

/** Levels arrive as numbers: 4 renders as "4", 4.5 as "4.5". A trailing ".0" on a whole level is noise. */
export const formatLevel = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

const TYPE_TONE = { technical: "brand", core: "warn", generic: "neutral" } as const;

/**
 * One standard on a list, on the same card as a vacancy and a course (Sprint 85, BL-19.15): a mark,
 * the kind and level as chips, the name, where it comes from and (when the list has one) a line of
 * what it says. The standards browser and the search results both draw it, so a standard reads the
 * same wherever it is found. `heading` is the level the page needs (the browser's cards are `h2`;
 * under a search band's own `h2` they are `h3`). `compact` is the form a search band uses: it leaves
 * out the line of description and the usage count, which a person scanning six results has not asked
 * for (the first version without it made the search page 16 percent taller).
 */
export function StandardCard({
  row,
  lookalike,
  heading: Heading = "h2",
  compact = false,
}: {
  row: StandardRow;
  lookalike: boolean;
  heading?: "h2" | "h3";
  compact?: boolean;
}) {
  const t = useTranslations("skillsPage");
  const tType = useTranslations("skillsPage.type");
  return (
    <Link
      href={`/skills/${row.slug}`}
      className="block h-full rounded-xl border border-border-token bg-surface p-4 shadow-card transition-shadow hover:border-brand hover:shadow-raised"
    >
      <div className="flex items-start gap-3">
        <IconTile>
          <AwardIcon />
        </IconTile>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {row.skill_type && <Badge tone={TYPE_TONE[row.skill_type]}>{tType(row.skill_type)}</Badge>}
            {row.nsqf_level != null && <Badge>{t("levelShort", { level: formatLevel(row.nsqf_level) })}</Badge>}
            {/* Why this sorts where it does, and a real signal of how central the unit is to the framework. */}
            {!compact && (row.qp_count ?? 0) > 0 && (
              <span className="text-xs text-muted">{t("usedInQps", { count: row.qp_count ?? 0 })}</span>
            )}
          </div>
          <Heading className="mt-2 text-base font-semibold">{row.name}</Heading>
          <StandardOrigin row={row} lookalike={lookalike} />
          {!compact && row.description && <p className="mt-1.5 line-clamp-2 text-sm text-muted">{row.description}</p>}
          {/* Why this matched. Without it a transliterated hit looks wrong. */}
          {row.matched_on && row.match_kind === "alias" && (
            <p className="mt-3 text-xs text-brand">{t("matchedVia", { term: row.matched_on })}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
