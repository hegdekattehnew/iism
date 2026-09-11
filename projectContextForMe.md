# Project context — read this first

Working notes for Claude Code. Purpose: recover full context on a new session without
re-reading the codebase or the conversation history. Update it at the end of any session
that changes the shape of the project.

**Last updated:** 2026-09-09 · Sprints 1–15 built. Sprint 15 was consolidation: no new product
surface, four unpushed sprints pushed, the documents made to agree with the code.

> Every count in this file is dated. An undated number in a document that survives fifteen
> sprints is a number nobody can trust and nobody can check — the header above claimed
> "Sprints 1–5" through nine further sprints, which is how §10 came to assert the branch was
> pushed while four sprints sat on one laptop.

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
| `docs/adr/architecture-decisions.md` | **39 ADRs — the source of truth for every design decision.** Read before any structural change. |
| `docs/IISM-Product-Definition.docx` | 20-page product definition: problem, actors, intelligence layer, scope, risks, decision appendix. Written for the founding team, deliberately candid. |
| `CLAUDE.md` | Working conventions, repo layout, current state. Auto-loaded each session. |
| `README.md` | Setup and run instructions. |
| `~/.claude/plans/i-want-to-create-lively-phoenix.md` | **The sprint plan, 1–8.** Sprint 7 is marked superseded but still holds the translation-pipeline design. Lives outside the repo. |
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

```
api/                    FastAPI modular monolith
  main.py               app, health, demo task endpoints
  core/                 config, database, cache, tasks (ARQ), health
  modules/skills/       models.py     Skill, SkillAlias (the leaf)
                        hierarchy.py  AwardingBody, Sector, SubSector, Occupation,
                                      QualificationPack, QpSkill, QpEntryRoute,
                                      QpNcoCode, ModelCurriculum
                        content.py    PerformanceElement, PerformanceCriterion,
                                      KnowledgeParameter, GenericCriterion (~614k rows)
                        concepts.py   SkillConcept -- rows that mean the same thing
                        + schemas, service, routes, __init__ (public interface)
  modules/matching/     scoring.py (pure), service.py (retrieval + gap + courses),
                        schemas, routes. No model client, by ADR-036.
  modules/analytics/    analytics_events (ADR-025). record() commits.
  modules/geography/    State, District, SubDistrict. Its own module because jobs
                        and profiles reference it and neither is a skill. No routes
                        yet -- nothing consumes it over HTTP.
  modules/marketplace/  Job, JobSkill, Course, CourseSkill + browse/detail endpoints
  modules/identity/     User, Tenant, Membership, OTP sign-in, JWT
  core/security.py      tokens, OTP hashing, rate limits, get_current_user
  adapters/notifications/  NotificationProvider protocol + console impl
  adapters/nsqf/        base.py       NsqfSource port (6 iterators)
                        documents.py  ALL document parsing, shared by every source
                        mongo.py / jsonfile.py  the two sources
                        normalise.py  levels, HH:MM, credits, slugs, NCO codes
                        importer.py   phased projection into Postgres
web/                    Next.js 16 PWA
  src/app/[locale]/     13 routes, all bilingual
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
                        0014 (analytics events)
scripts/                seed_skills.py, seed_marketplace.py, import_nsqf.py,
                        legacy_skill_map.py (hand-authored, the only curated->NOS map),
                        retire_legacy_skills.py, seed_candidates.py (demo profiles +
                        the golden pairs), evaluate_matching.py — all idempotent
tests/fixtures/         nsqf_sample.json — the corpus in miniature, so tests need no Mongo
backups/                schema.sql (committed DDL) + README.md (the three restore paths).
                        *.sql.gz dumps are git-ignored: 40 MB and regenerable.
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
make db-dump     # full backup, ~40 MB gzipped, ~8s
make db-restore DUMP=backups/iism-....sql.gz   # ~5s, DROPS and recreates the db
make db-schema   # refresh backups/schema.sql (DDL only, committed)
make import-nsqf # project the NSQF corpus from Mongo into Postgres (idempotent)
make api         # uvicorn on :8000
make worker      # ARQ worker
make web         # Next.js on :3000
make check       # ruff + mypy + pytest  <- run before claiming anything works
make gen-api     # regenerate the TS client after ANY endpoint change
```

