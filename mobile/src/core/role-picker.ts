/**
 * "What work do you do?" without the screen: grouping a qualification's standards and building the
 * request that adds the ticked ones. Ported from the web's `RolePicker`, with its three rules kept:
 *
 * - **Nothing starts ticked.** Pre-ticking a whole qualification would let the easy path claim
 *   standards nobody affirmed, which is also why the server writes every one as `self_declared`.
 * - **Electives stay in their groups.** Flattened, "choose one of these" reads as "all of these are
 *   required".
 * - **A standard already held is shown ticked and cannot be ticked again**, and is never sent.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";

export type Standard = components["schemas"]["RoleStandardOut"];

export type Group = {
  key: string;
  requirement: Standard["requirement"];
  name: string | null;
  items: Standard[];
};

/** Consecutive standards sharing a requirement and a group, in the server's order. */
export function groupStandards(list: readonly Standard[]): Group[] {
  const groups: Group[] = [];
  for (const s of list) {
    const name = s.group_name ?? null;
    const last = groups[groups.length - 1];
    if (last && last.requirement === s.requirement && last.name === name) {
      last.items.push(s);
    } else {
      groups.push({ key: `${s.requirement}:${name ?? ""}`, requirement: s.requirement, name, items: [s] });
    }
  }
  return groups;
}

/** A new set with `slug` flipped. A standard already held is left alone. */
export function toggle(ticked: ReadonlySet<string>, slug: string, held: ReadonlySet<string>): Set<string> {
  const next = new Set(ticked);
  if (held.has(slug)) return next;
  if (next.has(slug)) next.delete(slug);
  else next.add(slug);
  return next;
}

/** The server refuses more than this many in one request, and refuses the whole batch if it would. */
export const BULK_MAX = 60;
export const PREFERRED_ROLE_MAX = 120;

export type BulkBody = {
  items: { skill_slug: string; proficiency: number }[];
  preferred_role_title: string | null;
};

/**
 * The request for the ticked standards, or `null` when there is nothing to send (the button reads
 * "tick at least one"). Held standards never go, whatever the set says.
 */
export function bulkBody(
  ticked: ReadonlySet<string>,
  held: ReadonlySet<string>,
  proficiency: number,
  preferredRole: string | null,
): BulkBody | null {
  const items = [...ticked]
    .filter((slug) => !held.has(slug))
    .slice(0, BULK_MAX)
    .map((skill_slug) => ({ skill_slug, proficiency }));
  if (items.length === 0) return null;
  const title = preferredRole?.trim().slice(0, PREFERRED_ROLE_MAX) || null;
  return { items, preferred_role_title: title };
}
