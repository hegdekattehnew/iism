# CLAUDE.md

Guidance for Claude Code (and any future contributor) working in this repository.

> **Start a new session by reading [projectContextForMe.md](projectContextForMe.md).** It carries
> session-to-session continuity: what has been built, the local machine's quirks, and the gotchas
> that have already cost time. Update it whenever the shape of the project changes.

## Project

**Intelligent Integrated Skill Marketplace (IISM)** — evolving toward a **Workforce Mobility OS**.

A marketplace connecting skills, jobs, courses, and assessments, with an intelligence layer
that matches candidates to opportunities and recommends career paths. India-first,
multi-sector and taxonomy-first (ADR-024, superseding ADR-015). Hindi and English at
launch (ADR-033).

Full architecture rationale lives in [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md)
(37 ADRs). Read it before making any structural decision — the summary below
is a condensed index, not a replacement.

## Architecture at a glance

- **Layered system** (ADR-001): Marketplace Layer (CRUD, transactions) + Intelligence Layer
  (AI, graph, scoring). Keep these decoupled — the intelligence layer consumes marketplace
  data, it doesn't own it.
- **Modular monolith** (ADR-014): one deployable app, organized into clearly bounded modules
  under `api/modules/`, so it can be split into microservices later without a rewrite. Don't
  let modules reach into each other's internals — go through their public interface.
- **API-first, REST** (ADR-016): no GraphQL for now. Every capability should be reachable via
  a documented REST endpoint, including internal ones consumed by other modules.
- **Event-driven** (ADR-006): async work (matching, scoring, embeddings) goes through workers,
  not inline in request handlers. Redis + ARQ initially (ADR-027 — ARQ, not Celery, because
  the app is async end to end), Kafka is a later migration, not a day-one dependency.
- **Adapter pattern** (ADR-017): every external system (payment providers, assessment
  providers, Aadhaar verification, government systems) sits behind an adapter in
  `api/adapters/`. Business logic never calls a third-party SDK directly.
- **Hybrid AI** (ADR-005, ADR-018): LLMs (external, not self-hosted/custom-trained) for
  extraction and explanation; deterministic logic for actual decisions (matching, scoring).
  Don't let an LLM call be the thing that decides a match score — it should explain a score
  computed deterministically.

## Tech stack (from the ADR — don't substitute without a new ADR)

| Concern | Choice | ADR |
|---|---|---|
| Backend | Python + FastAPI | ADR-002 |
| Database | PostgreSQL + pgvector | ADR-003 |
| NSQF source of record | MongoDB — raw corpus, projected into Postgres, never read at request time | ADR-034 |
| NSQF ingestion policy | Selective: the PII-bearing `ssc` collection is never imported | ADR-035 |
| Embeddings | sentence-transformers, stored in pgvector | ADR-013 |
| Async / queues | Redis + ARQ (→ Kafka later) | ADR-006, ADR-027 |
| Cache | Redis | ADR-020 |
| Search | PostgreSQL full-text search (→ OpenSearch later) | ADR-021 |
| Auth | Centralized identity service, JWT | ADR-009 |
| Identity | UUID primary key; Aadhaar optional verification, not primary ID | ADR-011 |
| Authorization | Permission-based (RBAC now, designed for ABAC) | ADR-012, ADR-022 |
| Multi-tenancy | Global users + tenant + membership model, from day 1 | ADR-010 |
| Observability | OpenTelemetry + Prometheus + Grafana | ADR-019 |
| Skill taxonomy | NSQF-aligned, framework-agnostic | ADR-004 |
| Matching | Hybrid deterministic scoring: skill overlap + semantic similarity + experience | ADR-007 |
| Career paths | Graph-based role transition engine | ADR-008 |

## Repository layout

