/**
 * The six repeating sections of a profile (work history, education, certificates, languages,
 * preferred roles, preferred places) as **one table**, so one editor serves all of them, as on the
 * website (`SectionEditor`, `useSectionDefs`). Adding a section is an entry here, not a screen.
 *
 * - **The limits are the server's, repeated on the form** (`marketplace/schemas.py`), and
 *   `tests/test_mobile_section_limits.py` compares every one against the API's own schema, so a
 *   changed limit fails a build and not a person on a phone (the web's `constraints.test.ts`).
 *   The field literals below are **one per line** because that test reads them.
 * - **The server's routes take an untyped body**, so there is no generated request type: the shapes
 *   come from the response types (`ExperienceOut`...), and an enumeration is a record keyed by the
 *   schema's own union, which stops compiling when the server adds a value.
 * - **A date is a month and a year**, typed into two small fields and sent as the first of the
 *   month. It needs no picker package (which would be native code nothing here can run). When an
 *   entry is edited and the month and year are not changed, **the date the entry already had is
 *   sent back**, so editing a job's description on the phone does not move a start date the website
 *   recorded as the 15th.
 * - **An edit sends the whole entry**, because the server treats an absent field as "clear it": the
 *   fields the phone does not show (`nsqf_level`) travel back as they came.
 *
 * No React Native import: this file is tested in Node.
 */

import type { components } from "../api/schema";
import { EDUCATION_LEVELS } from "./profile";

export type Collection =
  | "experiences"
  | "educations"
  | "certifications"
  | "languages"
  | "preferred_roles"
  | "preferred_locations";

export const COLLECTIONS: readonly Collection[] = [
  "experiences",
  "educations",
  "certifications",
  "languages",
  "preferred_roles",
  "preferred_locations",
];

export type Proficiency = components["schemas"]["LanguageOut"]["proficiency"];
const PROFICIENCIES: Record<Proficiency, true> = { basic: true, conversational: true, fluent: true, native: true };
export const LANGUAGE_PROFICIENCIES = Object.keys(PROFICIENCIES) as Proficiency[];

export const YEAR_MIN = 1950;
export const YEAR_MAX = 2100;

export type Field =
  | { kind: "text"; key: string; max: number; min?: number; required?: boolean; long?: boolean }
  | { kind: "year"; key: string }
  | { kind: "date"; key: string; required?: boolean; hiddenBy?: string }
  | { kind: "flag"; key: string; default: boolean; clears?: string }
  | { kind: "choice"; key: string; options: readonly string[]; required?: boolean; default?: string };

/** One field per line: `tests/test_mobile_section_limits.py` reads these literals. */
export const FIELDS: Record<Collection, readonly Field[]> = {
  experiences: [
    { kind: "text", key: "employer_name", max: 120, required: true },
    { kind: "text", key: "role_title", max: 120, required: true },
    { kind: "text", key: "location", max: 120 },
    { kind: "date", key: "started_on", required: true },
    { kind: "date", key: "ended_on", hiddenBy: "is_current" },
    { kind: "flag", key: "is_current", default: false, clears: "ended_on" },
    { kind: "text", key: "description", max: 1000, long: true },
  ],
  educations: [
    { kind: "text", key: "qualification", max: 160, required: true },
    { kind: "text", key: "institution", max: 160 },
    { kind: "text", key: "specialisation", max: 120 },
    { kind: "choice", key: "education_level", options: EDUCATION_LEVELS },
    { kind: "year", key: "year_completed" },
    { kind: "flag", key: "is_pursuing", default: false },
  ],
  certifications: [
    { kind: "text", key: "name", max: 160, required: true },
    { kind: "text", key: "issuing_body", max: 160 },
    { kind: "text", key: "credential_id", max: 80 },
    { kind: "date", key: "issued_on" },
    { kind: "date", key: "expires_on" },
  ],
  languages: [
    { kind: "text", key: "language", max: 40, min: 2, required: true },
    { kind: "choice", key: "proficiency", options: LANGUAGE_PROFICIENCIES, required: true, default: "conversational" },
    { kind: "flag", key: "can_read", default: true },
    { kind: "flag", key: "can_write", default: true },
  ],
  preferred_roles: [{ kind: "text", key: "title", max: 120, required: true }],
  preferred_locations: [
    { kind: "text", key: "state", max: 80, required: true },
    { kind: "text", key: "district", max: 80 },
  ],
};

/** What the phone does not show but must send back unchanged on an edit, or the server clears it. */
const CARRIED: Partial<Record<Collection, readonly string[]>> = {
  certifications: ["nsqf_level"],
};

/** Which message in the `sectionProblem` namespace says what is wrong. */
export type ProblemCode = "required" | "short" | "long" | "year" | "date" | "order";
export type Problem = { field: string; code: ProblemCode };

