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

/** The server's explanation for a failed query or mutation, if it kept one. */
export function detailOf(error: unknown): string | null {
  return error instanceof ApiError ? error.detail : null;
}
