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
(34 ADRs). Read it before making any structural decision — the summary below
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
  modules/
    identity/            Users, tenants, memberships, OTP sign-in (ADR-009/010/011/032)
    marketplace/         Jobs, courses and their skill links (ADR-001)
    skills/              NSQF taxonomy: Skill/SkillAlias plus the hierarchy above them
                         (Sector → SubSector → Occupation → QualificationPack → QpSkill)
                         in hierarchy.py, and ModelCurriculum (ADR-004, ADR-034)
    matching/            Hybrid scoring engine (ADR-007)
    career_paths/        Graph-based role transition engine (ADR-008)
    intelligence/        LLM extraction/explanation, embeddings (ADR-005/013/018)
  adapters/              External integrations behind interfaces (ADR-017)
    notifications/       NotificationProvider protocol + console impl (the reference)
    nsqf/                NsqfSource port, Mongo and JSON-file sources, shared document
                         parsing, normalisation and the importer (ADR-034)
web/                     Next.js PWA, mobile-first, en + hi (ADR-029, ADR-033)
  src/i18n/              Locale routing and request config
  src/messages/          en.json, hi.json — no user-facing string is hardcoded
  src/lib/api-schema.d.ts  GENERATED from OpenAPI; never edit by hand
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
- **A NOS carries no level of its own.** Level lives on `qualification_packs.nsqf_level` and,
  contextually, on each `qp_skills` row. `skills.nsqf_level` is a derived modal value for display
  only — never score against it.
- **Anything touching the NSQF corpus goes through `api/adapters/nsqf/`.** No module imports a
  MongoDB driver. Document parsing lives in `documents.py` and is shared by every source, so the
  test fixture exercises the real import path rather than a second reader that can drift from it.
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
  not-yet-built pages render `PlaceholderPage` rather than 404.

## Current state

Sprint 6 (NSQF master data) is complete. The national corpus is projected from MongoDB into
Postgres: 43 sectors, 540 sub-sectors, 1,144 occupations, 4,424 qualification packs, 21,303
NOS-derived skills, 27,278 QP→NOS links and 1,950 model curricula. `make import-nsqf` is
idempotent. `/skills` pages server-side and orders by how many qualifications use a unit; a skill
page lists the qualifications containing it, each with its contextual level and elective group.

Four things to respect:
- **The 52 curated skills were kept, not replaced.** They are tagged `source='curated'`, labelled
  as such in the UI, and still own every `job_skills` and `course_skills` link. Two vocabularies
  coexist; that is deliberate debt, recorded in `projectContextForMe.md` §12.
- **The imported corpus is English-only.** The source contains no Devanagari, and the 149 aliases
  attach only to curated skills — so `khoon nikalna` resolves and nothing in the national taxonomy
  does. A real regression against ADR-033, pending the translation job.
- **`skills.qp_count` is denormalised** and maintained by the importer, because the browse orders
  by it and an ORDER BY over a correlated subquery cannot use an index.
- **Elective and optional NOS carry `group_name`.** Flattening them would present "choose one of
  these" as "all of these are required".

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
