/**
 * The few profile fields the phone edits, and the rules that turn what was typed into the request.
 * Ported from the web's `AboutSection`, with the same limits **mirrored on the input that can break
 * them** (the web's `constraints.test.ts` rule: a constraint the form does not know about is one the
 * person finds out the hard way).
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";

export type ProfileUpdate = components["schemas"]["CandidateProfileUpdateFull"];
export type EducationLevel = NonNullable<ProfileUpdate["education_level"]>;

/**
 * Every education level the server accepts, **checked by the compiler**: a record keyed by the
 * schema's own union fails to compile when the server adds or renames one, rather than leaving a
 * restated list that quietly omits it.
 */
const LEVELS: Record<EducationLevel, true> = {
  none: true,
  primary: true,
  secondary: true,
  higher_secondary: true,
  iti: true,
  diploma: true,
  graduate: true,
  postgraduate: true,
};
export const EDUCATION_LEVELS = Object.keys(LEVELS) as EducationLevel[];

/** The server's limits (`CandidateProfileUpdateFull`), repeated on the inputs. */
export const LIMITS = { fullName: 120, headline: 160, place: 80, yearsMax: 60 } as const;

export type BasicsForm = {
  fullName: string;
  headline: string;
  state: string;
  district: string;
  years: string;
  education: EducationLevel | null;
};

/** What the form starts from: the profile as it was loaded. */
export function basicsFrom(profile: {
  full_name?: string | null;
  headline?: string | null;
  location_state?: string | null;
  location_district?: string | null;
  years_experience?: number | null;
  education_level?: string | null;
}): BasicsForm {
  const level = EDUCATION_LEVELS.find((l) => l === profile.education_level) ?? null;
  return {
    fullName: profile.full_name ?? "",
    headline: profile.headline ?? "",
    state: profile.location_state ?? "",
    district: profile.location_district ?? "",
    years: profile.years_experience == null ? "" : String(profile.years_experience),
    education: level,
  };
}

/** Whole years, 0 to the server's limit; blank means "not said" (`null`); anything else is `undefined`. */
export function yearsFrom(text: string): number | null | undefined {
  const trimmed = text.trim();
  if (trimmed === "") return null;
  if (!/^\d{1,2}$/.test(trimmed)) return undefined;
  const years = Number(trimmed);
  return years <= LIMITS.yearsMax ? years : undefined;
}

const orNull = (text: string, max: number) => text.trim().slice(0, max) || null;

/**
 * The request, or `null` when the years are not a number the server would take (the screen says so
 * before a request is made). A blank field is sent as `null`: the person cleared it.
 */
export function profileBody(form: BasicsForm): ProfileUpdate | null {
  const years = yearsFrom(form.years);
  if (years === undefined) return null;
  return {
    full_name: orNull(form.fullName, LIMITS.fullName),
    headline: orNull(form.headline, LIMITS.headline),
    location_state: orNull(form.state, LIMITS.place),
    location_district: orNull(form.district, LIMITS.place),
    years_experience: years,
    education_level: form.education,
  };
}