```
api/                     FastAPI modular monolith
  main.py                App entrypoint, health, demo task endpoints
  core/                  Cross-cutting
    config.py            Settings — ALWAYS via get_settings(), never a module singleton
    database.py          Async engine, Base, get_db_session dependency
    cache.py             Async Redis client
    tasks.py             ARQ worker settings + task registry (ADR-027)
    health.py            Per-dependency health probes
    authorization.py     Permissions resolved from membership role (ADR-039).
                         Ask for a Permission, never a role.
    text.py              slugify, shared by identity and the NSQF importer
  modules/
    identity/            Users, tenants, memberships, OTP sign-in by phone *or* email,
                         credential linking, organisation creation and the organisation
                         profile (ADR-009/010/011/032/038)
    marketplace/         Jobs, courses and their skill links (ADR-001). publishing.py is
                         the employer's write path; everything else there is read-only.
    skills/              NSQF taxonomy. models.py = Skill/SkillAlias (the leaf);
                         hierarchy.py = AwardingBody → Sector → SubSector →
                         Occupation → QualificationPack → QpSkill, plus
                         QpEntryRoute, QpNcoCode, ModelCurriculum;
                         content.py = what a standard actually says, ~614k rows
                         (ADR-004, ADR-034)
    geography/           State, District, SubDistrict, plus the service that resolves a
                         written place name on write. Its own module: jobs and
                         profiles reference it and neither is a skill.
    matching/            Deterministic scoring + gap-closing courses (ADR-007, ADR-036).
                         scoring.py is pure -- no I/O, no clock, no model. employer.py is
                         the same scorer run in reverse for the console (ADR-037).
    analytics/           analytics_events (ADR-025). record() COMMITS.
    career_paths/        Graph-based role transition engine (ADR-008)
    intelligence/        LLM extraction/explanation, embeddings (ADR-005/013/018)
  adapters/              External integrations behind interfaces (ADR-017)
    notifications/       NotificationProvider protocol + console impl (the reference)
    nsqf/                NsqfSource port, Mongo and JSON-file sources, shared document
                         parsing, normalisation and the importer (ADR-034)
web/                     Next.js PWA, mobile-first, en + hi (ADR-029, ADR-033)
  src/i18n/              Locale routing and request config
  src/messages/          en.json, hi.json — no user-facing string is hardcoded
  src/components/ui/     The component library — Radix primitives over this project's tokens
  src/lib/api-schema.d.ts  GENERATED from OpenAPI; never edit by hand
  public/sw.js           Service worker. Its DENY list is a security boundary, not a cache tweak
infra/                   docker-compose (Terraform later — ADR-028)
migrations/              Alembic migrations
tests/                   pytest + testcontainers
docs/adr/                Architecture Decision Records (source of truth for design choices)
```

Each module under `api/modules/` is internally cohesive (its own models, schemas, service
logic, routes) and exposes a narrow public interface via its `__init__.py`. Other modules
import from `api.modules.<name>` only — never from `.service` or `.models` directly. This is
what makes the modular-monolith → microservices path (ADR-014) realistic later.
`api/modules/skills/` is the reference implementation of the pattern; copy its shape.

## Conventions

- Python 3.12, fully type-hinted, async FastAPI routes and async SQLAlchemy sessions.
- **Never bind config at import time.** Use `get_settings()` inside functions; a module-level
  `settings = get_settings()` is unoverridable and silently points the engine at the wrong
  database in tests.
- No business logic in route handlers — routes validate input/auth and delegate to a module's
  service layer.
- Every new external dependency (payment, assessment, verification, government API) gets an
  adapter + interface in `api/adapters/`, never a direct SDK call from a module.
- Secrets and config come from environment variables via `api/core/config.py` (pydantic-settings),
  never hardcoded. See `.env.example` for the expected variables.
- Anything touching Aadhaar data, resumes, or assessment results must go through the
  encryption path described in ADR-023 — don't persist that data in plaintext, including in
  logs.
- New architectural decisions (new datastore, new auth model, new AI approach, etc.) get a new
  ADR entry in `docs/adr/architecture-decisions.md`, not a silent divergence from the existing
  ones.
