/**
 * Reading a status code back off a failed query.
 *
 * TanStack Query carries whatever the query function threw, so the convention
 * across this app is `throw new Error(String(response.status))` -- which makes
 * the status recoverable at the render site without a custom error class.
 *
 * **This exists because collapsing every failure into one branch misled
 * somebody.** Every organisation panel rendered "no access" -- or nothing at
 * all -- whether the API said 401 or 403, and the two mean opposite things:
 * 403 is "this is not yours", 401 is "you are signed out". An owner following
 * instructions to delete their own organisation found the control simply
 * absent, because their fifteen-minute access token had expired half an hour
 * earlier and the panel hid itself exactly as it hides from a non-owner.
 */

/** The HTTP status a failed query carried, or null if it did not carry one. */
export function statusOf(error: unknown): number | null {
  if (error instanceof ApiError) return error.status;
  if (!(error instanceof Error)) return null;
  const code = Number(error.message);
  return Number.isInteger(code) && code >= 100 && code <= 599 ? code : null;
}

/** Whether this failure means "you are signed out", not "this is not yours". */
export function isSignedOut(error: unknown): boolean {
  return statusOf(error) === 401;
}


/**
 * An API failure that kept what the server said.
 *
 * Thrown instead of `new Error("create failed")`, which is what the job editor
 * used to throw — so a vacancy whose title was two characters long produced
 * "Could not save. Check the details and try again." and nothing else. The
 * server had said exactly what was wrong ("String should have at least 3
 * characters") and the client threw it away, leaving somebody to guess which
 * of eleven fields it meant.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string | null,
    /** What the server said about each field it named, by the schema's own field name (BL-19.10). */
    readonly fields: Readonly<Record<string, string>> = {},
  ) {
    // The message is the detail when there is one, so anything that only logs
    // `error.message` still says something useful.
    super(detail ?? String(status));
    this.name = "ApiError";
  }
}

/** FastAPI's field names, as a person would read them. */
const FIELD_NAMES: Record<string, string> = {
  title: "Title",
  description: "Description",
  positions: "How many people",
  closes_at: "Closing date",
  salary_min_inr: "Minimum salary",
  salary_max_inr: "Maximum salary",
  experience_min_years: "Minimum experience",
  experience_max_years: "Maximum experience",
  nsqf_level_min: "NSQF level",
  name: "Name",
  contact_email: "Contact email",
  website: "Website",
  // The candidate's own profile. Without these the six-collection editor and
  // the details form rendered the raw column -- "full_name: String should have
  // at most 120 characters" -- which names a database, not a field on screen.
  full_name: "Full name",
  headline: "Headline",
  location_state: "State",
  location_district: "District or city",
  years_experience: "Years of experience",
  education_level: "Highest education",
  date_of_birth: "Date of birth",
  expected_salary_min_inr: "Expected minimum salary",
  expected_salary_max_inr: "Expected maximum salary",
  notice_period: "Notice period",
  preferred_employment_type: "Preferred employment type",
  skill_slug: "Standard",
  proficiency: "Confidence",
};

/**
 * What the server said, as one sentence.
 *
 * FastAPI answers in two shapes: `detail` is a string for a raised
 * `HTTPException` ("Unknown standards: welding-x"), and a list of field errors
 * for a 422 from a schema. Both are worth showing; neither was.
 */
export function readDetail(body: unknown): string | null {
  if (typeof body !== "object" || body === null) return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;

  const parts = detail.flatMap((item) => {
    if (typeof item !== "object" || item === null) return [];
    const { loc, msg } = item as { loc?: unknown; msg?: unknown };
    if (typeof msg !== "string") return [];
    // `loc` is ["body", "field"] or ["body", "skills", 0, "skill_slug"]; the
    // last string in it is the field a person would recognise.
    const field = Array.isArray(loc)
      ? [...loc].reverse().find((p): p is string => typeof p === "string" && p !== "body")
      : undefined;
    const label = field ? (FIELD_NAMES[field] ?? field) : null;
    return [label ? `${label}: ${msg}` : msg];
  });
  return parts.length ? parts.join(". ") : null;
}

/**
 * What the server said about each field, by the schema's field name.
 *
 * A 422 from a schema is a list of `{loc, msg}`; `readDetail` folds it into one sentence for the
 * alert at the top of a form, and this keeps the parts so each can sit **next to the field it is
 * about** (BL-19.10). The key is the last string in `loc` (`["body", "title"]` is `title`, a nested
 * `["body", "skills", 0, "skill_slug"]` is `skill_slug`); a field named twice keeps its first message,
 * and the server's words are kept exactly as it wrote them. A plain-string `detail` names no field.
 */
export function readFieldErrors(body: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  const detail = typeof body === "object" && body !== null ? (body as { detail?: unknown }).detail : null;
  if (!Array.isArray(detail)) return out;
  for (const item of detail) {
    if (typeof item !== "object" || item === null) continue;
    const { loc, msg } = item as { loc?: unknown; msg?: unknown };
    if (typeof msg !== "string" || !Array.isArray(loc)) continue;
    const field = [...loc].reverse().find((p): p is string => typeof p === "string" && p !== "body");
    if (field && !(field in out)) out[field] = msg;
  }
  return out;
}

/** An `ApiError` for a failed response body: the status, the one-sentence detail and the per-field parts. */
export function apiErrorFrom(status: number, body: unknown): ApiError {
  return new ApiError(status, readDetail(body), readFieldErrors(body));
}

/** What the server said about one field of a failed save, if it said anything. */
export function fieldErrorOf(error: unknown, field: string): string | undefined {
  return error instanceof ApiError ? error.fields[field] : undefined;
}

/** Everything the server said by field about a failed save, for `FormErrors`; nothing for any other failure. */
export function fieldsOf(error: unknown): Readonly<Record<string, string>> | undefined {
  return error instanceof ApiError ? error.fields : undefined;
}

/** The server's explanation for a failed query or mutation, if it kept one. */
export function detailOf(error: unknown): string | null {
  return error instanceof ApiError ? error.detail : null;
}

/** Seconds the server asked the caller to wait before trying again (`Retry-After`), or 0. */
export function retryAfterSeconds(response: Response): number {
  const seconds = Number(response.headers.get("retry-after"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : 0;
}

/** A failed request that remembers how long it was told to wait. */
export type WaitError = Error & { retryAfter?: number };

export function failedWith(response: Response): WaitError {
  return Object.assign(new Error(String(response.status)), {
    retryAfter: retryAfterSeconds(response),
  });
}
