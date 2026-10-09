import { randomUUID } from "node:crypto";

import type { APIRequestContext, Page } from "@playwright/test";

import { E2E } from "../../playwright.config";

/** The privacy notice a new account agrees to; `api/core/config.py` holds the same string. */
export const CONSENT_VERSION = "2026-09-11";

const ACCESS = "iism.access_token";
const REFRESH = "iism.refresh_token";

export type Tokens = { access_token: string; refresh_token: string };

/** A mailbox on the reserved fixtures domain, never a real address. */
export const uniqueEmail = (label = "e2e") => `${label}-${randomUUID().slice(0, 12)}@iism-fixtures.co.in`;

/** A valid-looking mobile number (starts 6-9), unique per call so tests never share a person. */
export function uniquePhone(): string {
  const n = Number.parseInt(randomUUID().replace(/-/g, "").slice(0, 8), 16) % 1_000_000_000;
  return `9${String(n).padStart(9, "0")}`;
}

const api = (path: string) => `${E2E.API}${path}`;

/** A job seeker, created through the API (set-up, not the journey under test). */
export async function seekerTokens(request: APIRequestContext, phone = uniquePhone()): Promise<Tokens> {
  const asked = await request.post(api("/auth/otp/request"), { data: { phone } });
  const { debug_code } = await asked.json();
  const verified = await request.post(api("/auth/otp/verify"), {
    data: { phone, code: debug_code, consent_version: CONSENT_VERSION },
  });
  return verified.json();
}

/** An organisation and its owner, created through the API. Returns the slug and the tokens. */
export async function organisation(
  request: APIRequestContext,
  tenantType: "employer" | "course_provider",
  name: string,
): Promise<{ slug: string; email: string; tokens: Tokens }> {
  const email = uniqueEmail(tenantType === "employer" ? "hiring" : "academy");
  const asked = await request.post(api("/auth/org/register"), {
    data: { email, organisation_name: name, tenant_type: tenantType, consent_version: CONSENT_VERSION },
  });
  const { debug_code } = await asked.json();
  const verified = await request.post(api("/auth/email/otp/verify"), { data: { email, code: debug_code } });
  const tokens: Tokens = await verified.json();
  const me = await request.get(api("/auth/me"), { headers: { authorization: `Bearer ${tokens.access_token}` } });
  const memberships = (await me.json()).memberships as { tenant: { slug: string; tenant_type: string } }[];
  const slug = memberships.find((m) => m.tenant.tenant_type === tenantType)!.tenant.slug;
  return { slug, email, tokens };
}

/** Be signed in from the first request, the way a returning visitor is. */
export async function signInAs(page: Page, tokens: Tokens): Promise<void> {
  await page.addInitScript(
    ([a, r, at, rt]) => {
      localStorage.setItem(a, at);
      localStorage.setItem(r, rt);
    },
    [ACCESS, REFRESH, tokens.access_token, tokens.refresh_token],
  );
}

const bearer = (t: Tokens) => ({ authorization: `Bearer ${t.access_token}` });

/** Declare a standard on a seeker's profile (the one thing that moves a match score). */
export async function addSkill(request: APIRequestContext, tokens: Tokens, skillSlug: string): Promise<void> {
  const res = await request.post(api("/me/profile/skills"), {
    headers: bearer(tokens),
    data: { skill_slug: skillSlug, proficiency: 4 },
  });
  if (!res.ok()) throw new Error(`addSkill ${skillSlug}: ${res.status()} ${await res.text()}`);
}

/** Apply to a vacancy as a seeker. */
export async function applyTo(request: APIRequestContext, tokens: Tokens, jobSlug: string): Promise<void> {
  const res = await request.post(api("/me/applications"), {
    headers: bearer(tokens),
    data: { job_slug: jobSlug },
  });
  if (!res.ok()) throw new Error(`apply ${jobSlug}: ${res.status()} ${await res.text()}`);
}

/** The slug the server gave a vacancy, found by its (unique) title among an organisation's own. */
export async function jobSlugByTitle(
  request: APIRequestContext,
  tokens: Tokens,
  orgSlug: string,
  title: string,
): Promise<string> {
  const res = await request.get(api(`/org/${orgSlug}/jobs`), { headers: bearer(tokens) });
  const jobs = (await res.json()) as { slug: string; title: string }[];
  const found = jobs.find((j) => j.title === title);
  if (!found) throw new Error(`no vacancy titled ${title} in ${orgSlug}`);
  return found.slug;
}

/** A short unique suffix, so two tests never share a title, an organisation or a person. */
export const suffix = () => randomUUID().slice(0, 8);

/** The standard the fixture names "Collect blood samples" (HC/N0001). */
export const COLLECT_BLOOD = "collect-blood-samples-hc-n0001";

/** The slug the server gave a course, found by its (unique) title among an organisation's own. */
export async function courseSlugByTitle(
  request: APIRequestContext,
  tokens: Tokens,
  orgSlug: string,
  title: string,
): Promise<string> {
  const res = await request.get(api(`/org/${orgSlug}/courses`), { headers: bearer(tokens) });
  const courses = (await res.json()) as { slug: string; title: string }[];
  const found = courses.find((c) => c.title === title);
  if (!found) throw new Error(`no course titled ${title} in ${orgSlug}`);
  return found.slug;
}

export const SKILL_STERILE_FIELD = "maintain-a-sterile-field-hc-n0002";

/** A published vacancy, created and published through the API as set-up for a journey. */
export async function publishedJob(
  request: APIRequestContext,
  org: { slug: string; tokens: Tokens },
  title: string,
  skills: { skill_slug: string; importance?: number; is_mandatory?: boolean }[],
): Promise<string> {
  const created = await request.post(api(`/org/${org.slug}/jobs`), {
    headers: bearer(org.tokens),
    data: { title, location_state: "Karnataka", location_district: "Bengaluru", skills },
  });
  if (!created.ok()) throw new Error(`create job: ${created.status()} ${await created.text()}`);
  const { slug } = await created.json();
  const published = await request.post(api(`/org/${org.slug}/jobs/${slug}/publish`), { headers: bearer(org.tokens) });
  if (!published.ok()) throw new Error(`publish job: ${published.status()} ${await published.text()}`);
  return slug;
}