- **Review every autogenerated migration before applying it.** Indexes created with raw SQL are
  invisible to SQLAlchemy metadata, so autogenerate proposes DROPping them. `migrations/env.py`
  has an `include_object` guard listing them — add to `MANUALLY_MANAGED_INDEXES` whenever you
  create an index with `op.execute()`. Alembic also does **not** diff CHECK constraint bodies:
  widening one is invisible to autogenerate and must be written by hand.
- **NSQF levels are `Numeric(3, 1)`, never integers.** The national corpus uses half-steps —
  2.5, 3.5, 4.5, 5.5, 6.5 — and 4.5 alone covers 6,532 skills. Any level that becomes an `int`
  anywhere in the stack silently excludes 38% of the taxonomy. That includes Pydantic schemas and
  query parameters, not only columns: widening the column and leaving the schema at `int` returned
  500 for every affected row while every existing test kept passing.
- **Output schemas stay permissive; input schemas carry the constraints.** `NsqfLevel` on the way
  out, `NsqfLevelIn` on the way in. A constraint on a response model turns one odd row into a 500
  for the entire response.
- **A NOS carries its own NSQF level — and so does the qualification, and so does the link
  between them.** All three are real and different facts. The source names them inconsistently:
  `nsqf` on a standard, `nsqfLevel` on a qualification. Checking the qualification's spelling
  against standards returns zero, which is how "a NOS has no level" was once wrongly written into
  the schema. **Never conclude a field is absent from one collection using another's spelling** —
  the same trap sits on `type`/`nosType` and `Sectors`/`sectors`.
- **Sector-local identifiers are not global.** An occupation's `code` *and* its `occupationID` are
  both scoped to a sector — `"1"` is a different occupation in each of forty sectors. Key on
  `(sector, ref)`. Assuming the id was global collapsed 1,811 occupations into 529.
- **Anything from the `ssc` collection is off limits.** It is a portal account registry holding
  4,027 emails, 4,042 mobile numbers and 50 bank accounts. Sectors and awarding bodies come from
  the `sectors` collection instead. Nothing in `api/` may read `ssc`.
- Full record of the source data: [docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md).
- **Anything touching the NSQF corpus goes through `api/adapters/nsqf/`.** No module imports a
  MongoDB driver. Document parsing lives in `documents.py` and is shared by every source, so the
  test fixture exercises the real import path rather than a second reader that can drift from it.
- **Derived content keys on `(parent, ordinal)`, never the source's own id.** `pcID` repeats within
  a standard, `kpID` and `skillID` occasionally do. It is deleted and rewritten each import rather
  than upserted, so anything attached to it later (translations, embeddings) needs its own table.
- **Free prose columns are `Text`, never `String(n)`.** Two import runs died on `varchar(512)`;
  occupation names reach 894 characters. Bound only genuine codes and enums.
- **Review every autogenerated migration for unnamed foreign keys.** Alembic emits
  `create_foreign_key(None, ...)`, whose generated downgrade calls `drop_constraint(None, ...)` and
  fails. Twelve appeared across 0011 and 0012.
- **`make check` passing does not mean the import is right.** It passed while `occupations` held
  529 rows instead of 1,811. Compare the import report against independently computed expectations.
- **A model with a cross-module foreign key must import the target module.** SQLAlchemy resolves
  `ForeignKey("districts.id")` against the metadata, so a script importing `marketplace.models`
  without `geography.models` fails at mapper configuration. This bit twice in one sprint —
  marketplace→geography and skills→concepts. Import for the side effect, with a comment saying why.
- **After mutating a relationship, re-query with `populate_existing=True`.** Without it the
  instance already in the session's identity map is returned with its stale collection, so the
  query succeeds and quietly returns the wrong answer. `db.refresh()` does not cascade nested
  eager loads either — see `api/modules/marketplace/profile_service.py::_load`.

## Frontend conventions

- No user-facing string is hardcoded. Everything goes through `next-intl`; both `en.json` and
  `hi.json` must be updated together (ADR-033).
