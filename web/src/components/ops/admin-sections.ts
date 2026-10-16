/**
 * The back office's sections, in the order an operator needs them (Sprint 73, UI-16).
 *
 * One list read by the nav **and** by the page, so a link can never point at an id the page does not
 * have. The first four are the daily work and stay open: something waits there, and a person who
 * opens `/admin` should see it without a click. The rest are reference panels that fold away and are
 * only loaded when opened; `enrolment` is the admin tier's alone (`OPS_ENROL`).
 */
export const DAILY_SECTIONS = ["overview", "verification", "grievances", "reports"] as const;
export const FOLDED_SECTIONS = ["programmes", "districts", "aliases", "enrolment"] as const;
export const ADMIN_SECTIONS = [...DAILY_SECTIONS, ...FOLDED_SECTIONS] as const;
export type AdminSection = (typeof ADMIN_SECTIONS)[number];

export const sectionId = (section: AdminSection) => `admin-${section}`;