export type FormValue = string | boolean;
export type Form = Record<string, FormValue>;
export type Entry = { id: string } & Record<string, unknown>;

/** The state of a date field is three form keys; the helpers keep them in one place. */
export const monthKey = (key: string) => `${key}:month`;
export const yearKey = (key: string) => `${key}:year`;
const originalKey = (key: string) => `${key}:original`;
const carriedKey = (key: string) => `~${key}`;

export function blankForm(collection: Collection): Form {
  const form: Form = {};
  for (const field of FIELDS[collection]) {
    switch (field.kind) {
      case "text":
      case "year":
        form[field.key] = "";
        break;
      case "date":
        form[monthKey(field.key)] = "";
        form[yearKey(field.key)] = "";
        form[originalKey(field.key)] = "";
        break;
      case "flag":
        form[field.key] = field.default;
        break;
      case "choice":
        form[field.key] = field.default ?? "";
        break;
    }
  }
  return form;
}

const ISO = /^(\d{4})-(\d{2})-(\d{2})/;

/** The form an existing entry is edited in. */
export function formFromEntry(collection: Collection, entry: Entry): Form {
  const form = blankForm(collection);
  for (const field of FIELDS[collection]) {
    const value = entry[field.key];
    switch (field.kind) {
      case "text":
        form[field.key] = typeof value === "string" ? value : "";
        break;
      case "year":
        form[field.key] = typeof value === "number" ? String(value) : "";
        break;
      case "date": {
        const match = typeof value === "string" ? ISO.exec(value) : null;
        if (match) {
          form[monthKey(field.key)] = String(Number(match[2]));
          form[yearKey(field.key)] = match[1];
          form[originalKey(field.key)] = value as string;
        }
        break;
      }
      case "flag":
        form[field.key] = typeof value === "boolean" ? value : field.default;
        break;
      case "choice":
        form[field.key] = typeof value === "string" && field.options.includes(value) ? value : (field.default ?? "");
        break;
    }
  }
  for (const key of CARRIED[collection] ?? []) {
    const value = entry[key];
    form[carriedKey(key)] = value == null ? "" : String(value);
  }
  return form;
}

const WHOLE = /^\d{1,4}$/;

/** A whole number in `[low, high]`, or `undefined`. */
function whole(text: string, low: number, high: number): number | undefined {
  const trimmed = text.trim();
  if (!WHOLE.test(trimmed)) return undefined;
  const n = Number(trimmed);
  return n >= low && n <= high ? n : undefined;
}

const two = (n: number) => String(n).padStart(2, "0");

/**
 * A date field: `null` when both parts are blank, `undefined` when it is not a month and a year,
 * else `YYYY-MM-01`, **or the date the entry already had** when the month and year are unchanged.
 */
function dateFrom(form: Form, key: string): string | null | undefined {
  const monthText = String(form[monthKey(key)] ?? "");
  const yearText = String(form[yearKey(key)] ?? "");
  if (monthText.trim() === "" && yearText.trim() === "") return null;
  const month = whole(monthText, 1, 12);
  const year = whole(yearText, YEAR_MIN, YEAR_MAX);
  if (month === undefined || year === undefined) return undefined;
  const original = ISO.exec(String(form[originalKey(key)] ?? ""));
  if (original && Number(original[1]) === year && Number(original[2]) === month) return String(form[originalKey(key)]);
  return `${year}-${two(month)}-01`;
}

export type Built = { ok: true; body: Record<string, unknown> } | { ok: false; problems: Problem[] };

/**
 * The request for a form, or every problem the person can fix before a request is made. The
 * server's rules are applied in the server's terms (an end before a start, a certificate that
 * expires before it was issued) so the sentence appears next to the field, not as a 422 afterwards.
 */
