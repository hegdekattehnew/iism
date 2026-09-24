# Project context — read this first

Working notes for Claude Code. Purpose: recover full context on a new session without
re-reading the codebase or the conversation history. Update it at the end of any session
that changes the shape of the project.

**Last updated:** 2026-09-22 · **Sprints 1–24 built, merged to `main` via PR #1, CI green.**
Sprint 23 made a profile buildable by someone who cannot name a National Occupational Standard;
Sprint 24 closed the course loop for training providers. **Sprint 25 is agreed: teammate
invitations and the sole-owner trap** (§11). Deployment is deferred by the owner, deliberately.

> Every count in this file is dated. An undated number in a document that survives fifteen
> sprints is a number nobody can trust and nobody can check — the header above claimed
> "Sprints 1–5" through nine further sprints, which is how §10 came to assert the branch was
> pushed while four sprints sat on one laptop.

---

## 0. Status at a glance

*Everything here is checkable in under two minutes. Check it rather than trusting it — this file
has been wrong before, and §10 explains how.*

| | |
|---|---|
| **Branch** | `v2/foundations`, merged into `main` (PR #1, merge commit `7b6337a`) |
| **Last sprint** | 32 — every route handler delegates (17 violations moved, guarded) |
| **Next sprint** | 33 — the monetisation ADR (now 043) + payment adapter port |
| **Tests** | 680 backend (`make check`), 259 web (`cd web && npm test`) |
| **Migrations** | head `0028`; 42 ADRs |
| **Golden set** | `make evaluate` must print **all 34 golden pairs, 7 orderings and 16 course expectations hold** |
| **Deployment** | deferred by the owner; nothing is deployed anywhere |

**To get running** (Docker must be up; ports are non-default — 5433 / 6380 / 27018):

```
make up && make migrate && make import-nsqf && make seed    # first time, ~2 minutes
make api        # :8000   — reloads on change
make worker     # does NOT reload: restart it after any api/ change
make web        # :3000
```

**Demo logins** (all seeded, `OTP_EXPOSE_IN_RESPONSE=true` returns the code in the response):
`hiring@apollo-care.example` (employer, 5 applicants, **and a three-person team**),
`admin@skillbridge-institute.example` (provider, interested learners), `+919000000001`
(candidate with matches and a gap). Never sign in as the owner's real number, `+919880663641`.
Apollo Care is the only seeded organisation with more than one member — a second owner, an admin
and one pending invitation — so `/employer/apollo-care-hospitals/team` is where Sprint 25 demos.

**Sessions last 15 minutes and now refresh silently** — before 2026-09-23 they did not, because
the refresh guard matched `/auth/me` by substring. If a signed-in screen ever looks like it has
revoked your rights, check `/auth/refresh` is being called before believing it.

**The three things most likely to waste an hour**, all in §8: the worker not reloading, a stale
API process serving old code, and `make check | grep` reporting grep's exit status rather than
the suite's.

---

## 1. What this is

**IISM — Intelligent Integrated Skill Marketplace.** A marketplace connecting candidates,
vocational courses and vocational jobs, where all three are decomposed into NSQF-aligned
skills so the system can compute what a person is missing for the work they want, and which
training closes that gap.

The core loop is the product: **candidate → target job → skill gap → courses that close it → job.**
The listings are commodity; the skill graph and the scoring over it are the defensible part.

India-first, multi-sector, Hindi + English at launch, free in v1.

## 2. Where the real documentation lives

| Document | What it holds |
|---|---|
| `docs/adr/architecture-decisions.md` | **42 ADRs — the source of truth for every design decision.** Read before any structural change. |
| `docs/IISM-Product-Definition.docx` | 20-page product definition: problem, actors, intelligence layer, scope, risks, decision appendix. Written for the founding team, deliberately candid. **Read the next row with it.** |
| `docs/scope-reconciliation.md` | **Where the product definition and the tree disagree** (2026-09-24). Seven divergences, each naming the file that proves it — semantic similarity, weights-in-configuration, dismissal instrumentation, course↔role alignment, five of eight actor types, the provider's market signal, `SkillRelation`. The `.docx` is deliberately not amended; this sits beside it. |
| `CLAUDE.md` | Working conventions, repo layout, current state. Auto-loaded each session. |
| `README.md` | Setup and run instructions. |
| `~/.claude/plans/i-want-to-create-lively-phoenix.md` | **The most recent sprint plan** (overwritten each sprint — Sprints 30–31's is the latest). Lives outside the repo. |
| `docs/nsqf-source-data-findings.md` | **Everything measured about the NSQF corpus** — field-naming traps, level distributions, content volumes, deduplication rates, translation costs, data-quality issues. Read before touching the importer. |
| This file | Session-to-session continuity, environment quirks, hard-won gotchas. |

ADR-001–023 came from a March 2026 spreadsheet. **ADR-024–035 were written in this project
(Sept 2026)** and cover: multi-sector scope, monetization deferral, supply acquisition, ARQ over
Celery, AWS topology, Next.js client, in-house identity, AI provider abstraction, dual credentials,
language scope, the NSQF source of record (034), and selective ingestion — why the PII-bearing
`ssc` collection is deliberately not imported (035). Three repairs were also made: ADR-014's malformed status, ADR-015 marked superseded,
and **ADR-023's `Final decision` field was empty** — the most compliance-sensitive decision in the
document was formally unresolved. It is now filled in.

## 3. Decisions that were genuinely contested

Do not silently re-litigate these; they were deliberate and are recorded in ADRs.

- **Multi-sector, not single-sector.** Overrides ADR-015. Taxonomy is sector-agnostic, so
  constraining it saved little. Trade: go-to-market focus. If validation stalls, narrow the GTM
  while keeping the taxonomy general.
- **Free v1, no revenue model.** ADR-025 *defers* the question rather than answering it.
  Measurement replaces revenue as the signal — precision@5 on a golden set, click-through,
  enrollment conversion. None of that instrumentation exists yet.
- **Deterministic decides; the LLM only explains.** ADR-005/018. A product principle, not a
  technical footnote. No LLM ever produces a match score.
- **Embeddings pinned at 384 dimensions.** ADR-031. pgvector's HNSW needs a fixed dimension;
  384 is the only size natively shared by MiniLM and reachable by OpenAI/Gemini Matryoshka
  reduction. Any other number silently breaks the multi-provider adapter.
- **Phone + OTP for candidates, email for organisations.** ADR-032. Makes SMS a login-availability
  concern, not a notification nicety.
- **ARQ, not Celery.** ADR-027 amends ADR-006. The app is async end to end.

Decided while planning Sprints 3 and 4 (not yet ADRs — write them if they survive contact):

- **Inventory before authentication.** An earlier note said auth was Sprint 3; that was revised
  because there is still nothing worth protecting. A login form proves nothing about whether the
  product works. Jobs and courses land first, then a profile worth protecting.
- **Jobs and courses anchor to skills only.** No Qualification Pack or Occupation hierarchy yet —
  matching works from skill overlap alone, and QP anchoring becomes a nullable column later rather
  than a restructure. Keeps NSQF sourcing off the critical path.
- **`Tenant` arrives in Sprint 3, before auth.** Jobs and courses must belong to something; a
  throwaway `organisation_name` string would force an FK migration later. One small table now,
  models only, `User` and `Membership` layered on in Sprint 4.

## 4. Current state

**Sprint 24 (somebody is interested) — complete, 2026-09-21.** Deployment deferred; the question was
which functionality is worth most, and a scan across all three actors found one that got nothing at
all. A learner shown "the courses that close your gap" could not act on one — no enrol, no enquiry,
not even the provider's website that the API already returned — and providers published into
silence. Now a learner registers interest (sharing name, contact, district and a note with that
provider, revoked on withdrawal), the provider gets an inbox, a roll-up of which courses people
want, and the first notification they have ever received. `api/modules/interests/` is a sibling of
`applications/`; the provider payload has **no score**, because a course publishes what it teaches
and inventing a scorer for it is what ADR-037 forbids. Migration 0025. Two defects fixed alongside:
`course_recommended` was recorded against the job with a bare count (ADR-025's click-through has
been uncomputable since Sprint 10 — now one row per course, carrying `from_job`), and
`_delete_tenant` never deleted applications explicitly. 527 backend and 89 web tests. **Still open:**
teammate invitations and the sole-owner trap (agreed as the next sprint — a sole owner deleting
their account still destroys the organisation and every application to it); a learner-facing notice
when a provider marks "contacted"; vacancy lifecycle; `is_verified` still has no writer.

**Sprint 23 (say what you do, and we'll name the standards) — complete, 2026-09-18.** Asked as "should
a CV populate the profile?"; answered by finding that only `candidate_skills` changes a score, and
that the only way to add one was naming a National Occupational Standard nobody can name. A CV would
have filled experiences and education, which no scorer reads. Now a candidate types their job ("ward
boy", "ड्राइवर"), the qualification behind it names its standards, and they tick what they can do —
one request, written `self_declared`, nothing pre-ticked. A curated alias map bridges colloquial
titles the corpus does not use (**awaiting labour-market review**). Profile location now resolves on
save; experience enters the score by a split of the level weight that is neutral for anyone who
fits (golden set bit-identical); locality orders equal scores and never changes one. Migration 0024
(trigram index on `job_role`, two analytics names); `migrations/env.py` repaired — it would have
dropped the live skill trigram index. 501 backend and 66 web tests; verified in the browser as a
brand-new account in English and Hindi. **CV upload deferred** until the residual gap is visible.
**Follow-up the same day:** the homepage search now lands on `/search` — open jobs, then roles, then standards — instead of the standards browser, and every standard card shows its code, level and the qualification it belongs to, flagging same-named results. **Found, not fixed** (task raised): three district names exist in two states and resolve
arbitrarily, and every NSQF import rewrites every profile's `updated_at`.

**Sprint 22.5 (demo readiness) — complete, 2026-09-17.** No new product surface: the readiness
check before demoing found that the whole of Sprint 21 could not be shown cold, because all six
seeded applications sat in organisations **nobody could sign in to**. All ten seeded organisations
now have owner accounts on the reserved `.example` domain, provisioned the way the product does it;
sixteen applications spread across all five employers in mixed states; fifty courses instead of
twenty, chosen so that **every mandatory standard across the twenty vacancies is taught by at least
one course** (two were taught by none, and their gap panels were empty). Thirteen leftover fixture
organisations were removed by `scripts/clean_fixtures.py` — explicit slugs, `--dry-run` by default,
**no account deleted**. Malay is hidden from the switcher and still routed. The browser walkthrough
found one real defect: the employer's inbox rendered `employerConsole.matchScore` as text, because
that key only ever existed in `matchesPage`; the test harness now fails on any missing key and the
inbox has its own test file. Verified: `make seed` twice identical, the coverage query, `make
evaluate` unmoved, 440 backend and 56 web tests, and a cold-start walkthrough in both languages.
**Still open:** publishing a listing in two languages, notification preferences, a real email
provider, deployment, and per-country taxonomy (needs its own ADR first).

**Sprint 22 (many languages, and something arrives) — complete, 2026-09-17.** Two problems, both
visible only once someone looked. The language switcher was two tabs, and under it the product was
bilingual by construction: 18 `_en`/`_hi` column pairs, 16 API fields, 37 client ternaries. Now the
base column holds the row's own text and every other language is a row in `content_translations`
(ADR-041, migrations 0021–0022) — 187 rows moved, adding a language is INSERTs. The API negotiates
the language and the client renders what it is given; a Malay skeleton ships as a third locale so
the machinery is exercised beyond two. And the loop Sprint 21 closed no longer closes silently: an
outbox (0023) queues an email to the employer when somebody applies and an in-app notice to the
candidate when their status changes, drained by an ARQ cron. **Migration 0022 was rehearsed against
a full copy of the development database** — three GENERATED search vectors had to be dropped and
rebuilt. **Still open:** publishing a listing in two languages (the employer editors lost their
Hindi inputs), notification preferences, and translating the corpus itself.

**Sprint 21 (the loop closes) — complete, 2026-09-17.** The marketplace can finally produce an
outcome. A candidate applies to a vacancy (sharing name and contact with that employer, for that
vacancy, recorded as consent), withdraws (which takes the contact back and keeps the row), and saves
vacancies privately. An employer sees who applied, ranked by the same scorer, with the contact
details to act on, and moves each one to shortlisted, not suitable or hired. Export and erasure
cover both new tables; a rolling 24-hour cap answers spraying. Migrations 0019 (applications,
saved_jobs) and 0020 (four analytics names). Seeded candidates gained work histories and six demo
applications, so a fresh machine shows a profile and an inbox with something in them. **Verified end
to end against the running API and in the browser in both locales.** Details in `CLAUDE.md`.
**Still open:** teammate invitations, membership removal and `is_verified` still have no writer;
deployment moved to Sprint 22.

**Sprint 20 (safe to deploy) — complete, 2026-09-11.** No new product surface; the NFR gaps that
need no outside account, closed before the first deployment. Consent recorded server-side at
signup (DPDP Act 2023), self-serve export and deletion at `/account`, privacy notice / terms /
grievance pages in both languages **marked draft pending legal review**, analytics purged after
12 months. Security headers on API and web (web CSP report-only), rate limiting on every class of
request, body-size cap, `/docs` local-only, DB pool and statement timeout. Encrypted backups outside
the tree, **MongoDB covered for the first time**, restore drill run and passed. `uv.lock` committed
and CI installing from it, dependency audits and Dependabot, a first-load JS budget, axe checks,
error pages that say "unavailable" instead of 404, and the employer overview's N+1 gone. Details in
`CLAUDE.md` → Current state. **Still open, needing the owner:** a named grievance officer
(`web/src/lib/legal.ts`), legal review of the three pages, and the pull request.

**Sprint 19 (every door opens onto all three) — complete, 2026-09-11.** The registration page at
`/signup/[type]` now switches between job seeker, employer and training provider in place, instead
of committing whoever arrived to the type in the URL. Links, not a toggle; the form is keyed so
switching gives a clean one. No backend change — registration already handled all three.

**Sprint 18 (one identity, honestly) — complete, 2026-09-11.** Prompted by three defects found by
hand: "profile" inside an organisation opened the candidate editor; re-registering an existing
number silently signed you in; there seemed to be no way to be only an organisation. All three
were one defect, and a scan found seven more — most seriously that `POST /auth/org/register` forked
a signed-in candidate into a second account, which Sprint 16's homepage chooser had made easy to
reach. Fixed and verified end to end in a browser; `web/` gained its first test runner. Details in
`CLAUDE.md` → Current state. **Still open:** nothing can remove a membership, so an account that
already has a personal tenant stays a job seeker; no organisation can add a second member; and
`is_verified` has no writer.

**Sprint 17 (logging you can run a customer on) — complete, 2026-09-10.** One structured JSON stream
on stdout for the API, the worker and stdlib loggers alike (ADR-040), a redaction filter in the
shared processor tail that masks phones, emails and OTPs so no logger can route around it (ADR-023),
and a request id, user id and tenant id on every line. The worker's heartbeat noise (~34,500
lines a day) was silenced by pinning `arq.worker` to WARNING. Details in `CLAUDE.md`.

**Sprint 16 (who is this for) — complete, 2026-09-10.** The homepage now says which three roles the
marketplace serves (a role chooser beside the hero), the job-seeker landing makes clear where you
are, and the header switcher names contexts instead of saying "Switch". Also found and fixed:
`BrowsePanels` and `Audiences` had sat unpadded on the homepage for four sprints after the `Card` /
`CardBody` rename, and `divide-y` emits no border width in this build. The hero's fold budget is
measured in Hindi, the binding case. Details in `CLAUDE.md` → Frontend conventions.

**Sprint 15 (consolidation) — complete, 2026-09-09.** No new product surface. The push, the
deletions, the shared-policy extraction, three new test files, and this document made true.

*Counted live on 2026-09-09.* Database **557 MB** (not the 485 MB written here for three sprints).
`skills` 21,355 · `skill_aliases` **298** (not 149 — the importer carried more than the seed) ·
`skill_concepts` 18,958 · `qp_entry_routes` 14,405 (the table is `qp_entry_routes`; this file
called it `entry_routes`) · `tenants` 49 · `users` 38 · `memberships` 40 · `jobs` 23 · `courses` 21
· `job_skills` 91 · `course_skills` 66 · `candidate_profiles` 34 · `candidate_skills` 90 ·
`analytics_events` 41. **39 ADRs**, 17 migrations.

The tenant count is lower than it was mid-sprint because verifying the journeys end to end left
throwaway organisations behind, and clearing them also removed **11 orphaned personal tenants**
from earlier sessions — rows with no membership at all, which no account could reach. Worth
knowing if a number here looks smaller than a memory of it: the seed is the floor, and everything
above it is journey debris.

**Scale, with the generated code separated out** — because quoting a gross figure to anyone
technical invites exactly one question, and it should be answered here first:

| | files | lines | |
|---|---|---|---|
| `api/` | 68 | 9,861 | authored |
| `scripts/` | 7 | 2,484 | authored |
| `tests/` | 18 | 4,170 | authored |
| `migrations/` | 18 | 1,714 | authored |
| `web/src/` excl. generated | 92 | 8,197 | authored |
| `web/src/lib/api-schema.d.ts` | 1 | 4,675 | **generated** — `make gen-api` |
| `web/src/messages/*.json` | 2 | 1,556 | authored (650 keys × 2 locales) |
| `backups/schema.sql` | 1 | ~2,127 | **generated** — `make db-schema` |
| `web/package-lock.json` | 1 | ~8,100 | **generated** — npm |

So roughly **26,400 lines of authored code**, of which 4,170 are tests. Anything that quotes a
number near 40,000 is counting a file a tool wrote.

**Five of the six rich-profile collections are empty.** Sprint 5 built experiences, educations,
certifications, languages, preferred roles and preferred locations; across all six the database
holds **one row** (an experience). The schema is real, the generic route and editor are real, and
`tests/test_profile_sections.py` exercises them — but nothing has ever put data through them at
volume, and no seeded candidate has a work history. That is a fact about the seed, not the code,
and it is the reason a demo of the profile wizard looks thinner than the schema behind it.

**What Sprint 15 found, which is more useful than what it deleted:**
- `record()` raised `TypeError` on an unknown event name, from above the `try/except` that exists
  to absorb exactly that, and its docstring says "Never raises". `log.warning(..., event=name)`
  collides with structlog's own first positional argument. `analytics/` had no test file; writing
  one found it in the first run. The same collision sat in the `except` branch.
- Three of eight publishing writes had no tenant-type guard while `CLAUDE.md` asserted all eight
  did. Fixed structurally, not by adding three call sites.
- Two profile columns were closed `Literal` unions on a response model with no CHECK behind them
  (migration 0017). Found by writing the test that asserts unions and constraints agree.
- The seed never resolved geography and relied on a backfill that runs **before** the rows it
  fixes exist. A clean `make import-nsqf && make seed` left every seeded job invisible to
  location-filtered matching.
- 37 dead message keys per locale, `orgAuth` entire. The audit produced two rounds of false
  positives first; **do not delete an i18n key on a grep alone** (§8).

**Sprint 1 (walking skeleton) — complete.** Every architectural layer exists and is connected,
with near-zero business logic.

**Sprint 2 (skill taxonomy) — complete.** `Skill` + `SkillAlias`, 52 bilingual skills, 149 aliases,
multi-script search, `/skills` browser and `/skills/[slug]` detail in both locales.

**Sprint 3 (marketplace) — complete.** `Tenant` (identity, models only), `Job` + `JobSkill`,
`Course` + `CourseSkill`. 8 tenants, 20 jobs, 20 courses, 96 job-skill and 76 course-skill links,
all bilingual. `/jobs` and `/courses` browsers with filters and detail pages; `/skills/[slug]`
shows jobs needing the skill and courses teaching it. 46 tests.

**Also built (unplanned addition):** the public homepage template — header with nav and CTAs, hero
with search, how-it-works, audience cards, browse panels, CTA band, footer. The Sprint 1 System
Status panel now lives at the *foot of the homepage* behind a "Development panel" badge.

**Sprint 4 (identity + profile) — complete.** `User` (nullable independently-unique phone/email),
`Membership`, personal tenants provisioned at first sign-in. Phone + OTP, hashed codes in Redis,
per-phone rate limiting, 5-guess cap, JWT access + rotating refresh. `NotificationProvider`
adapter with a console implementation. `CandidateProfile` + `CandidateSkill` carrying `source`.
`/signin` and `/profile` live; header reflects auth state. 78 tests.

**Sprint 5 (rich candidate profile) — complete.** Driven by real use: the first-login profile was
five fields. Added personal details, job preferences, and six repeating collections (experiences,
educations, certifications, languages, preferred roles, preferred locations). Guided wizard on
first visit, sectioned editor after, weighted completeness meter. 101 tests.

**Sprint 6 (NSQF master data) — built, then rolled back** on 2026-09-04. The audit that prompted
it is in [docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md).

**Sprint 14 (three ways in, one way back) — done** on 2026-09-08. Prompted by the observation that
the product looked job-seeker-first and would "restrict an identity who wants only to come to either
hiring people or provide training". Partly true, and the audit found worse.

- **An employer-only identity was already possible** — `/auth/org/register` creates a user with an
  employer tenant and no personal workspace. The problem was discoverability: every homepage route
  to an account went to the candidate phone form, and `/employers/signin` sat two clicks behind a
  marketing page.
- **A training provider could not register at all.** `OrgSignInForm` hardcoded
  `tenant_type: "employer" as const`. The API had accepted `course_provider` since Sprint 12; no UI
  could produce it.
- **And a provider account led nowhere.** No write path for `Course` existed anywhere in `api/`. A
  provider got an employer's heading, a nav reading "Vacancies", and a "New vacancy" button whose
  save returned 403 into a mutation with **no `onError`** — so the form sat there having silently
  done nothing. A `course_provider` tenant with a member and zero courses already existed in the
  database when this started.
- **`/org/{slug}/candidates` answered 200 to providers** with two empty arrays and
  `candidates_total`, which has no tenant filter. The only number on the screen was a global count
  of every candidate on the platform, presented as a pool they could reach.
- **Pushed back on one half of the request, and the reasoning held up.** The proposal was to fork
  *login* by user type as well as registration. ADR-032's rule is about the credential at
  registration; after Sprint 13 one identity holds both credentials, so at sign-in the credential no
  longer identifies anyone. Two doors would punish exactly the people who linked both. Registration
  is type-aware; sign-in detects an `@` and routes on what the account holds.
- **Course publishing is a sibling of job publishing, not a generalisation.** `CourseSkill` carries
  only `level_taught`, so duplicates collapse on the **highest level** where a job's collapse on the
  strongest signal. Resisting the urge to unify them is the point.
- **No migration.** Everything needed already existed in the schema — the first sprint in six that
  did not touch it.
- **A stale Turbopack cache cost ten minutes.** Every page 500'd with a `JSON.parse` error at a fixed
  byte offset while `npm run build` passed cleanly. `rm -rf web/.next` fixed it. Suspect the cache
  first when the build disagrees with the dev server.
- **Its second disguise (Sprint 16) is a hydration mismatch.** Fast Refresh updated the *client*
  bundle and left the *server* module graph behind, so one `<a>` was server-rendered with the old
  `href` and client-rendered with the new one — reported as "some attributes of the server rendered
  HTML didn't match the client properties", which reads like a bug in the component and is not one.
  **The tell is that the React diff shows two values you recognise as the before and after of your
  own edit.** Same fix: stop the dev server, `rm -rf web/.next`, restart. Do not add
  `suppressHydrationWarning` — it would hide the real ones.

**Sprint 13 (multi-tenancy you can see) — done** on 2026-09-07. Prompted by a single observation:
*"I was expecting an option on the frontend to change tenancy after login."* There wasn't one, and
auditing why turned up more than a missing control.

- **The Sprint 12 plan said "the header gains a switcher" and I built it inside `EmployerWorkspace`
  instead, without flagging the deviation.** That is the root of everything below. A switcher inside
  the page is invisible to anyone who has not already reached the page, and `/employer/{org}` had no
  inbound link from anywhere a signed-in person could be — its only entry was a one-shot
  `router.push` at the moment of email verification.
- **A candidate's personal tenant resolved as an organisation context — a real hole, mine.** Every
  candidate is `owner` of a personal tenant, `_context_for` filtered on membership and slug alone,
  and `owner` carries `JOB_CREATE`, `JOB_PUBLISH`, `CANDIDATE_SHORTLIST`. Confirmed against the
  running API: `GET /org/personal-…/candidates` returned **200**. It returns 404 now. The lesson is
  narrow and worth keeping: *a permission set answers "may this person act here", never "is this the
  right kind of place".*
- **The only visible "create an organisation" path created a second account.** It posts
  `/auth/org/register`, which mints a new `User` for an unknown address. So the one affordance a
  candidate could find produced exactly the outcome ADR-038 exists to prevent, while
  `POST /me/organisations` — which does the right thing — was called from nowhere in `web/src`.
  Endpoints without an interface are not features; they are tests that happen to pass.
- **Sign-out did not clear the TanStack cache.** The `QueryClient` outlives the session, so the
  previous person's profile, matches and memberships stayed in memory for whoever signed in next.
  On a shared phone that is the same problem the service worker's DENY list exists to stop.
- **Circular import when identity started importing `core.authorization`.** `authorization` imports
  identity's models, and importing a submodule runs the package `__init__`. Solved the way
  `get_current_user` already solves it: `TYPE_CHECKING` for annotations, a local import inside the
  function for runtime.
- **`TenantOut` is embedded in every public job and course payload.** Any column added to it is
  published. `contact_email` therefore lives on `OrganisationOut` only.
- Still true and still deliberate: `CandidateProfile` is 1:1 with `User`, not with a tenant. A
  person's skills are theirs; forking them per employer would fragment the history the matching
  engine scores against.

**Sprint 12 (one identity, many roles) — done** on 2026-09-07. Organisation identity, the
authorization primitive both ADR-012 and ADR-022 had described for eleven sprints without anyone
building it, and self-serve job publishing. ADR-038 and ADR-039. 233 tests. 557 message keys per
locale.

What a future session should not have to rediscover:
- **A person is not an actor type.** The multi-role case is the load-bearing design decision, and it
  is cheap now and expensive later: every org-scoped query depends on how the active tenant is
  resolved. It comes from the request path and is granted by the membership — never from the token,
  never from a request body.
- **404, not 403, for an organisation you are not a member of.** A 403 confirms it exists, and an
  employer could enumerate competitors by guessing slugs. Inside an organisation you *do* belong to,
  an insufficient role is a 403.
- **Registration had a readable enumeration oracle and it was caught by running the flow, not by
  reading it.** The first version sent a "you already have an account" note instead of a code, so
  the two responses differed by one field whenever `expose_otp` was on. It now sends a real sign-in
  code and creates no second organisation — indistinguishable, and friendlier.
- **`scripts/seed_candidates.py` was creating a personal tenant with no membership.** Invisible for
  four sprints because nothing read `Membership`. It now provisions through the real sign-in path,
  so seeded candidates are shaped like real ones.
- **`Job.status` defaults to `"published"` in the model.** Every create path must set `draft`
  explicitly. This is a footgun aimed squarely at the code this sprint added.
- **Geography resolved only inside the NSQF importer's backfill.** A job created through the API had
  a NULL `state_id` and was invisible to location-filtered matching while appearing normally at
  `/jobs` — the worst kind of bug, because nothing looks wrong. Resolution moved into
  `api/modules/geography/service.py` and happens on write.
- **`SkillOut` carried no `nos_code`**, so a picker could show three standards with identical names
  and no way to tell them apart. Verified in the browser: searching "infection control" returns
  three rows named the same, distinguishable only by `MSU/HSS/CRS0093-004` and friends.
- **A design-system `Button` defaulting to `type="submit"` is a footgun.** The picker's Add button
  saved a half-written vacancy instead of adding a standard. `Button` now defaults to
  `type="button"`; every form already declared its submit explicitly.
- **next-intl reads a dot as a namespace separator**, so `"employment.full_time"` as a flat key
  renders as the literal key string on screen. It must be a nested object.
- **The Sprint 11 mount guard was wrong** and I wrote it: `environment == "production"` mounted the
  unauthenticated console on staging, on CI, and anywhere `ENVIRONMENT` was unset. It is an
  allowlist now, and `/health` reports it — which the old comment falsely claimed it already did.
- **`email-validator` rejects the reserved `.test` TLD**, which is exactly the sort of thing a
  hand-written address regex waves through. Test fixtures use an ordinary domain.

**Sprint 11 (make it sellable) — done** on 2026-09-07. Six parts, in the plan's must-land order:
a component library, the landing page proving scale from live counts, the employer console, an
installable PWA, match visualisation, and real content on the three audience routes. Migration 0015
(the analytics event CHECK). ADR-037. 208 tests. 487 message keys in each locale.

What a future session should not have to rediscover:
- **The shadcn CLI was tried and reverted.** It adds a second dark-mode mechanism (a `.dark` class)
  beside the `prefers-color-scheme` one already in `globals.css`, 62 duplicate oklch tokens
  including `--background` / `--foreground` / `--border`, a Geist font override in `layout.tsx`, and
  installs `cn` and `shadcn` as runtime dependencies. Its components would have rendered light
  inside this app's dark theme. Radix primitives plus `cva` over the existing tokens, directly,
  cost about a day and owe nothing.
- **`buttonVariants` must not live in a `"use client"` module.** Exporting the cva from
  `button.tsx` broke prerendering of every server component styling a button:
  `Error: Attempted to call buttonVariants() from the server`. It lives in `button-variants.ts`.
- **`ui.tsx` and `ui/` both resolve for `@/components/ui`.** Having both is a silent collision; the
  file was deleted and its contents folded into `ui/layout.tsx` and `ui/button-link.tsx`, so no
  import in the codebase changed.
- **The employer console is the same `score_match`, arguments swapped** (ADR-037), and it refuses
  to mount in production. It is unauthenticated and reads the candidate pool, so the guard is code,
  not a comment: `mount_employer_console` returns `False`, and a test boots the app in both
  environments to prove the route is present in one and absent in the other.
- **No employer-facing payload identifies a candidate** — reference, headline, district, years and
  the gap only. A test asserts the absence of `full_name`, `phone`, `email` and `user_id`.
- **Adding an analytics event needs a hand-written migration.** Alembic does not diff CHECK bodies,
  so a new `EVENT_NAMES` entry is accepted by the model and rejected by the database — and
  `record()` swallows its own failures by design, so the only symptom is events that silently never
  appear. This is the third time a CHECK constraint has cost time in this project.
- **A label overstated the data and had to be corrected.** "Fully qualified" appeared beside "holds
  3 of 6 required standards", because the flag means *all mandatory held*. It now says exactly
  that. Worth naming: the failure was in the words, not the arithmetic, and only a screenshot
  caught it.
- **`qlmanage -t -s 512` honours an SVG's `width`/`height`, not its viewBox.** The 64px source
  rendered 64px in the corner of a 512 canvas. The icon sources are 512-sized SVGs; the maskable
  one has no rounded corners, because the launcher applies its own mask and a rounded source is
  cropped twice.
- **The service worker registers in production builds only.** In development it caches hashed
  chunks that hot reload then replaces. Demonstrate installability with `npm run build && npm start`.
- **The in-app browser pane refuses `serviceWorker.register`** — "an unknown error occurred when
  fetching the script", although the same page fetches `/sw.js` fine at 200 with
  `application/javascript`. Registration therefore has **not** been confirmed in a real browser;
  that check is still outstanding and needs Chrome or a phone.
- **Twenty seeded candidates now, not five.** The original five are unchanged and still first in
  the list, because the golden set is asserted against them.

**Sprint 10 (matching and the gap) — done** on 2026-09-06. The payoff, after three deferrals.
`/matches` ranks jobs for a signed-in candidate with the score broken down, names the gap standard
by standard, and lists the courses that close it plus how to become qualified. Migration 0014
(`analytics_events`). ADR-036. 195 tests, plus a golden set behind `make evaluate`.

Non-obvious things:
- **`scoring.py` is pure and must stay pure** — no I/O, no clock, no model. That is what makes a
  score defensible to an employer and measurable against the golden set.
- **`record()` commits.** `get_db_session` never commits, so the first wiring flushed three events
  per request into an empty table. Only call it from handlers with no other uncommitted work.
- **Zero matched standards scores zero.** Letting level and evidence through alone gave every job
  a small non-zero score for everyone — noise that ranking then had to see past.
- **A missing mandatory standard caps at 45**, not zero: a candidate one short of a strong match
  needs telling, not hiding.
- **Golden-set expectations are relative, never absolute.** "This candidate outranks that one"
  survives a weighting change; "scores 82" does not, and a suite failing on every improvement is
  one people stop running.
- **`openapi-fetch` resolves rather than throws on non-2xx.** A 401 arrived as `data: undefined`
  and rendered as "nothing matches" — telling a signed-out visitor they had no matches. Authenticated
  queries must check `error` explicitly.

**Sprint 9 (connect the graph) — done** on 2026-09-06. The national taxonomy is now the
operational vocabulary. 87 job links, 64 course links and 4 candidate skills all point at real
National Occupational Standards; the 52 curated skills are `source='legacy'`, hidden from search
and browse but still reachable by URL because profiles reference them. 149 aliases carried across,
so `khoon nikalna` resolves to `HSS/N0513`. `skill_concepts` holds 18,958 concepts over 21,303
rows. Migration 0013. 179 tests.

Two things worth knowing:
- **`scripts/legacy_skill_map.py` is hand-authored and is the only place the old vocabulary maps
  to the new.** It cannot be automated: full-text search gets `Blood sample collection` →
  `HSS/N0513` right and `Customer service` → a hair-and-beauty NOS wrong, and nothing in the data
  distinguishes the two cases.
- **52 curated slugs collapse to 38 standards**, because the curated vocabulary is finer-grained
  than NSQF. Seeding merges duplicate links on the strongest signal.

**Sprint 8 (complete NSQF migration) — done** on 2026-09-05, against the full master data after
four further collections arrived (`sectors`, `ssc`, `state`, `district`).

```
states 36 | districts 766 | sub_districts 7,100
awarding bodies 106 (43 SSC + 63 AB) | sectors 43 | sub_sectors 796 | occupations 1,808
skills 21,303 | qualification_packs 4,424 | qp_skills 27,278 | model_curricula 1,950
qp_entry_routes 14,405 | nco_codes 2,541 | qp_skills with weightage 25,522
performance elements 38,340 | criteria 238,370 | knowledge 185,559 | generic 151,840
```

Migrations 0011 (geography) and 0012 (structure, entry routes, content, pruning). `make
import-nsqf` runs in ~90s and is idempotent — verified by identical counts across consecutive
runs. New module `api/modules/geography/`; new file `api/modules/skills/content.py`.

Things a future session must not relearn the hard way:
- **The `ssc` collection is never imported.** Portal accounts with 4,027 emails, 4,042 mobiles and
  50 bank accounts. `sectors` supplies the same organisations, cleanly, with four times the reach.
- **The owning body is the code prefix.** 97% of qualifications, 99.8% of standards.
- **Sector-local ids.** Occupation `code` *and* `occupationID` are both scoped to a sector;
  keying on the id alone collapsed 1,811 occupations into 529 before it was caught.
- **`minEduQual` is a structured array of alternative entry routes**, not a text description.
- **`alignedTo` is dirty**: 1,914 clean NCO codes, 507 variant, 793 free text that is discarded
  and counted.
- **Content keys on ordinals**, because `pcID` repeats within a unit.
- **7,459 of 21,263 current standards have no performance criteria.** Real, not a bug.

**Verified at last run:** 160 Python tests pass · Ruff + mypy clean · tsc + ESLint + `next build`
clean · migrations round-trip and autogenerate reports no drift · import idempotent across two
runs · all endpoints 200 · multi-script search still resolves `khoon nikalna` and `रक्त` ·
21,355 skills / 149 aliases / 8 tenants / 20 jobs / 20 courses, all 20 job locations resolved
to the geography master.

**Not built yet:** matching, typed `SkillRelation` edges, embeddings, analytics instrumentation,
observability, the encryption path, and **Hindi for the national corpus** (§12).

## 5. Repository map

*Refreshed 2026-09-23 (after Sprint 27).* Authored code: `api/` 108 files / 17,152 lines ·
`scripts/` 8 / 3,690 · `tests/` 30 / 9,544 · `migrations/` 28 / 2,800 · `web/src/` 153 / 14,961
(excluding the generated client, which is another ~7,000 lines and is never counted here).

```
api/                    FastAPI modular monolith
  main.py               app assembly, health, middleware order, demo task endpoints
  worker.py             ARQ entrypoint -- configures logging, registers crons (analytics purge)
  core/                 config, database (pool + statement timeout), cache, tasks (ARQ),
                        health, security (tokens, OTP, get_current_user), authorization
                        (permissions from membership, ADR-039), logging + redaction
                        (ADR-040/023), middleware (request context, security headers,
                        body-size cap, rate limiting -- all pure ASGI), text
  modules/skills/       models.py     Skill, SkillAlias (the leaf)
                        hierarchy.py  AwardingBody, Sector, SubSector, Occupation,
                                      QualificationPack, QpSkill, QpEntryRoute,
                                      QpNcoCode, ModelCurriculum
                        content.py    PerformanceElement, PerformanceCriterion,
                                      KnowledgeParameter, GenericCriterion (~614k rows)
                        concepts.py   SkillConcept -- rows that mean the same thing
                        + schemas, service, routes, __init__ (public interface)
  modules/matching/     scoring.py (pure), service.py (retrieval + gap + courses),
                        employer.py (the same scorer reversed, batched per employer),
                        schemas, routes. No model client, by ADR-036.
  modules/analytics/    analytics_events (ADR-025). record() commits.
  modules/geography/    State, District, SubDistrict. Its own module because jobs
                        and profiles reference it and neither is a skill. No routes
                        yet -- nothing consumes it over HTTP.
  modules/marketplace/  Job, JobSkill, Course, CourseSkill, CandidateProfile + collections;
                        publishing.py (jobs) and course_publishing.py (courses) are siblings,
                        listings.py their shared policy
  modules/identity/     User, Tenant, Membership, Invitation. OTP sign-in by phone or email,
                        credential linking, organisations and their profile, consent record.
                        invitations.py holds the **three rules about who may do what to a
                        team** -- escalation, the last owner, and enumeration-safety -- each
                        in one function, because Sprint 15's finding was that a guard every
                        handler must remember is one that eventually is not there.
                        member_routes.py carries two routers: the org-scoped one, and a
                        public one keyed on the invitation token, because somebody accepting
                        is not yet a member and `require()` would 404 them out of their own
                        invitation.
  modules/privacy/      DPDP export, deletion preview and erasure. Depends on every module;
                        nothing depends on it.
  modules/applications/ Applying, withdrawing, saving, and the employer's inbox. Holds the
                        product's first deliberate disclosure: contact reaches an employer
                        because the candidate applied, and goes when they withdraw.
  modules/interests/    Registering interest in a course, and the provider's view of who did.
                        The **second** disclosure, on the same terms. A sibling of
                        applications/, never an extension: a course publishes what it teaches,
                        so a learner cannot be scored against it, and the provider inbox
                        therefore carries no card and no score at all (ADR-037).
  modules/notifications/  The outbox (ADR-006): queued in the request, sent by the worker.
                        The row names a recipient by id and never holds an address --
                        that is resolved at send time, so contact stays out of a dumped
                        table and out of every log line (ADR-023).
  adapters/notifications/  NotificationProvider protocol + console impl
  adapters/nsqf/        base.py       NsqfSource port (6 iterators)
                        documents.py  ALL document parsing, shared by every source
                        mongo.py / jsonfile.py  the two sources
                        normalise.py  levels, HH:MM, credits, slugs, NCO codes
                        importer.py   phased projection into Postgres
web/                    Next.js 16 PWA
  src/app/[locale]/     27 routes, all bilingual: browse (skills, jobs, courses), signin,
                        signup/[type], profile, matches, account, employer/[org] (+ settings,
                        candidates/[job]), audience pages, privacy/terms/grievance, status
                        (local only), error.tsx, not-found.tsx, a catch-all
  src/lib/legal.ts      PRIVACY_NOTICE_VERSION (must match api/core/config.py) + grievance officer
  src/test/harness.tsx  the three mocked seams for Vitest component tests
  src/components/       Header, Hero, HowItWorks, Audiences, BrowsePanels, CtaBand,
                        Footer, SkillBrowser, SkillRequirements, SkillQualifications,
                        SkillRelated, SystemStatus, DevPanel, PlaceholderPage, ui
  src/messages/         en.json, hi.json — no user-facing string is hardcoded
  src/lib/api-schema.d.ts  GENERATED from OpenAPI, never hand-edit
infra/docker-compose.yml   Postgres 16 + pgvector (5433), Redis 7 (6380), Mongo 7.0 (27018)
migrations/versions/    0001 (pgvector + skills), 0002 (taxonomy + search),
                        0003 (tenants, jobs, courses),
                        0004 (users, memberships, candidate profiles),
                        0005 (rich profile), 0006 (list-filter indexes),
                        0007 (widen nsqf_level to Numeric(3,1)),
                        0008 (NSQF hierarchy), 0009 (widen level_taught),
                        0010 (skills.qp_count), 0011 (geography),
                        0012 (structure, entry routes, content, pruning),
                        0013 (skill concepts + 'legacy' source),
                        0014 (analytics events), 0015 (employer analytics events),
                        0016 (organisation profile), 0017 (profile enum CHECKs),
                        0018 (user consent), 0019 (applications + saved jobs),
                        0020 (application analytics events),
                        0021 (content translations), 0022 (locale base columns),
                        0023 (notification outbox), 0024 (job_role trigram index +
                        role analytics names), 0025 (course interests + two widened CHECKs)
scripts/                seed_skills.py, seed_marketplace.py, import_nsqf.py,
                        legacy_skill_map.py (hand-authored, the only curated->NOS map),
                        retire_legacy_skills.py, seed_candidates.py (demo profiles +
                        the golden pairs), evaluate_matching.py — all idempotent
tests/fixtures/         nsqf_sample.json — the corpus in miniature, so tests need no Mongo
backups/                schema.sql (committed DDL) + README.md (restore paths, drill record).
                        Dumps are encrypted and live in ~/iism-backups, never here.
tests/                  pytest + testcontainers
```

`api/modules/skills/` is the **reference implementation** of the module pattern. Copy its shape
for every new module: own models/schemas/service/routes, narrow public interface in `__init__.py`,
and other modules import only from `api.modules.<name>`.

## 6. The local machine — quirks that will waste time

This is an **Apple Silicon (arm64) Mac, macOS 26.6.2**, and the setup has traps:

- **Default `node` is v8.16.2** via nvm. The nvm default was repointed to **v24.18.0**, but a
  non-login Bash shell may still resolve v8. When node fails with weird syntax errors, use the
  explicit path: `~/.nvm/versions/node/v24.18.0/bin`.
- **System `python3` is 3.7.1.** The project uses **uv-managed Python 3.12.14** in `.venv`.
  Always invoke `.venv/bin/python`, never bare `python3`.
- **Homebrew at `/usr/local` is the Intel build running under Rosetta.** Everything it installs is
  x86_64. Deliberately left alone — Python comes from uv (native arm64) instead. Do not install
  project dependencies through brew.
- **Docker host ports are non-default:** Postgres **5433**, Redis **6380**, chosen so any
  pre-existing local install is untouched. Docker Desktop is native aarch64, 8 GB / 8 CPU —
  raise the memory before embedding workers arrive.
- **Docker CLI was not on PATH.** `~/.docker/bin` and `~/.local/bin` were added to `.zshrc`
  (backup at `~/.zshrc.bak-20260901-141223`).
- LibreOffice, pandoc and poppler are **not installed**, so .docx → PDF rendering is unavailable
  locally. `textutil` and `qlmanage` are the macOS-native fallbacks.

## 7. Commands

```bash
make up          # start Postgres + Redis, wait for healthy
make migrate     # alembic upgrade head
make seed        # taxonomy + marketplace + demo candidates (idempotent)
make evaluate    # score the matcher against the golden set
make db-dump     # encrypted Postgres dump -> ~/iism-backups (needs IISM_BACKUP_PASSPHRASE)
make db-restore DUMP=~/iism-backups/iism-pg-....sql.gz.enc   # DROPS and recreates the target
make mongo-dump  # encrypted dump of the NSQF source of record
make mongo-restore DUMP=...  # [INTO=<db>]
make restore-drill  # dump both, restore into scratch dbs, compare counts, clean up
make db-schema   # refresh backups/schema.sql (DDL only, committed)
make import-nsqf # project the NSQF corpus from Mongo into Postgres (idempotent)
make api         # uvicorn on :8000
make worker      # ARQ worker
make web         # Next.js on :3000
make check       # ruff + mypy + pytest  <- run before claiming anything works
make gen-api     # regenerate the TS client after ANY endpoint change (reads local /openapi.json)
cd web && npm test && npm run build && npm run budget   # web tests, build, first-load JS budget
```

Three processes must run for the full stack: **api, worker, web.** The API and web reload on
change; **the worker does not** — restart `make worker` after any change to `api/`, or it keeps
running old code (found 2026-09-15: a worker from 2026-09-10 plus two orphaned copies).

## 8. Gotchas — each of these cost real time

1. **Never bind config at import time.** `from api.core.config import settings` captures the object
   before tests can override it, and silently points the engine at the *development* database.
   Always `get_settings()` inside functions. There is no module-level `settings` singleton.
2. **`Skill.search_vector` is `GENERATED ALWAYS` in Postgres.** It must be declared with SQLAlchemy
   `Computed(..., persisted=True)`, otherwise the ORM includes it in INSERT and Postgres rejects
   the write.
3. **pytest event loops must be session-scoped for both fixtures and tests.**
   `asyncio_default_fixture_loop_scope` *and* `asyncio_default_test_loop_scope` are both set to
   `session`; asyncpg connections cannot cross event loops.
4. **`migrations/env.py` must not clobber a pre-set `sqlalchemy.url`.** The test suite sets it to a
   container; env.py only falls back to environment config when it is absent.
5. **Route order matters:** `/skills/search` is declared *before* `/skills/{slug}`, or the literal
   path gets captured as a slug. There is a test guarding this.
6. **TanStack Query pauses `refetchInterval` on hidden tabs.** Status boards and job polling need
   `refetchIntervalInBackground: true` — without it the demo task appears to hang forever.
7. **React 19 lints `setState` inside `useEffect` as an error.** Use TanStack Query for server
   state, and derive values rather than storing and syncing them.
8. **Next 16 renamed `middleware.ts` → `proxy.ts`.** Also, `next dev` regenerates
   `web/CLAUDE.md` and `web/AGENTS.md` on every run — commit them, don't fight them.
9. **Postgres ships no Hindi text-search configuration.** Hindi uses the `simple` config plus
   `pg_trgm`. This partially undercuts ADR-021 and may pull the OpenSearch migration forward.
10. **The preview browser pane returns blank screenshots when scrolled while hidden.** Verify
    below-the-fold content by DOM inspection (`javascript_tool` / `get_page_text`), not screenshots.
11. **Never trust an autogenerated migration.** Raw-SQL indexes (GIN/trigram/tsvector) are invisible
    to SQLAlchemy metadata, so `--autogenerate` proposes DROPping them — which would silently break
    search. `migrations/env.py` now has an `include_object` guard with a
    `MANUALLY_MANAGED_INDEXES` set; add to it whenever you create an index via `op.execute()`.
    Autogenerate also writes the mirror-image `create_index` into `downgrade()`, which fails with
    DuplicateTableError — delete those too.
12. **Verify migrations by exit code and table counts, not by grepping log output.** A failed
    downgrade rolls back and leaves the version row untouched, so a naive `grep 'Running downgrade'`
    reports success on a migration that actually errored. This bit us once already.
13. **`include_object` must be passed in BOTH `run_migrations_offline` and `do_run_migrations`.**
    Autogenerate uses the online path; patching only the offline one silently does nothing.
14. **Alembic does not diff CHECK constraint bodies.** Widening `tenant_type` to allow `personal`
    was invisible to autogenerate; without a hand-written `drop_constraint`/`create_check_constraint`
    every candidate sign-in would have failed on insert.
15. **`db.refresh()` does not cascade nested eager loads,** and a plain re-query returns the stale
    instance from the identity map. Mutating a relationship then serialising it needs
    `selectinload(...).selectinload(...)` **plus** `.execution_options(populate_existing=True)`.
    Without the latter the query succeeds and returns the wrong data — no error at all.
16. **Application-written timestamps need `DateTime(timezone=True)`.** A bare `Mapped[datetime]`
    maps to `TIMESTAMP WITHOUT TIME ZONE` and asyncpg rejects an aware value outright.
17. **`ENVIRONMENT=test` is not `development`.** Config guards that relax "in development" must
    list both, or the whole suite fails at import with a validation error.
18. **A route taking `body: dict` loses FastAPI's automatic 422.** The generic
    `/me/profile/{collection}` handler must catch `ValidationError` and re-raise as 422, or bad
    input returns 500. Same for DB CHECK violations — validate in the schema, not just the column.
19. **Correction to gotcha 14:** Alembic *does* detect newly-**added** named CHECK constraints. It
    only fails to diff **changed** bodies. Both were seen this project.
20. **Adding a NOT NULL column to a populated table needs `server_default`,** or the ALTER fails
    outright on the existing rows.
21. **Routes mounted via `include_router` do not expose `.path` on `app.routes`** in this FastAPI
    version — they are wrapped in `_IncludedRouter`. Inspect `app.openapi()["paths"]` instead;
    checking `app.routes` silently finds nothing and looks like the route is missing.
22. **Never purge `sys.modules` to rebuild the app in-process.** It leaves other tests in the same
    file holding a different `get_settings` with its own `lru_cache`, and the contamination only
    shows up as an unrelated test failing. Use a subprocess.
23. **pytest's logging plugin swallows handler output for our loggers.** A `StreamHandler` capture
    comes back empty, so log-content assertions pass vacuously. Assert on the rendered record via
    monkeypatch, and always assert the capture is non-empty first.
24. **String-replace edits silently no-op after ruff reformats.** Three separate edits this project
    reported success while changing nothing. Always `assert old in s` before replacing.

33. **Widening a database column is half the job — the response models are the other half.**
    Migration 0007 widened every `nsqf_level` to `Numeric(3,1)`; the Pydantic schemas still said
    `int`. 8,055 skills (38%) then failed serialisation and `/skills` returned 500 for the whole
    page. Nothing caught it because the 52 curated skills all sit at whole levels, so every
    transliteration and search check kept passing. Grep the schemas whenever a column type changes.
34. **Output schemas must not re-validate stored data.** A constraint on an output model turns one
    odd row into a 500 for the entire response. Constrain input (`NsqfLevelIn`), leave output
    permissive (`NsqfLevel`).
35. **NSQF levels have half-steps.** 2.5, 3.5, 4.5, 5.5 and 6.5 are real; 4.5 alone covers 6,532
    skills and 905 qualifications. Anything typed `int` or a dropdown listing 1–10 silently hides
    38% of the taxonomy — and a filter that returns a correct *empty* page announces nothing.
36. **The two collections name the same concept differently, and this caused a real error.**
    A standard states its level in `nsqf`; a qualification states it in `nsqfLevel`. Checking the
    qualification's spelling against standards returns zero every time, which reads exactly like
    "a NOS has no level" — and all 27,538 carry one. That wrong conclusion was written into the
    schema, four commit messages and every document before it was caught. The same trap applies to
    `type` vs `nosType` (3,952 vs 98.7% coverage) and `Sectors` vs `sectors`. **Never conclude a
    field is absent from one collection using another collection's spelling** — enumerate the
    actual field paths per collection first. Full record in
    [docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md).
37. **Elective and optional NOS are nested in named groups.** Flattening them to plain links turns
    "choose one of these" into "all of these are required". `qp_skills.group_name` is what keeps
    that distinction; reading only `compulsoryNos` loses 1,756 links outright.
38. **The model-curriculum key is spelled `compulsary` in the source**, and `nos.elective` /
    `nos.optional` carry another 749 usable links. Reading only the first list found 128
    curriculum-to-unit links where there are 877.
39. **`$exists: true` matches the empty string.** 2,399 curriculum entries have a `unitCode` that
    is present but blank. They are counted in the report (`mc_entries_without_code`), not dropped
    in silence and not raised one by one.
40. **Ordering 21k rows alphabetically is a product decision, not a default.** It opens the
    taxonomy on "0JT" and "10.1. Case Studies". `skills.qp_count` is denormalised precisely so the
    browse can order by prominence — an ORDER BY over a correlated subquery cannot use an index.
41. **Only the latest version of each code is imported.** `(code, version)` is the natural key
    — 21,263 distinct `unitCode` across 27,538 documents. Prior versions stay in Mongo; that is
    what making it the source of record buys (ADR-034).

42. **Sector-local identifiers are not global, and this trap fires twice.** An occupation's
    two-digit `code` is scoped to a sector -- that was caught. Its `occupationID` is *also* scoped,
    reusing `"1"`, `"2"`, `"3"` across forty-odd sectors -- that was not, and keying on it collapsed
    1,811 occupations into 529. Nothing failed; the count was simply wrong. **When a source id looks
    global, count the distinct values before keying on it.**
43. **`minEduQual` is a structured array, never a text description.** 14,877 alternative entry
    routes across 4,564 qualifications, each pairing an education requirement with an experience
    one. An earlier pass counted non-empty arrays and called them text values. `"NA"` experience
    stays NULL -- "no experience required" and "not stated" would score differently.
44. **`alignedTo` is dirty and must be parsed, not stored.** Of 3,214 values: 1,914 well-formed NCO
    codes, 507 in variant formats (U+2010 hyphens, `NCO 2015- ` spacing, comma-separated multiples),
    and 793 free text like `(CNC Operator)`. The free text is discarded and counted. Sampling one
    clean value and generalising is how this was first misreported -- the same mistake shape as the
    level error.
45. **Content rows key on `(parent, ordinal)`, never the source's own id.** `pcID` repeats within a
    unit in 17 of 6,000 standards, `kpID` in 1, `skillID` in 2. A natural key on the source id fails
    partway through the import, after thousands of rows are already written.
46. **Content is deleted and rewritten each run, not upserted.** It is wholly derived and owned by
    the importer, and a revised standard with fewer criteria must not leave the surplus behind.
    Anything later attached to content (translations, embeddings) must therefore live in its own
    table, not as a column on these rows.
47. **Free prose columns are `Text`, not `String(n)`.** Two import runs died on `varchar(512)`
    overflow -- occupation names reach 894 characters and entry-route specialisations 735. Postgres
    stores `Text` and `varchar(n)` identically, so a cap buys nothing except a future failure. Keep
    a bound only on genuine codes and enums.
48. **Autogenerate emits unnamed foreign keys.** `op.create_foreign_key(None, ...)` produces a
    downgrade calling `op.drop_constraint(None, ...)`, which fails outright. Name every FK before
    applying a generated migration -- twelve appeared across 0011 and 0012.
49. **A source iterated more than once double-counts its own diagnostics.** `iter_nos` now runs
    three times (collect, then two content passes), so `skipped_documents` tripled. Capture
    per-source counters at the end of the collect phase, not at the end of the import.
50. **Regenerating a migration: never delete the old file before the new one exists.** A glob that
    did not match left the database at a revision whose file was gone, and alembic could then do
    nothing in either direction. Autogenerate against a scratch database instead, and reconcile.
51. **`make check` is not enough after a data-model change.** It passed while `occupations` held 529
    rows instead of 1,811. Compare the import report against independently computed expectations --
    for content, the ceiling is the sum over the *current version* of each code, which is how
    38,340 elements was confirmed correct rather than short.

52. **A model with a cross-module foreign key must import the target module.** SQLAlchemy resolves
    `ForeignKey("districts.id")` against the metadata at mapper-configuration time, so a script
    importing `marketplace.models` without `geography.models` dies with `NoReferencedTableError`.
    This fired twice in one sprint — marketplace→geography, then skills→concepts. Import for the
    side effect and say why in a comment; the alternative is every script needing to know the
    whole graph.
53. **A `Literal` on an output schema is a latent 500, and this is the second time.** Adding
    `legacy` to `skills.source` broke `GET /skills/{slug}` for every retired row until the schema
    listed it. Output models stay permissive; the constraint belongs on input.
54. **A many-to-one remap creates duplicate association rows.** 52 curated skills collapse to 38
    standards, so a job listing both "hand hygiene" and "infection control" tried to insert
    `HSS/N9618` twice and hit `uq_job_skill`. Merge on the strongest signal — highest importance,
    mandatory beats optional — rather than taking the first or last.
55. **`scripts/` is not an importable package.** Sibling imports work (`from legacy_skill_map
    import ...`) because Python puts a script's own directory on `sys.path`; `from scripts.x import`
    does not, because only `api*` is installed.

## 9. Conventions that must not be broken

- No business logic in route handlers — validate and delegate to a service.
- Every external system behind an adapter in `api/adapters/`. No direct SDK calls from modules.
- Async work never runs inline in a request handler.
- No user-facing string hardcoded — `en.json` and `hi.json` updated together.
- Every header/footer link must resolve; unbuilt pages render `PlaceholderPage`, never 404.
- New architectural decisions get a new ADR, not a silent divergence.
- Aadhaar, resumes and assessment results must go through the ADR-023 encryption path — including
  staying out of logs. Resume-derived embeddings inherit the same sensitivity.

## 10. Git state

**Merged 2026-09-21.** `v2/foundations` reached `origin`, PR #1 was opened and merged into `main`
(merge commit `7b6337a`), and **CI ran green on it** — the first time CI had ever run on this work.
Verified with the API, not assumed.

This section was wrong in the most expensive possible way, and the shape of the mistake is worth
keeping. It said "Pushed 2026-09-07 … that risk is closed", because the last commit to actually
reach the remote was one called *"Correct the git section: the branch is pushed"*. Sprints 11, 12,
13 and 14 — five commits and several thousand lines — then accumulated locally while the document
went on asserting they were safe. **A claim about the remote is only true at the moment it is
checked**; re-check it, do not read it here.

- Branch **`v2/foundations`**, tracking `origin/v2/foundations`. Work continues on it; `main` now
  contains everything through Sprint 24.
- Verified with `git log origin/v2/foundations..HEAD`, which must be **empty**. Comparing the
  branch tip against the document is what failed for four sprints.
- **CI runs on pull requests and on `main`.** Both jobs — *API: lint, types, tests* and *Web: lint,
  types, build* — passed on the merge commit, which is what finally exercised Sprint 20's
  dependency audits and the first-load budget outside this laptop.
- **`gh` is still not installed**, so PRs are opened in the browser at
  `https://github.com/hegdekattehnew/iism/compare/main...v2/foundations`, and their title and
  description have to be pasted by the owner. Two consequences worth knowing: the session cannot
  read CI itself without the GitHub API (unauthenticated reads work for this public repo), and
  **pasting a rendered Markdown file loses its formatting** — send raw text, not a `.md` the
  client will render.
- **Dependabot is live on `main`** and opened 5 PRs the moment it merged (16 web updates, 4 Python,
  three GitHub Actions bumps). Its `uv` update job fails; the npm and actions jobs succeed. That is
  Dependabot's own infrastructure, not this repo's CI.
- Two things a reviewer needs telling: it is a 211-file, +35,107-line change spanning eight
  sprints and is not reviewable as a single unit, and it **contains a deliberate rollback**
  (`c10829f` discards `a62d964`), so reading commit-by-commit means passing through work that was
  undone on purpose.
- The NSQF work reads as a sequence worth understanding in order: `a62d964` projected the corpus,
  `5cf496f` made it usable at 21k rows, `75abc17` added tests, **`c10829f` rolled the whole thing
  back** after an audit, and `4230c9c` re-migrated against the complete master data. The rollback
  commit is not a failure to skim past — it carries the audit that made the second attempt right.
- `1fd92af` connected the taxonomy to the marketplace; `3b69a42` added matching.
- The original `app/` (identity module, auth, 8 actor types) remains in history on `main` at
  `ef59c4e`. Recoverable if that work is ever worth mining.

## 10a. Backup and restore

`backups/README.md` is the full account. In short:

- **A crashed container loses nothing** — the data is in Docker volumes. Deleting one loses it.
- Since Sprint 20 every dump is **encrypted** (`IISM_BACKUP_PASSPHRASE`, openssl aes-256-cbc with
  pbkdf2) and written to **`~/iism-backups`, outside the working tree**. `make db-dump` /
  `db-restore` for Postgres, `make mongo-dump` / `mongo-restore` for MongoDB — **which had no
  backup at all before**, although it is the corpus's only source (ADR-034).
- **`make restore-drill`** dumps both, restores into scratch databases, compares exact counts and
  drops them. **Run 2026-09-11, passed**: Postgres 36 tables, key counts identical; MongoDB 7
  collections, every count identical.
- The last plaintext dump (`backups/iism-20260907-1003.sql.gz`, pre-encryption, real accounts in
  the clear) was **deleted by the owner on 2026-09-11**. It was gitignored and never committed.
- `backups/schema.sql` (DDL) is committed and refreshed with `make db-schema`.
- Almost every Postgres row is derived and rebuilds from MongoDB with `make import-nsqf && make
  seed`. People — accounts, consent, profiles, analytics — exist only in a dump.

## 11. What comes next

*Rewritten 2026-09-22. The previous version had gone stale in the way that misleads rather than
merely ages: it called deployment "Sprint 22" (Sprint 22 was languages and notifications), and
listed course-provider self-serve publishing and organisation email sign-in as upcoming when both
shipped in Sprints 12–14. **Delete an item here when it ships; do not let it drift.***

**Deployment is deferred by the owner.** It is not blocked on design — §13 lists what it needs —
and it stays out of the sprint queue until they say otherwise.

### The homepage counts (reported twice, 2026-09-23, fixed the same day)

"I added a job listing and the numbers under the marketplace section are not updated." Two
distinct causes, a day apart, and the second is the more interesting one.

**First: two caches, neither invalidated.** The figures are computed live, but
`useOrgJobMutations` refreshed `["org-jobs", slug]` and nothing else, and `sw.js` served
`/marketplace/` stale-while-revalidate — so on a production build the number was permanently one
visit behind. Probed against the committed worker: all three count endpoints answered from cache
while online. `web/src/lib/counts.ts` now holds the keys and `LIVE_DATA` in `sw.js` makes the
counts network-first.

**Second: the number was right and its definition was not the reader's.** The panel counted
**open** vacancies, and `scripts/seed_marketplace.py` closes `inventory-clerk-nagpur` on every run
— so publishing a twenty-first vacancy moved the figure 19 → 20. Nothing was broken and nothing a
cache fix could reach. The panel now leads with `jobs_posted` and names `jobs_open` underneath
when they differ.

- `posted_job()` is the count's predicate, `open_job()` stays the listings'. A bare
  `status == "published"` in a count is deliberate; the docstring says so, because the rule beside
  it says every public listing must use `open_job()` and the next reader would file this as the
  one that was missed.
- **Both payloads carry both names.** `jobs` meaning "open" in one response and "posted" in
  another is the trap; the rename made `tsc` fail on the one stale reader, which is the whole
  reason it was a rename and not a redefinition.
- **Not monotonic, and that is the honest shape.** Unpublishing removes the page and removes the
  row, so the figure never names a vacancy a visitor cannot open. A true lifetime tally needs
  `first_published_at` and would advertise vacancies that exist nowhere on the site. Walked
  through every state against the live API: draft 21/20 → published 22/21 → closed 22/20 →
  reopened 22/21 → unpublished 21/20.
- **The second line hides when the two figures converge** — the branch a seeded database never
  shows, because the seed always closes one. It has its own test for exactly that reason.

No migration: `ix_jobs_status_closed` is on `(status, closed_at)`, so the posted count uses the
leading column and gets the same index-only scan.

### Sprint 28 — clear the decks (done 2026-09-23)

The monetisation ADR and payment port are **deferred by the owner**; the gate ADR-025 sets cannot be
cited honestly yet (five golden pairs, all candidate→job where ADR-025 means course; click-through
computable since Sprint 24 and computed nowhere; enrolment conversion at zero and deliberately not
modelled). Scoped as one sprint this came to ~44 files, so it is two — Sprint 29 carries the admin
pages and the golden-set expansion.

**Geography — done 2026-09-23.**

- **`PlaceIndex` is the one resolution rule**, pure and session-free, with two loaders:
  `resolve_location` narrows to the names one write could reach, `load_place_index` loads the master
  for the import sweep. `resolve_location`'s signature is unchanged, so none of its six callers moved.
- **The importer's private alias map and private lookup are gone.** A test asserting the two maps
  were identical had kept the letters in step and not the algorithm.
- **The churn is fixed and measured.** Two consecutive `make import-nsqf` runs:
  `locations_updated=20` then `locations_updated=0`, with sha256 digests over
  `(id, state_id, district_id, updated_at)` on `jobs` and `candidate_profiles` **identical before
  and after both**.
- **A second defect found while measuring**: `scripts/seed_candidates.py` never resolved geography
  at all, so all twenty seeded preferred locations carried NULL on both FKs and `candidate_facts` —
  which reads exactly those columns — saw nothing. Half of Sprint 23's locality tie-break had no
  input. Fixed the way Sprint 15 fixed the marketplace seed; probed by clearing the twenty and
  running the seed alone, 20 unresolved before and 0 after.
- `make evaluate` still prints **88 / 45 CAPPED / 86 / 100 / 0**, bit-identical, which matters
  because resolving preferred locations changes what the tie-break sees.
- 606 backend tests (was 598). Non-vacuity: neutering the state filter fails six of the seven new
  tests; reverting the change-guard fails the seventh on `assert 1 == 0`.

**The operator surface — done 2026-09-23.** `tenants.is_verified` had existed since Sprint 12 with
**no writer of any kind**. A marketplace whose verified badge nobody can grant has no verified
organisations.

- **ADR-042** records a second authority beside ADR-039's: global, granted by `users.is_staff`
  alone, expressed as `OPS_*` members of the same closed `Permission` enum. `require_operator()`
  sits beside `require()` and returns an `OperatorContext` with **no tenant on it**.
  `ROLE_PERMISSIONS` may never hold an `OPS_` member — `owner` is the widest role there is.
- **No HTTP writer for `is_staff`, ever.** `scripts/grant_staff.py` (`make grant-staff`) is the only
  one; it needs database credentials, refuses to create an account, and prints the full roster after
  every run including the dry one.
- **Migration 0028 dropped `is_verified`** and derives it from `verified_at`. Free only in this
  sprint: nothing had ever written the boolean, so no row could disagree. `verified_at` +
  `verified_by` + a ≥10-character `verification_note`, with a CHECK making an unevidenced badge
  **unrepresentable**. Down-and-up rehearsed; `alembic check` clean.
- **`tenant_verification_events` is append-only** and revocation is a new row. On revoke the
  tenant's three columns go NULL, so a revocation's reason survives only in the log — which is why
  both exist. `_delete_tenant` went from eleven tables to twelve.
- **Exercised live, not inferred**: granted MedLife through the API and watched `is_verified` flip
  to true on the public `/jobs` payload for both its vacancies; granted Apollo Care and read
  **"Verified"** on `/en/employer/apollo-care-hospitals/settings` in the browser; revoked it and
  read **"Not yet verified"**. Anonymous 401, non-staff 404 with a body byte-identical to
  `/ops/nonsense`, operator 200 on the same URL.
- **`hiring@apollo-care.example` is now an operator** on the dev database, and the verification
  events from those demonstrations are still there — they are append-only by design, so deleting
  them to tidy up would contradict the thing being demonstrated.
- 628 backend tests (was 606). Four probes: removing a route's guard fails four tests including the
  route walk; letting `_OWNER` reach `OPS_ORG_VERIFY` fails the disjointness test; removing the
  CHECK **from migration 0028** fails the database test (removing it from the model does not — the
  test database is built from migrations, which is the point).
- **A finding worth keeping**: this FastAPI keeps included routers nested, so `app.routes` holds
  `_IncludedRouter` objects and exactly two bare `APIRoute`s. The first route-guard test found zero
  `/ops` routes and **failed on its own anti-vacuity assertion** rather than passing against an
  unguarded back office.

**Still to do in Sprint 28:** nothing. Sprint 29 carries the `/admin` pages and the golden set.

### Sprint 29 — a back office you can see, and a matcher you can defend (done 2026-09-23)

**The `/admin` pages.** `OperatorOnly` keeps three answers apart that a permission gate usually
collapses: not-found for a signed-in non-operator (the same answer the API gives), a sign-in prompt
for somebody signed out, and **nothing at all while the answer is in flight** — the branch that
rots, because it is invisible on a fast connection and 404s every operator on a slow one. It has
its own test, and the first version of that test passed against the bug: it asserted the children
were absent, which is also true when the signed-out prompt is showing. It now asserts the prompt is
absent too.

- `is_staff` rides on `/auth/me`, so the gate costs no extra request.
- **The harness was lying about signed-out.** `derived()` returned a populated account regardless of
  `world.signedIn`, so every signed-out branch was untestable through that seam. Fixed; the whole
  suite still passed, which says the old behaviour was never load-bearing.
- Budget unchanged at **672/684 KB** — admin routes are route-local, not in the header or the barrel.
- Exercised in a browser: granted MedLife through the UI and watched the badge reach the public
  `/jobs` payload, then withdrew it. **The withdrawal note corrects the grant**: the note I typed
  when granting claimed a lab licence had been checked and nothing had been, and a false evidence
  note undermines the one field the whole feature exists for. Both decisions are in the history.
- `/hi/admin/...` at 360×640: no overflow, dates localised, the operator's own note left in the
  language they wrote it in.

**The golden set: 5 pairs → 34 pairs, 7 orderings, 16 course expectations.**

- **Nine labels failed on the first run and all nine were mine.** Three claimed
  `capped_missing_mandatory` for candidates already scoring below 45 (`capped` is
  `raw > MANDATORY_GAP_CAP`, so it was correctly False — they get `missing_mandatory` now); four
  named `inventory-clerk-nagpur`, which the seed closes as filled; one ordering was written
  backwards. The scorer was right every time.
- **`below_assessed_peer` is gone as a per-pair label**, and the reason is structural rather than an
  oversight: "ranks below that other candidate" names a *pair*, and a per-pair label has nowhere to
  put the peer. It lives in `GOLDEN_ORDERINGS` now. The `if/elif` chain gained the `else` it never
  had, so an unrecognised label fails instead of asserting nothing.
- **Course recommendation has labelled data for the first time** — ADR-025's precision@5 is about
  course recommendation, and `courses_closing_gap` had none of any kind. That is one third of
  Sprint 28's uncitable gate now citable.
- **`make evaluate` is still not in CI and should not be.** It needs the corpus, which is not in the
  repository, so a scheduled workflow would be red every morning for a reason nobody could fix.
  `tests/test_golden_set.py` (19 tests) runs in CI instead and catches both classes of mistake above
  **statically** — probed by re-introducing each and watching the named test fail.
- Probes on the scoring run itself: making `self_declared` score like `certified` fails the evidence
  ordering by name; removing the mandatory cap fails fourteen expectations by name.

### Sprints 30 and 31 — the audit, and acting on it (done 2026-09-24)

No new functionality, by instruction: *"check the Scope from our baseline documents and the reality
of completed items."* Three axes audited — route-handler delegation, tenant scoping, swallowed
exceptions — and the result is worth stating as a whole: **the server is in better shape than the
documents claim, and the client was in worse shape than its tests suggested.**

- **Tenant scoping audited clean, and no security work followed.** All 29 `{org_slug}` routes
  carry `require(...)`; every service reachable from them re-filters on `tenant_id` in the same
  `WHERE` as the slug or id, including both classic IDOR shapes. The one auth-free surface is the
  demonstration console, behind an allowlist that fails closed. Saying so *is* the result.
- **Eleven frontend writes failed in silence, and the worst were not obscure.** `SkillsSection` --
  the file whose own docstring calls it "the only part of a profile that changes a match score" --
  had no `error`, `isError` or `onError` anywhere. `Notices.markRead` never read `error` at all,
  and openapi-fetch resolves on a non-2xx, so `onSuccess` ran on a 500 and the button did nothing
  for ever. See the frontend conventions in `CLAUDE.md`.
- **One was actively misleading**: an expired session was told its vacancy needed a required
  standard it already had. Fixed and verified in a browser against the real API.
- **`ProviderWorkspace`'s docstring described a fix the file never contained** -- past tense, four
  sprints old, `isSignedOut` never imported there. Found while writing the tests, not by the audit.
- **`web/src/lib/mutation-errors.test.ts`** reads the source and fails when a `useMutation` has
  neither an `onError` nor anything reading its `.isError`. **`tests/test_worker_schedule.py`**
  asserts the four feature crons are registered where arq actually reads them.
- **`docs/scope-reconciliation.md`** is the ledger: seven places the product definition and the
  tree disagree, each naming the file that proves it. The `.docx` is deliberately not amended.
  Its sharpest finding is in no other document: **three of the four `SKILL_SOURCES` have no writer
  outside the seed**, so `EVIDENCE_WEIGHT_SHARE = 0.10` is a constant for every real candidate --
  a tenth of the match score carries no information in production.

### Sprint 32 — every handler delegates (done 2026-09-24)

The audit recorded 17 route-handler violations as accepted; the owner reversed that and asked for
them fixed before any other work. All 17 moved, plus two the audit had classed as borderline, so
the route layer now makes **zero** calls to `db.*`, `select()` or `record()`.

- **The point was to preserve the ordering, not bury it.** Fifteen of the seventeen existed because
  `record()` commits and therefore has to run after the business commit. Each service function now
  commits and then records, with the reason written beside it -- one function owns the sequence
  instead of every handler remembering it.
- **`tests/test_route_delegation.py` is the guard**, and it names the module, the handler and the
  call when it fails. Probed by restoring `update_organisation`'s old shape.
- **One deliberate behaviour change**: `member_removed` now fires when somebody *leaves*, not only
  when an owner removes them. Moving the record into the single writer is what exposed it -- the
  leave path had never been measured. `{"self": true}` keeps the two apart.
- Also found and fixed while doing it: `update_organisation` had **no service layer at all**, which
  is how `contact_email` went eight sprints without the normalisation every other address has.

### Sprint 33 — the monetisation ADR, and a payment adapter port (next)

Sprint 27 finished the job-connect pillar's outstanding work. The owner's stated direction is a
marketplace that also **sells courses** and carries **gig work**, and the honest next step is the
decision, not the code.

- **Write ADR-043 first, superseding ADR-025** (042 went to operator authority, which
  landed first). ADR-025 says "free v1, no billing implementation…
  a successor ADR is required before any billing code is written, **and must cite those metrics**"
  — precision@5 on the golden set, candidate-to-course click-through, provider-reported enrolment
  conversion. Two of the three are still thin (5 golden pairs; click-through joinable only since
  Sprint 24). **The ADR should say so rather than pretend the gate was passed** — deciding to
  proceed with weak data is a legitimate call, and recording it as weak is what makes it honest.
- **Then the port, and only the port.** `api/adapters/payments/` as an interface with a console
  implementation that refuses production, exactly as `ConsoleNotificationProvider` and
  `ConsoleEmailProvider` do. No gateway, no orders, no entitlements. ADR-017 has listed payment
  providers as a future adapter since the beginning and nothing was ever written.
- Sequencing after that is in the pillar assessment below: course checkout (~2 sprints), then gig
  as its own module with its own ADR.

### Also outstanding, in rough order

- ~~**Grow the golden set.**~~ **Done 2026-09-23 (Sprint 29)**: 34 pairs, 7 orderings and 16 course
  expectations, including the first labelled data course recommendation has ever had. The
  monetisation ADR can now cite one of ADR-025's three metrics honestly; the other two still need
  users rather than code.
- **SMS, which is what job alerts actually need.** Sprint 27 shipped in-app plus email; 39 of 40
  candidates are phone-only, so most alerts land only when somebody opens the site. This is
  blocked on DLT registration, not on design.
- ~~**`is_verified` still has no writer.**~~ **Closed 2026-09-23 (Sprint 28)**: `users.is_staff`, `/ops/*` and `make grant-staff`. See the Sprint 28 entry above.

### The three pillars, and where each actually stands

*Assessed 2026-09-22 against the tree, not from memory. The owner's stated goal is a marketplace
that sells courses, connects jobs, and carries gig work.*

- **Job connect — built, end to end**, and ahead of the other two. Publish → NSQF-scored match →
  apply → employer inbox → contact disclosed. What remains is Sprint 26's lifecycle and reach.
- **Selling courses — listed and demanded, never sold.** `Course.fee_inr` exists and renders, and
  **nothing downstream reads it as money**: no payment adapter (`api/adapters/` holds
  `notifications/` and `nsqf/` and nothing else), and no order, entitlement, enrolment, refund,
  payout or invoice table in any of 26 migrations. **ADR-025 forbids writing billing code** until
  a successor ADR cites precision@5 on the golden set (5 pairs), candidate-to-course click-through
  (only *joinable* since Sprint 24, with no volume behind it) and provider-reported enrolment
  conversion (no surface at all). That gate has not been passed. Note also that Sprint 24's
  "interest, not enrolment" reasoning **inverts** the moment money moves through the platform: if
  we take the payment, we are the system of record for the enrolment.
- **Gig work — does not exist.** Zero hits for "gig" or "freelanc" across `api/`, `web/src`,
  `docs/` and `scripts/`. It is not a feature but a third marketplace with different physics:
  `Job` encodes a permanent salaried vacancy (monthly salary bands, years of experience,
  `notice_period` on the profile), there is no availability model, no proximity ranking beyond
  Sprint 23's tie-break, no reputation layer and no completion record for a payment to settle
  against. Downstream of the money layer by necessity, and it should get an ADR before code.

**Nothing built so far has to be undone for any of it**, which is the important finding. The
expensive assets — 21,303 NSQF standards with role search, one pure deterministic scorer, one
identity many roles, two working consent-and-revocation disclosure loops, geography to
sub-district — are exactly what all three pillars need.

Suggested order after Sprint 26: the monetisation ADR and a **payment adapter port only** (an
interface with a console implementation that refuses production, as `ConsoleNotificationProvider`
does), then course checkout, then gig as its own module.

### Then, in rough order of value

- ~~**Grow the golden set.**~~ **Done 2026-09-23 (Sprint 29).** 34 pairs against 20 vacancies, plus
  orderings and course expectations. Still short of the 50–100 the original plan named, and the
  remaining gap is labelling effort rather than machinery.
- ~~**`is_verified` has no writer.**~~ **Closed 2026-09-23 (Sprint 28).** The API half is done —
  `users.is_staff`, `/ops/*`, `make grant-staff`, ADR-042. **The `/admin` pages are Sprint 29**;
  until they land an operator uses `/docs` or `curl`, which is fine for a handful of internal
  people and is why the UI was the half that could be cut.
- **CV upload and LLM extraction.** Deferred in Sprint 23 after establishing that it fills
  experiences and education, which no scorer reads, and needs multipart, object storage, a documents
  table, PDF/DOCX extraction, AES-256-GCM with KMS (ADR-023) and an `LLMProvider` adapter (ADR-031)
  before one skill reaches a profile. Revisit once role-led suggestion shows what gap remains.
- **Semantic similarity** — the deliberate omission from Sprint 10 (ADR-007 names it; ADR-036 says
  deterministic overlap ships first so there is a baseline). Embeddings over performance criteria,
  never titles: `OJT` and `Project` embed to noise. Also the answer if role search proves too weak.
- **Hindi for the corpus.** The interface is fully bilingual; the *corpus* is not. Say that plainly
  in any demo. ~$5 for the navigable surface, blocked on credentials rather than design.
- **Confirm the PWA installs on a real device.** Manifest, icons and worker are in place and tested
  for correctness, but the in-app browser pane will not register a worker, so nothing has proved
  Chrome offers "Install". One phone, five minutes — until then say "installable" with the caveat.
- **A learner-facing notice when a provider marks "contacted"**. Found in Sprint 24 and
  deliberately not built. *(Its sibling — notifying applicants when an organisation deletes itself
  — was closed on 2026-09-23 along with the organisation-deletion route.)*
- **Ownership transfer as one act.** Sprint 25 makes it possible — promote, then leave — but it is
  two steps and the second can fail on its own. A single "hand over and leave" would be safer.
- **`CLAUDE.md` cites ADR-026 for the siblings-not-generalisations rule.** ADR-026 is *Supply
  Acquisition Strategy*; that rule has no ADR and lives only in `CLAUDE.md`. Either write it as one
  or stop citing a number for it.
- Still unbuilt and ADR'd: career paths (ADR-008, and the NCO codes now exist), typed `SkillRelation`
  edges, observability (ADR-019), the ADR-023 encryption path, caching as caching (ADR-020).

### Measured in Sprint 27 (performance and security)

- **The lifecycle predicate costs nothing.** A/B of the same queries with and without
  `closed_at IS NULL`, 200 iterations each: browse `+0.001ms`, homepage count `-0.001ms`, matching
  retrieval `-0.001ms`. The homepage count uses an index-only scan on the new
  `ix_jobs_status_closed`. All five new query shapes plan sub-millisecond.
- **Do not compare raw throughput against §12a without checking the box.** A re-run measured
  `/skills?limit=24` at 72 rps against §12a's 350 — but `/skills` is **untouched** by Sprint 27
  and degraded 4.9×, while `/jobs`, which the sprint *did* change, degraded only 2×. Docker
  Desktop was at 56% CPU, Spotlight at 34%, load 3.38 on 8 cores, and the API was running with
  `--reload`. The database is ~0.1ms of a ~126ms request, which is §12a's own conclusion intact:
  **the bottleneck is Python CPU, not the database.**
- **Security spot-checks all held**: the new close/reopen endpoints answer 401 anonymous and
  **404 (never 403)** to a non-member; the public job payload still carries no `contact_email`;
  the rate limiter still returns 429 under a burst; nothing in `api/` reads the `ssc` collection;
  and the alert sweep logs four integers and no identity. 103 security-focused tests pass.

### Left behind by Sprint 26, worth knowing

- **The first-load budget has 16 KB of headroom** (668 KB against 684). Radix Dialog took ~33 KB
  and `next/dynamic` made it *worse* rather than better, because the header mounts the dialog on
  every route anyway. **The next component added to the header will breach it**, and the answer
  then is either a hand-rolled portal (~2 KB, but a focus trap is genuinely hard) or raising the
  budget deliberately with a reason.
- **Fonts cost 47 KB on an English page and 166 KB on a Hindi one**, measured against a production
  build. That is the price of Hindi rendering the same on every platform; it is worth it, and it
  should be said out loud rather than discovered.
- **`is_verified` had no writer until Sprint 28**, so anybody may create an organisation under any
  name and nothing vouched for it. The duplicate guard added this sprint is per account, not
  global — two accounts may still both
  create "Apollo Care", which is correct (two employers may share a name) and is *not* a substitute
  for verification.

### In flight, not on the branch

*Nothing. The geography fix that sat here for five sprints landed in Sprint 28, rewritten against
current code rather than carried from the stale worktree — see the Sprint 28 entry above. The
`claude/angry-jackson-46292c` worktree and branch are deleted.*

## 12a. Measured performance (re-audited 2026-09-05, after the corpus landed)

Single uvicorn worker, load generator on the same box, so **treat throughput as a floor**.
The database was **485 MB** when this was measured; it is **557 MB** as of 2026-09-09, across
21,355 skills and ~614,000 content rows. The timings below were not re-run.

| Endpoint | c=10 rps | c=50 rps | p50 | p99 (c=50) |
|---|---|---|---|---|
| `GET /skills?limit=24` | 350 | 313 | 19 ms | 589 ms |
| `GET /skills/{slug}/requirements` | 235 | 230 | 34 ms | 895 ms |
| `GET /skills/search?q=` | 154 | 183 | 57 ms | 648 ms |
| `GET /jobs` | 135 | 149 | 66 ms | 1,159 ms |

**The 2026-09-02 conclusion still holds: the bottleneck is Python CPU, not the database.**
Throughput is flat across concurrency while p99 climbs an order of magnitude — the signature of a
saturated single process, not a slow query. Serving 614k content rows did not move the numbers,
because every hot path is index-backed:

- `/skills` first page uses `ix_skills_qp_count` with an incremental sort.
- Content fetch is two index scans (`ix_performance_elements_skill_id`, then
  `ix_performance_criteria_element_id`) — 7.5 ms for a 128-criterion standard.
- FTS still uses the GIN index at 21k rows; the trigram fallback uses `ix_skills_name_en_trgm`.

**One new weakness the corpus exposed.** Deep offset paging degrades badly: `offset 21000`
seq-scans and fully sorts all 21,355 rows (70 ms against 7 ms for the first page). Fine while
people browse the first pages, wrong if anything ever walks the catalogue. Keyset pagination on
`(qp_count, name_en)` is the fix when that matters.

**Still not ready for 1000 concurrent users.** Outstanding, in order:

1. **No caching.** Redis serves only OTP, refresh tokens and the ARQ broker — ADR-020 is
   unimplemented. The taxonomy is near-static and the bulk of the database is read-only
   reference data.
2. **Single uvicorn process.** Multiple workers is the cheapest win available.
3. **Connection pool maths.** 15 connections per process against `max_connections=100` caps you at
   ~6 processes; PgBouncer before that.
4. **Deep offset paging**, as above.

Fixed since the last audit: the four missing filter indexes, and the browsers that fetched
`limit=200` and filtered client-side — `/skills` now pages server-side.

## 12b. Security posture (audited 2026-09-02)

**Fixed in this pass:**
- `POST /tasks/ping` was unauthenticated and enqueued work — 25 anonymous
  requests queued 26 jobs. The demo router is now mounted only when
  `settings.is_local`, so the path does not exist in production.
- The console notification provider logged the OTP **and** the full phone
  number. It now logs `notification dispatched to +9198*****999 (63 chars)`.
- Added composite indexes on the columns every listing filters by.

**Closed in Sprint 20 (2026-09-11):** rate limiting on every class of request
(auth, write, read — per account when signed in, per IP otherwise, fails open);
security headers on the API and the web app (the web CSP is **report-only** and
still allows inline scripts — see `CLAUDE.md`); DPDP consent, export and erasure;
a 256 KB request body cap; `/docs` and `/openapi.json` local-only; CORS without
credentials.

**Still open:**
1. `/health/deep` is public and returns raw exception strings.
2. The web CSP is not yet enforced, and enforcing it strictly needs nonces, which
   need dynamic rendering.

**Verified safe, so do not re-litigate:** SQL injection is not possible — the
raw search query is fully parameterised and `x'; DROP TABLE skills; --` left
the table intact. Cross-user isolation is correct and tested. No tokens reach
the logs. CORS is restricted to one origin.

## 12. Open risks — state these honestly, do not soften

- ~~The work exists in one place.~~ **Re-closed 2026-09-09** — and it had quietly re-opened:
  this line said "Closed 2026-09-07" while Sprints 11–14 sat unpushed. See §10. MongoDB,
  which it named as unbacked, gained encrypted dumps and a passed restore drill in Sprint 20 — but
  **the dumps are still on this laptop**, so a lost laptop loses both copies. Off-machine storage
  has not been scheduled; it was assigned to Sprint 21 and that sprint closed the application loop
  instead.

- Two-sided cold start is unsolved; hybrid supply is a bet, not a solution.
- No revenue model, and free may become the permanent default by inertia.
- Multi-sector dilutes GTM focus — a knowing trade, reversible by narrowing GTM only.
- Recommendation quality is **measured, and not continuously**. Sprint 29 took the set from five
  pairs to **34 pairs, 7 orderings and 16 course expectations**, which is enough to defend a
  weighting — the five never were. Two things still qualify every claim. `make evaluate` **cannot
  run in CI** (it needs the 21,303-standard corpus, which is not in the repository), so the number
  is produced by hand rather than on every change. And **precision has no negative class**: ADR-025
  names click-through, and `EVENT_NAMES` has `course_recommended` and `course_opened` but nothing
  for a recommendation dismissed, so "shown and ignored" and "shown and rejected" are the same rows
  (`docs/scope-reconciliation.md` §3).
- Self-declared skills are unreliable until assessment integration lands. Three of the four
  `SKILL_SOURCES` have no writer at all: every real candidate scores the 0.6 evidence floor, and
  `assessed`/`certified` appear only in seeded fixtures. There is no assessment module or adapter.
- Employer-side supply is the weakest link in Indian vocational markets.
- ~~Two vocabularies coexist.~~ **Closed in Sprint 9.** The 52 curated skills are retired and
  every link points at a National Occupational Standard. What replaced it is a smaller, honest
  debt: the curated→NOS map is hand-authored, so some anchors are judgement calls. The uncertain
  ones are marked in `scripts/legacy_skill_map.py`.
- **The national taxonomy is English-only.** The carried aliases (298 rows as of 2026-09-09) are
  the only Hindi reaching it, covering a few dozen standards out of 21,355. Sprint 23's role search
  narrows the practical damage — a learner types "ward boy" or "ड्राइवर" and the alias map bridges
  to the English role name — but the standards, course titles and role names a provider publishes
  are still English on a Hindi page. Say this plainly.
- ~~4,784 imported skills are unreachable by sector navigation.~~ **Resolved in Sprint 8** — every
  standard states its own sector, so the hierarchy no longer depends on the qualification side.
  They still belong to no current qualification, which is a fact about the corpus, not a defect.
- **7,459 of 21,263 current standards publish no performance criteria at all.** Gap analysis will
  simply have nothing to say about a third of the taxonomy, and no amount of importing fixes it.
- **The source's own arithmetic does not always add up.** In 422 of 23,903 comparable elements the
  criteria marks do not sum to the element total (e.g. 8+6+6=20 against a stated 23). Reproduced
  faithfully rather than corrected — silently "fixing" a national standard would be worse.
- **Only 45 of 21,303 titles are section-numbered course fragments** ("10.1. Case Studies") but
  they are indistinguishable from real units in the schema. Prominence ordering hides them; it
  does not fix them.
- **A quarter of the corpus shares a name.** 1,778 standard names are borne by 4,838 rows, and some
  twins are near-identical reissues differing only by code and level. Sprint 24's search cards name
  the qualification, body and code and flag lookalikes; nothing can make two identically-named
  standards meaningfully distinguishable when the source itself does not distinguish them.
- ~~**Three district names exist in two states each** (Pratapgarh, Hamirpur, Bilaspur) and resolve
  arbitrarily.~~ **Closed 2026-09-23 (Sprint 28).** `PlaceIndex` constrains an ambiguous name to its
  written state and resolves it to nothing when there is no state to choose by. Verified against the
  imported corpus: exactly three names are ambiguous, and zero live rows held a district outside
  their resolved state.

## 13. What it would take to run this for a real customer

Written down on 2026-09-09, re-checked 2026-09-22, so the answer exists before it is asked in a
meeting. **Nothing here
is a defect** — every item is a deliberate stage-appropriate choice, and each one is load-bearing
for a demo precisely because it is absent. But a live pilot needs all of it, and the first three
are hard blockers rather than gaps.

**Blockers — a deployed instance today would let nobody in.**

1. **No SMS provider and no email provider.** `ConsoleNotificationProvider` and
   `ConsoleEmailProvider` both *raise* when `ENVIRONMENT == "production"`, by design (ADR-017):
   a no-op provider would look exactly like working authentication that nobody can complete.
   There is no password anywhere in the product (ADR-038), so an OTP that cannot be delivered is
   an account that cannot be entered. Needs a DLT-registered SMS vendor — DLT applies to SMS and
   not to email, which is why `EmailProvider` is its own port — behind the existing adapters.
2. **No Dockerfile and no deploy target.** `infra/` holds a single `docker-compose.yml` for local
   Postgres, Redis and Mongo. There is no application image, no Terraform (ADR-028 defers it), and
   CI runs lint, typecheck, tests and the web build with nothing to ship them to.
3. ~~MongoDB is backed up by nothing.~~ **Closed in Sprint 20**: encrypted dumps of both
   databases and a passed restore drill (§10a). **What remains is off-machine storage** — the dumps
   are still on this laptop, so a lost laptop loses both copies. Not yet scheduled.

Also closed in Sprint 20, and would have been blockers: consent, export and erasure (DPDP Act
2023), privacy notice / terms / grievance pages — **still drafts pending legal review, and the
grievance officer is not yet named** — rate limiting, and security headers.

**Required before real candidate data, not before a pilot instance.**

4. **The ADR-023 encryption path does not exist.** No `encrypt` anywhere in `api/`. Aadhaar,
   resumes and assessment results are all named by that ADR and none are collected yet, which is
   the only reason this is not already a breach waiting to happen. It must land *before* the first
   feature that collects any of them, not alongside it.
5. **ADR-019 observability is unbuilt.** No OpenTelemetry, no Prometheus, no Grafana; structlog
   and `/health/deep` are the whole story. Adequate for one laptop, not for diagnosing a customer's
   report.
6. ~~**`is_verified` has no writer.**~~ **Closed 2026-09-23 (Sprint 28).** `users.is_staff`,
   `/ops/*` and `make grant-staff` (ADR-042). It is still absent from `OrganisationIn` — no request
   shape can set it, and none can set `is_staff` either. The `/admin` pages landed in Sprint 29. What remains
   for a pilot is a notification when a badge changes, **so a revocation is currently silent**.
7. ~~**No teammate invitations.**~~ **Closed in Sprint 25.** Invitations, roles, the last-owner
   guard and the escalation rule all ship, and the sole-owner data loss this line described is
   refused with a 409 that is now reachable. `admin` and `member` are live roles.

**Would embarrass in a pilot, cheap to fix.**

8. ~~Five of six rich-profile collections are empty.~~ **Closed in Sprint 21** — the seed now
   writes work histories, education, languages, certifications and preferences (21/20/40/20/21/20
   rows as of 2026-09-22).
9. ~~The golden set is five pairs.~~ **34 pairs, 7 orderings and 16 course expectations as of
   Sprint 29.** What remains is that `make evaluate` cannot run in CI — it needs the 21,303-standard
   corpus, which is not in the repository — so the number is real and is produced by hand.
   `tests/test_golden_set.py` guards everything about the set that is checkable without a scorer.
10. The corpus is English-only (§12), in a product whose thesis is Hindi-first. The *interface* is
   fully bilingual, including everything Sprints 23–24 added; the standards themselves are not.