- `src/lib/api-schema.d.ts` is generated — run `make gen-api` after changing any endpoint.
  A breaking backend change should surface as a TypeScript error, not a runtime failure.
- Mobile-first. The target device is a low-end Android on mobile data.
- Server state goes through **TanStack Query**, not hand-rolled `useEffect` + `setState`.
  React 19's `react-hooks/set-state-in-effect` rule treats the hand-rolled form as an error.
  For anything that must keep polling while the tab is hidden (status boards), set
  `refetchIntervalInBackground: true` — TanStack pauses intervals on hidden tabs by default.
- Routes live under `web/src/app/[locale]/`. Every link in the header or footer must resolve;
  not-yet-built pages render `PlaceholderPage` rather than 404 — and it says *drafting*, never
  "coming soon", because a visitor reading "coming soon" discounts everything they just saw.
- Use the primitives in `web/src/components/ui/`. Nothing outside `globals.css` may hardcode a
  colour; every tone must define both its light and its dark value, or it renders invisible in one
  theme.

## Current state

Sprint 13 (multi-tenancy you can see) is done. A signed-in person switches between "Job seeker" and
each of their organisations from the header, creates an organisation without leaving their account,
links a second credential, and edits the organisation's public profile.

- **A personal workspace is not an organisation** (`ORGANISATION_TYPES` in
  `api/core/authorization.py`). Every candidate is `owner` of a personal tenant, so before this
  filter `_context_for` resolved their own personal slug as an org context and `owner` carried
  `JOB_CREATE`, `JOB_PUBLISH` and `CANDIDATE_SHORTLIST` — any candidate could read the employer
  console's aggregate pool and publish a vacancy as "Personal workspace". Verified 200 before, 404
  after; `tests/test_organisations.py` guards it.
- **Membership answers *may this person act here*, not *is this the right kind of organisation*.**
  `require_publisher_of` is the second check: a job needs an `employer`, a course a
  `course_provider`. Nothing enforced this before.
- **The switcher lives in the header, not in a page.** A switcher inside `EmployerWorkspace` could
  not be reached from the one screen that most needs it — its "no access" branch returns first — and
  `/employer/{org}` had no inbound link from anywhere a signed-in person could already be.
- **Context is derived from the URL, never stored.** `useActiveOrg()` reads
  `/employer/{slug}` from the path. Same rule as ADR-038 applies server-side, so the interface can
  never believe a context the API would refuse, and two tabs can be two organisations.
- **Creating an organisation must go through `POST /me/organisations`**, which adds a *membership*.
  The cold `/auth/org/register` path creates a **new `User`** for an unknown address — correct for a
  stranger, and a duplicate account for someone already signed in.
- **`qc.clear()` on sign-out.** The `QueryClient` is created once per browser session, so without it
  the previous person's profile, matches and memberships render to whoever signs in next. Same
  concern as the service worker's DENY list, one layer up.
- **`contact_email` is deliberately absent from `TenantOut`**, which is embedded in every public
  `JobOut` and `CourseOut`. Anything added to that model is published to whatever scrapes `/jobs`;
  `OrganisationOut` is the members-only view.
- **`is_verified` is set by an operator, never the organisation.** It is absent from
  `OrganisationIn`, so no request shape can set it — as are `slug` (a published URL) and
  `tenant_type` (changing it would strand listings already published under it).
- **`api/core/authorization.py` imports identity's models lazily**, inside `_context_for`, because
  `api/modules/identity/` now imports it back for the organisation routes. Same cycle
  `get_current_user` avoids the same way.

Sprint 12 (one identity, many roles) is done. An employer registers by email, posts a vacancy
against real National Occupational Standards, publishes it, and sees ranked candidates — and the
console finally ships to production, because it is behind something.

- **One `User`, many `Membership` rows** (ADR-038). A candidate can create an organisation from
  their existing identity and link a second credential; both organisation paths land in the same
  state. **Never fork an account by actor type** — a person is a candidate *and* a hiring manager,
  and two accounts would split their history permanently.