Three processes must run for the full stack: **api, worker, web.**

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

**Pushed 2026-09-09**, at the start of Sprint 15 and before anything else in it.

This section was wrong in the most expensive possible way, and the shape of the mistake is worth
keeping. It said "Pushed 2026-09-07 … that risk is closed", because the last commit to actually
reach the remote was one called *"Correct the git section: the branch is pushed"*. Sprints 11, 12,
13 and 14 — five commits and several thousand lines — then accumulated locally while the document
went on asserting they were safe. **A claim about the remote is only true at the moment it is
checked**; re-check it, do not read it here.

- Branch **`v2/foundations`**, tracking `origin/v2/foundations`.
- Verified with `git log origin/v2/foundations..HEAD`, which must be **empty**. Comparing the
  branch tip against the document is what failed for four sprints.
- **No pull request is open yet.** `gh` is not installed on this machine, so the PR has to be
  opened in the browser:
  `https://github.com/hegdekattehnew/iism/compare/main...v2/foundations`
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

- **A crashed container loses nothing** — the data is in the `pgdata` volume. Deleting the volume
  is what loses it.
- `make db-dump` writes ~40 MB gzipped in about eight seconds; `make db-restore DUMP=...` brings
  it back in about five. **Verified** by restoring into a scratch database and comparing row
  counts, extensions, indexes and the `GENERATED` tsvector table by table.
- Dumps are **git-ignored**. `backups/schema.sql` (61 KB DDL) is committed and refreshed with
  `make db-schema`.
- **716,187 of 716,257 rows are derived** and rebuild from MongoDB with `make import-nsqf && make
  seed`. Only **70 rows are irreplaceable** — users, profiles, analytics events. That ratio is why
  rebuilding from source is the honest default today, and why it stops being sufficient the moment
  real users arrive.
- **MongoDB is covered by none of this.** It is the source of record for the corpus (ADR-034), and
  if it is lost the taxonomy cannot be rebuilt from anything in this repository.

## 11. What comes next

Matching works, is measured, and is now visible from both sides. What is missing is mostly
**evidence and reach**, not mechanism.

**Confirm the PWA installs on a real device.** The manifest, icons and service worker are in place
and tested for existence and correctness, but the in-app browser pane will not register a worker,
so nothing has yet proved Chrome offers "Install". One phone, five minutes — and until it is done,
say "installable" with that caveat rather than as a fact.

**Tune against the golden set, and grow it.** Five labelled pairs is enough to catch a regression
and nowhere near enough to trust a weighting. The plan called for 50–100. Growing it is the
cheapest way to make every later scoring change safe.

**Semantic similarity** is the deliberate omission from Sprint 10 (ADR-007 names it; ADR-036 says
deterministic overlap ships first so there is a baseline). Embeddings over performance criteria
rather than titles — titles like `OJT` and `Project` embed to noise — with sentence-transformers
self-hosted, so no per-request cost.

**Hindi for the corpus** (Sprint 13): ~$5 for the navigable surface, blocked on credentials rather
than design. Worth stating plainly in any demo: the interface is fully bilingual today, the *corpus*
is not — standard names and descriptions are still English.

**Teammate invitations.** One owner per organisation today. The model already allows many
memberships per tenant, so this is an invitation token, an email and an acceptance path — no
restructuring, which is exactly why the context model was built for many memberships from the start.

**Course-provider self-serve publishing**, on the same rails as jobs. `publishing.py` and the
authorization dependency generalise; `Course` has no geography, which is the only real difference.

**The parked résumé builder and extractor**, deferred because correct Devanagari in PDF needs
complex-script shaping and therefore Pango/HarfBuzz. Still the best answer to profile-completion
friction, which is now the binding constraint on matching: a candidate with no declared skills
gets no matches, correctly, and nothing yet makes declaring them easy.

Also outstanding: career paths (ADR-008, and the NCO codes for it now exist), typed `SkillRelation`
edges, organisation/email login and self-serve publishing, a real SMS provider, observability, and
the ADR-023 encryption path.

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

