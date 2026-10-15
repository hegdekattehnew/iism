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

// ------------------------------------------------------------- what they are looking for

export type NoticePeriod = NonNullable<ProfileUpdate["notice_period"]>;
export type EmploymentType = NonNullable<ProfileUpdate["preferred_employment_type"]>;

const NOTICES: Record<NoticePeriod, true> = { immediate: true, within_15_days: true, within_30_days: true, over_30_days: true };
export const NOTICE_PERIODS = Object.keys(NOTICES) as NoticePeriod[];
const EMPLOYMENT: Record<EmploymentType, true> = { full_time: true, part_time: true, contract: true, apprenticeship: true, gig: true };
export const EMPLOYMENT_TYPES = Object.keys(EMPLOYMENT) as EmploymentType[];

/** The most a salary field takes: nine digits is more rupees than anybody earns and fits an `int`. */
export const SALARY_DIGITS = 9;

export type PreferencesForm = {
  salaryMin: string;
  salaryMax: string;
  notice: NoticePeriod | null;
  employment: EmploymentType | null;
  relocate: boolean;
  alerts: boolean;
};

export function preferencesFrom(profile: {
  expected_salary_min_inr?: number | null;
  expected_salary_max_inr?: number | null;
  notice_period?: string | null;
  preferred_employment_type?: string | null;
  willing_to_relocate?: boolean | null;
  job_alerts_enabled?: boolean | null;
}): PreferencesForm {
  return {
    salaryMin: profile.expected_salary_min_inr == null ? "" : String(profile.expected_salary_min_inr),
    salaryMax: profile.expected_salary_max_inr == null ? "" : String(profile.expected_salary_max_inr),
    notice: NOTICE_PERIODS.find((n) => n === profile.notice_period) ?? null,
    employment: EMPLOYMENT_TYPES.find((e) => e === profile.preferred_employment_type) ?? null,
    relocate: profile.willing_to_relocate === true,
    // The server's default is on; a profile that says nothing keeps the opt-in it has.
    alerts: profile.job_alerts_enabled !== false,
  };
}

/** Whole rupees: blank is `null` (not said), a number is that many, anything else is `undefined`. */
export function rupees(text: string): number | null | undefined {
  const trimmed = text.replace(/[\s,]/g, "");
  if (trimmed === "") return null;
  return new RegExp(`^\\d{1,${SALARY_DIGITS}}$`).test(trimmed) ? Number(trimmed) : undefined;
}

export type PreferencesProblem = "salaryMin" | "salaryMax" | "salaryOrder";

/**
 * The request, or what is wrong with the salary before a request is made (the server refuses a
 * maximum below the minimum, and a negative or fractional figure). The date of birth and the gender
 * the website also takes are **not** here, on purpose (ADR-078).
 */
export function preferencesBody(
  form: PreferencesForm,
): { ok: true; body: ProfileUpdate } | { ok: false; problem: PreferencesProblem } {
  const min = rupees(form.salaryMin);
  const max = rupees(form.salaryMax);
  if (min === undefined) return { ok: false, problem: "salaryMin" };
  if (max === undefined) return { ok: false, problem: "salaryMax" };
  if (min !== null && max !== null && max < min) return { ok: false, problem: "salaryOrder" };
  return {
    ok: true,
    body: {
      expected_salary_min_inr: min,
      expected_salary_max_inr: max,
      notice_period: form.notice,
      preferred_employment_type: form.employment,
      willing_to_relocate: form.relocate,
      job_alerts_enabled: form.alerts,
    },
  };
}