- **The active tenant is named by the request and granted by the membership**, never carried in the
  token. Switching workspaces must not re-issue tokens, one person may hold two tabs as two
  organisations, and a claim in a 15-minute token outlives a revoked membership.
- **A tenant you are not a member of is a 404, never a 403.** A 403 confirms the organisation
  exists, so an employer could enumerate competitors by guessing slugs. An insufficient *role*
  inside an organisation you do belong to is a 403 — existence is not news to you there.
- **`api/core/authorization.py` is the only authorization primitive** (ADR-039). Ask for a
  `Permission`, never a role. `Membership.role` had been written once and read nowhere for eleven
  sprints; do not add ad-hoc role checks beside this.
- **Organisations sign in by email OTP, not password** (ADR-038, superseding ADR-032's org half).
  There is no password anywhere in the product and no hashing dependency; `hash_secret` is
  HMAC-SHA256 with no work factor and **must not** be repurposed for one.
- **OTP keys carry their channel**: `auth:otp:{channel}:{identifier}`. Without it a phone and an
  email could share a code, an attempt counter and a request budget.
- **Registering a known address sends a sign-in code and creates no second organisation.** The
  earlier "you already have an account" note made the two responses differ by one field whenever
  `expose_otp` was on — a readable enumeration oracle. A test asserts they are indistinguishable.
- **`EmailProvider` is its own port**, not a second method on `NotificationProvider`. Different
  vendors, different compliance (DLT applies to SMS alone). `ConsoleEmailProvider` refuses
  production, like its sibling.
- **`Job.status` defaults to `"published"` in the model**, so `create_job` sets `draft` by hand. A
  create path that forgets puts an unfinished listing in front of candidates; a test guards it.
- **A job with no required standards cannot be published.** Matching scores concept overlap, so it
  would be published and permanently unmatchable.
- **Geography resolves on write**, in `api/modules/geography/service.py`. It used to happen only in
  the NSQF importer's backfill, so an API-created job had a NULL `state_id` and was invisible to
  `match_jobs(state_id=…)` while still appearing at `/jobs`.
- **`Button` defaults to `type="button"`**, inverting the HTML default. The standards picker's Add
  button sat inside the job form and silently saved a half-written vacancy instead of adding a
  standard. Submitting is the special case and every form says so explicitly.
- **next-intl reads a dot as a namespace separator.** `"employment.full_time"` as a flat key renders
  as the literal key; it has to be a nested object.
- **The demonstration console mounts in local environments only** — an allowlist. The previous guard
  compared against `"production"` alone, which mounted an unauthenticated reader of the candidate
  pool on `staging`, on CI, and anywhere `ENVIRONMENT` was unset. `/health` reports whether it is on.

Sprint 11 (make it sellable) is done. There is a component library, the landing page proves the
scale of the corpus from live counts, the employer console ranks candidates for a vacancy, the app
is installable, matches render as a picture rather than a list, and no route says "coming soon".

- **`api/modules/matching/employer.py` is the same scorer with its arguments swapped** (ADR-037).
  `score_match` does not care which side of the pair the query started from. **Do not add a second
  scoring implementation** — two scorers drift, and once they disagree about one pair neither
  number can be defended.
- **The employer console refuses to mount in production.** `mount_employer_console` returns `False`
  outside development, mirroring `ConsoleNotificationProvider`. It is unauthenticated and it reads
  the candidate pool; a test boots the app in both environments and asserts the route is present in
  one and absent in the other.
- **No employer-facing payload identifies a candidate.** Reference, headline, district, years and
  the gap — never a name, phone, email or user id. Nor may an analytics payload carry one.
- **Adding an analytics event needs a hand-written migration.** Alembic does not diff CHECK
  constraint bodies, so a name added to `EVENT_NAMES` alone is accepted by the model and rejected
  by the database — and `record()` swallows its own failures, so the only symptom is events that
  silently never appear. Migration `0015` is the pattern.
- **`web/src/components/ui/` is the component library**, built on Radix primitives and this
  project's own tokens. The shadcn CLI was tried and reverted: it installs a second dark-mode
  mechanism (`.dark` class) beside the `prefers-color-scheme` one already in use, 62 duplicate
  oklch colour tokens, and a font override. Its own docstring records this.
- **`buttonVariants` lives in `button-variants.ts`, which has no `"use client"`.** Exporting a cva
  from a client module breaks prerendering of every server component that styles a button —
  `Attempted to call buttonVariants() from the server`.
- **Charts render `MatchOut` fields and compute nothing.** The moment a picture derives its own
  number it can disagree with the score it claims to explain. The one exception is
  `required − shortfall` in `LevelScale`, which is the scorer's own identity run backwards.
- **The service worker's DENY list is a security boundary, not an optimisation.** `/me/`, `/auth/`,
  `/employer/`, `/matches`, `/profile`, `/signin` and anything carrying an `Authorization` header
  are never cached: a stale match would show a gap already closed, and cached profile data on a
  shared phone is an ADR-023 problem. `tests/test_pwa_assets.py` asserts it.
- **The worker registers in production builds only.** In development it would cache hashed chunks
  that hot reload then replaces. Installability is demonstrated from `npm run build && npm start`.
- **Icons were generated with `qlmanage -t -s 512`**, which honours the SVG's `width`/`height`
  attributes rather than the viewBox — a 64px source renders 64px in the corner of a 512 canvas.
  The sources are square-background SVGs sized 512; the maskable one has no rounded corners,
  because the launcher applies its own mask and a rounded source is cropped twice.
- **Twenty seeded candidates, not five.** Most vacancies now have someone fully eligible beside
  someone missing exactly one mandatory standard, because "who is nearly qualified?" is the first
  question an employer asks and a pool with no near-misses cannot answer it. The original five
  remain first in the list and unchanged — the golden set is asserted against them.

Sprint 10 (matching and the gap) is done. A signed-in candidate opens `/matches` and sees ranked
jobs with a score they can interrogate, the gap named standard by standard, courses that close
that specific gap, and how to become qualified.

- **`api/modules/matching/scoring.py` is pure and must stay that way.** No I/O, no clock, no model
  (ADR-036). A score has to be defensible to an employer and reproducible against the golden set,
  and neither survives a generated number.
- **A missing mandatory standard caps the score at 45, it does not zero it.** A candidate one
  standard short of a strong match needs telling, not hiding.
- **Zero matched standards scores zero**, deliberately. Letting the level and evidence components
  through alone gave every job in the catalogue a small non-zero score for everyone.
- **Matching compares at concept level**, which is the whole reason Sprint 9 built that table.
- **The candidate profile is created lazily, and `/me/matches` creates it too.** It used to 404 for
  anyone who had not opened `/me/profile` first, which the interface renders as its error state —
  so every new candidate arriving at matches first was told something had gone wrong instead of
  being shown the "add your skills" prompt `has_skills` exists for. `ensure_profile` is the single
  creation path and commits its own write, which is what keeps `record()`'s contract intact.
- **`record()` commits.** `get_db_session` never commits, so a merely-flushed event is discarded
  when the request ends — which is exactly what happened the first time this was wired up. Call it
  only from handlers with no other uncommitted work.
- **`make evaluate` runs the golden set.** Expectations are *relative* — "this candidate outranks
  that one" — never absolute scores, or every deliberate weighting change looks like a regression.

Sprint 9 (connect the graph) is done. The national taxonomy is now the operational vocabulary:
every job, course and candidate skill points at a real National Occupational Standard, and the 52
hand-curated Sprint 2 skills are retired.

- **`skill_concepts` groups rows that mean the same thing** — same awarding body + same normalised
  name + same level, giving 18,958 concepts from 21,303 rows. Derived and rebuilt by the importer
  on every run, like `qp_count`. Never edit it by hand. Level and body stay in the key: 576
  duplicate groups span levels and 174 cross bodies, and merging those would assert something
  untrue. Matching will score at concept level so a candidate and a job need not have picked the
  same row.
- **`scripts/legacy_skill_map.py` is the single place the old vocabulary maps to the new.** Job and
  course definitions still read in curated terms because they are legible that way; the map does
  the translation, so all 50 anchors are auditable in one file rather than across 172 literals.
- **The map is many-to-one, and that is the finding.** The curated vocabulary was authored at
  capability level ("hand hygiene", "bed making"); an NOS is a job task ("Follow infection control
  policies & procedures"). 52 slugs collapse to 38 standards. Seeding therefore merges duplicate
  links on the strongest signal — highest importance, mandatory beating optional — because a job
  needing one standard twice is a constraint violation, not two requirements.
- **Retired skills are `source='legacy'`: hidden from search, browse, count and facets, but their
  own page still resolves.** They are not deleted because profiles and certificates reference them,
  and a 404 on a row we deliberately kept would be a broken link of our own making.

Sprint 8 (complete NSQF migration) is done. The national corpus is in Postgres, migrated against
the full master data after the first attempt was rolled back:

```
states 36 | districts 766 | sub_districts 7,100
awarding bodies 106 | sectors 43 | sub_sectors 796 | occupations 1,808
skills 21,303 | qualification_packs 4,424 | qp_skills 27,278 | model_curricula 1,950
entry_routes 14,405 | nco_codes 2,541
performance elements 38,340 | criteria 238,370 | knowledge 185,559 | generic 151,840
```

`make import-nsqf` takes ~90 seconds and is idempotent. Things to respect:

- **The owning body comes from the code prefix.** `LSC` owns `LSC/Q6101`. That resolves 97% of
  qualifications and 99.8% of standards; the source's own `originSSC` field reaches 9%. Sector
  Skill Councils and awarding bodies share `awarding_bodies` because the source does.
- **`api/modules/geography/` is its own module**, not part of `skills` — jobs and profiles
  reference it and neither is a skill. A district is tied to a state *only* by the array embedded
  in each state document; the standalone collection has no state field at all.
- **Location FKs sit beside the free text, not instead of it.** Not every value resolves, and an
  unresolvable location is still a location. `Bengaluru` → `BENGALURU URBAN` via an alias map,
  because "Bengaluru" is what an employer would actually write.
- **Content tables key on `(parent, ordinal)`, never the source's id.** `pcID` repeats within a
  unit, so a natural key on it fails partway through an import.
- **Content is deleted and rewritten each run, not upserted.** A revised standard with fewer
  criteria must not leave the surplus behind.
- **7,459 of 21,263 current standards have no performance criteria** in their latest version.
  That is the data, not a bug — the import writes every row the current versions hold.
- **The 52 curated skills remain** alongside the 21,303 imported ones, tagged `source='curated'`.
  Two vocabularies still coexist; that debt is recorded in `projectContextForMe.md` §12.
- **Still English-only.** The corpus carries no Devanagari; the 149 carried aliases are the only
  Hindi reaching it.

Sprint 5 (rich candidate profile) is complete. `CandidateProfile` gained personal fields and job
preferences, plus six repeating collections: experiences, educations, certifications, languages,
preferred roles and preferred locations. `/profile` is a guided 5-step wizard on first visit and
a sectioned editor thereafter, with a weighted completeness meter.

Two things to respect:
- **The six collections share one generic route and one generic editor.** `/me/profile/{collection}`
  takes an untyped body, which means FastAPI's automatic 422 does **not** apply — the handler
  translates `ValidationError` itself. Adding a section is an entry in `CHILD_MODELS`, `_PAYLOADS`
  and `useSectionDefs`, not a new module.
- **`/me/profile/skills` is declared before `/me/profile/{collection}`** or the literal path gets
  captured as a collection name. There is a test guarding it.

Sprint 4 (identity + candidate profile) is complete. `identity` holds `User`, `Tenant` and
`Membership` with passwordless phone/OTP sign-in; `marketplace` gained `CandidateProfile` and
`CandidateSkill`. `/signin` and `/profile` are live in both locales, and the header reflects
signed-in state.

Non-obvious things that will bite:
- **`get_settings()` refuses to start outside development/test** if `JWT_SECRET_KEY` is the
  default or under 32 bytes, or if `OTP_EXPOSE_IN_RESPONSE` is on. That is deliberate.
- **OTP codes are stored hashed** in Redis, rate limited per phone, and capped at 5 guesses.
- **Phone numbers are normalised** to `+91XXXXXXXXXX` before any lookup — `9876543210`,
  `09876543210` and `+91 98765 43210` must resolve to one account, not three.
- **`candidate_skills.source` is always `self_declared` when a user adds a skill.** Only an
  assessment or certificate may set a stronger source; that ordering is what makes verified
  evidence outrank self-claims in Sprint 5's scoring.
- **`api/adapters/notifications/` is the ADR-017 reference implementation.** The console
  provider refuses to run in production, so a missing SMS vendor fails loudly rather than
  looking like working auth that nobody can complete.

Sprint 3 (marketplace) is complete. `marketplace` holds `Job` + `JobSkill` and `Course` +
`CourseSkill`; `identity` holds `Tenant` (models only — no auth yet). Seeded with 8 tenants,
20 jobs and 20 courses, all bilingual and linked to real skill slugs. `/jobs` and `/courses`
are live with filters and detail pages, and `/skills/[slug]` shows the jobs needing a skill
and the courses teaching it.

Two things to respect here:
- **The association tables carry the intelligence.** `JobSkill.importance` / `is_mandatory` and
  `CourseSkill.level_taught` are what make a weighted score and an honest skill gap possible.
  A plain many-to-many would not be enough.
- **`scripts/seed_marketplace.py` fails loudly on an unknown skill slug.** A job with no skills
  is invisible to matching, and that failure would not otherwise surface until Sprint 5.

Sprint 2 (skill taxonomy) is complete. `skills` holds `Skill` and `SkillAlias`, seeded with 52
bilingual skills and 149 aliases across Healthcare, Retail and cross-sector core skills.
Search resolves English, Devanagari and Latin-script transliteration in one query, with a
trigram fallback for typos. `/skills` and `/skills/[slug]` are live in both locales.

Two things to respect when extending the taxonomy:
- `Skill.search_vector` is `GENERATED ALWAYS` in Postgres and declared with SQLAlchemy
  `Computed(...)`. Without `Computed` the ORM puts it in INSERT and Postgres rejects the write.
- `scripts/seed_skills.py` is idempotent by slug and replaces aliases wholesale. The real NSQF
  importer must behave the same way, because Qualification Packs get revised and re-issued.

Sprint 1 (walking skeleton) is complete: Docker Compose, async FastAPI, Alembic with pgvector
enabled, an ARQ worker with heartbeat-based health reporting, a bilingual Next.js PWA, a
generated TypeScript client, testcontainers-backed tests and CI. The visible deliverable is the
System Status page at `/en` and `/hi`.

The public homepage template is also in place: header with nav and CTAs, hero with search,
how-it-works, audience cards, browse panels, CTA band, footer, and the dev/status panel last.
All 13 routes exist in both locales; content is placeholder where the feature is not built.

Still to come: matching (Sprint 6) — which needs analytics instrumentation and a golden-set
evaluation harness alongside it. Also outstanding: organisation/email login and self-serve
publishing, a real SMS provider, the NSQF hierarchy above Skill (SSC → Sector → Occupation → QP → NOS), typed
SkillRelation edges, embeddings, and analytics instrumentation. Do not assume every module listed
above ships in v1; confirm scope before building out a module's business logic.

## Local development

See [README.md](README.md) for setup (Docker Compose for Postgres/Redis, running the app,
running tests).