**Still open, in rough priority order:**
1. **No rate limiting outside the OTP path.** `/skills/search` runs a 4-way
   UNION with trigram matching, completely unthrottled.
2. **No security headers** — no HSTS, CSP, X-Frame-Options, X-Content-Type-
   Options. Missing CSP matters more than usual because tokens sit in
   `localStorage`, so any XSS is full account takeover.
3. **No DPDP erasure or export endpoints.** Zero routes for deletion, export or
   consent. Legally required in the target market.
4. `/health/deep` is public and returns raw exception strings.
5. No request body size limit; a 3 MB body is parsed before rejection.

**Verified safe, so do not re-litigate:** SQL injection is not possible — the
raw search query is fully parameterised and `x'; DROP TABLE skills; --` left
the table intact. Cross-user isolation is correct and tested. No tokens reach
the logs. CORS is restricted to one origin.

## 12. Open risks — state these honestly, do not soften

- ~~The work exists in one place.~~ **Re-closed 2026-09-09** — and it had quietly re-opened:
  this line said "Closed 2026-09-07" while Sprints 11–14 sat unpushed. See §10. What
  remains is that **MongoDB is backed up by nothing**: it is the source of record for the corpus
  (ADR-034), it lives only in a local Docker volume, and if it is lost the taxonomy cannot be
  rebuilt from anything in this repository or on GitHub.

- Two-sided cold start is unsolved; hybrid supply is a bet, not a solution.
- No revenue model, and free may become the permanent default by inertia.
- Multi-sector dilutes GTM focus — a knowing trade, reversible by narrowing GTM only.
- Recommendation quality is **unproven and unmeasured**. Every claim about it is a hypothesis
  until the golden-set harness exists.
- Self-declared skills are unreliable until assessment integration lands.
- Employer-side supply is the weakest link in Indian vocational markets.
- ~~Two vocabularies coexist.~~ **Closed in Sprint 9.** The 52 curated skills are retired and
  every link points at a National Occupational Standard. What replaced it is a smaller, honest
  debt: the curated→NOS map is hand-authored, so some anchors are judgement calls. The uncertain
  ones are marked in `scripts/legacy_skill_map.py`.
- **The national taxonomy is English-only.** The carried aliases (298 rows as of 2026-09-09)
  are the only Hindi reaching it, covering a few dozen standards out of 21,355. Say this
  plainly.
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

## 13. What it would take to run this for a real customer

Written down on 2026-09-09 so the answer exists before it is asked in a meeting. **Nothing here
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
3. **MongoDB is backed up by nothing** (§12). Postgres has `make db-dump`/`db-restore`, verified.
   Mongo is the source of record for the corpus and lives only in a local Docker volume.

**Required before real candidate data, not before a pilot instance.**

4. **The ADR-023 encryption path does not exist.** No `encrypt` anywhere in `api/`. Aadhaar,
   resumes and assessment results are all named by that ADR and none are collected yet, which is
   the only reason this is not already a breach waiting to happen. It must land *before* the first
   feature that collects any of them, not alongside it.
5. **ADR-019 observability is unbuilt.** No OpenTelemetry, no Prometheus, no Grafana; structlog
   and `/health/deep` are the whole story. Adequate for one laptop, not for diagnosing a customer's
   report.
6. **`is_verified` has no writer.** Deliberate — it is an operator decision and absent from
   `OrganisationIn` so no request shape can set it — but "deliberate seam" and "shipped feature"
   are different things, and a marketplace whose verified badge nobody can grant has no verified
   organisations.
7. **No teammate invitations.** `Membership.role` supports owner/admin/member and the permission
   model reads it (ADR-039), but the only way to gain a membership is to create the organisation.
   One person per organisation, in a product about organisations.

**Would embarrass in a pilot, cheap to fix.**

8. Five of six rich-profile collections are empty (§4) — no seeded candidate has a work history.
9. The golden set is five pairs. Every claim about match quality rests on them (§12).
10. The corpus is English-only (§12), in a product whose thesis is Hindi-first.