export function bodyFromForm(collection: Collection, form: Form): Built {
  const problems: Problem[] = [];
  const body: Record<string, unknown> = {};

  for (const field of FIELDS[collection]) {
    switch (field.kind) {
      case "text": {
        const text = String(form[field.key] ?? "").trim();
        if (text === "") {
          if (field.required) problems.push({ field: field.key, code: "required" });
          body[field.key] = field.required ? text : null;
        } else {
          if (field.min && text.length < field.min) problems.push({ field: field.key, code: "short" });
          if (text.length > field.max) problems.push({ field: field.key, code: "long" });
          body[field.key] = text;
        }
        break;
      }
      case "year": {
        const text = String(form[field.key] ?? "").trim();
        if (text === "") body[field.key] = null;
        else {
          const year = whole(text, YEAR_MIN, YEAR_MAX);
          if (year === undefined) problems.push({ field: field.key, code: "year" });
          body[field.key] = year ?? null;
        }
        break;
      }
      case "date": {
        const hidden = field.hiddenBy ? form[field.hiddenBy] === true : false;
        const value = hidden ? null : dateFrom(form, field.key);
        if (value === undefined) problems.push({ field: field.key, code: "date" });
        else if (value === null && field.required) problems.push({ field: field.key, code: "required" });
        body[field.key] = value ?? null;
        break;
      }
      case "flag":
        body[field.key] = form[field.key] === true;
        break;
      case "choice": {
        const value = String(form[field.key] ?? "");
        if (value === "" && field.required) problems.push({ field: field.key, code: "required" });
        body[field.key] = value === "" ? null : value;
        break;
      }
    }
  }

  // Rules that span fields, in the server's terms.
  if (collection === "experiences") {
    const start = body.started_on;
    const end = body.ended_on;
    if (typeof start === "string" && typeof end === "string" && end < start) {
      problems.push({ field: "ended_on", code: "order" });
    }
  }
  if (collection === "certifications") {
    const issued = body.issued_on;
    const expires = body.expires_on;
    if (typeof issued === "string" && typeof expires === "string" && expires < issued) {
      problems.push({ field: "expires_on", code: "order" });
    }
  }

  for (const key of CARRIED[collection] ?? []) {
    const raw = String(form[carriedKey(key)] ?? "");
    body[key] = raw === "" ? null : Number(raw);
  }

  return problems.length > 0 ? { ok: false, problems } : { ok: true, body };
}

/** The first problem for a field, if any, for the screen to show beside it. */
export function problemFor(problems: readonly Problem[], field: string): ProblemCode | null {
  return problems.find((p) => p.field === field)?.code ?? null;
}

/** Whether a field is shown at all (an end date is hidden for a job the person still holds). */
export function isVisible(field: Field, form: Form): boolean {
  return field.kind === "date" && field.hiddenBy ? form[field.hiddenBy] !== true : true;
}

/** Setting a flag may clear another field (`is_current` clears the end date), as the server does. */
export function setFlag(collection: Collection, form: Form, key: string, value: boolean): Form {
  const next: Form = { ...form, [key]: value };
  const field = FIELDS[collection].find((f) => f.key === key);
  if (field?.kind === "flag" && field.clears && value) {
    next[monthKey(field.clears)] = "";
    next[yearKey(field.clears)] = "";
    next[originalKey(field.clears)] = "";
  }
  return next;
}

/** A line for the list of entries: a title and the facts under it, ready for the screen to show. */
export function summaryOf(
  collection: Collection,
  entry: Entry,
  monthName: (month: number) => string,
): { title: string; lines: string[] } {
  const str = (key: string) => (typeof entry[key] === "string" ? (entry[key] as string) : "");
  const when = (key: string) => {
    const m = typeof entry[key] === "string" ? ISO.exec(entry[key] as string) : null;
    return m ? `${monthName(Number(m[2]) - 1)} ${m[1]}` : "";
  };
  switch (collection) {
    case "experiences":
      return { title: str("role_title"), lines: [str("employer_name"), [when("started_on"), entry.is_current ? "" : when("ended_on")].filter(Boolean).join(" - ")].filter(Boolean) };
    case "educations":
      return {
        title: str("qualification"),
        lines: [str("institution"), typeof entry.year_completed === "number" ? String(entry.year_completed) : ""].filter(Boolean),
      };
    case "certifications":
      return { title: str("name"), lines: [str("issuing_body"), when("issued_on")].filter(Boolean) };
    case "languages":
      return { title: str("language"), lines: [] };
    case "preferred_roles":
      return { title: str("title"), lines: [] };
    case "preferred_locations":
      return { title: [str("district"), str("state")].filter(Boolean).join(", "), lines: [] };
  }
}

/** Whether a path segment names a section (a typo or a hostile link must reach nothing). */
export function isCollection(value: unknown): value is Collection {
  return typeof value === "string" && (COLLECTIONS as readonly string[]).includes(value);
}

/**
 * Which message in the web's `profilePage.fields` names each field, so the phone says what the
 * website says. A test holds this to the real catalogues: a field with no label would render its
 * own key.
 */
export const FIELD_LABEL: Record<string, string> = {
  employer_name: "employer",
  role_title: "roleTitle",
  location: "location",
  started_on: "startedOn",
  ended_on: "endedOn",
  is_current: "current",
  description: "description",
  qualification: "qualification",
  institution: "institution",
  specialisation: "specialisation",
  year_completed: "yearCompleted",
  is_pursuing: "pursuing",
  name: "certName",
  issuing_body: "issuingBody",
  credential_id: "credentialId",
  issued_on: "issuedOn",
  expires_on: "expiresOn",
  language: "language",
  proficiency: "proficiency",
  can_read: "canRead",
  can_write: "canWrite",
  title: "roleTitleWanted",
  state: "state",
  district: "district",
};

/** The catalogue key (under `profilePage`) for an option of a choice field. */
export function optionKey(fieldKey: string, option: string): string {
  return fieldKey === "education_level" ? `educationLevel.${option}` : `langProficiency.${option}`;
}
