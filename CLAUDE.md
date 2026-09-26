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
launch (ADR-033); further languages are rows rather than a migration (ADR-041).

Full architecture rationale lives in [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md)
(42 ADRs). Read it before making any structural decision — the summary below
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
| Logging | Structured JSON to stdout, one shared processor tail | ADR-040 |
| Observability | OpenTelemetry + Prometheus + Grafana — **deferred, not built** | ADR-019, ADR-040 |
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
    logging.py           configure_logging(): one JSON stream for structlog and
                         stdlib alike (ADR-040). Call once per process.
    localisation.py      content_translations + locale negotiation (ADR-041). The
                         API resolves language; the client never picks.
    redaction.py         The ADR-023 filter. Runs in the shared tail, so no
                         logger in the process can route around it.
    middleware.py        Pure ASGI request context: request_id, the access log.
    text.py              slugify, shared by identity and the NSQF importer
  modules/
    identity/            Users, tenants, memberships, invitations. OTP sign-in by phone *or*
                         email, credential linking, organisation creation and the organisation
                         profile (ADR-009/010/011/032/038). invitations.py holds the three
                         rules about teams -- escalation, the last owner, enumeration-safety --
                         each in one function. member_routes.py has two routers, because
                         somebody accepting an invitation is not yet a member. ServiceAccount
                         (Sprint 33) is a fourth credential, alongside JWT rather than under
                         it -- an external system is not a `User` and never signs in.
    marketplace/         Jobs, courses and their skill links (ADR-001). publishing.py is
                         the employer's write path and course_publishing.py the provider's;
                         they are siblings, not one generalisation (ADR-026).
                         listings.py is what they *do* share: which standards exist,
                         the refusal of retired ones, slug uniqueness, eager loading.
                         partner_routes.py (Sprint 33) is the external-system actor's one
                         endpoint, gated by `core.security.get_service_account` rather than
                         `require()` -- same `service.list_jobs` the public listing calls,
                         because a partner is not owed a second query path.
    skills/              NSQF taxonomy. models.py = Skill/SkillAlias (the leaf);
                         hierarchy.py = AwardingBody → Sector → SubSector →
                         Occupation → QualificationPack → QpSkill, plus
                         QpEntryRoute, QpNcoCode, ModelCurriculum;
                         content.py = what a standard actually says, ~614k rows
                         (ADR-004, ADR-034). roles_routes.py + role_aliases.py =
                         role search: a job title to its qualification's standards
    geography/           State, District, SubDistrict, plus the service that resolves a
                         written place name on write. Its own module: jobs and
                         profiles reference it and neither is a skill.
    matching/            Deterministic scoring + gap-closing courses (ADR-007, ADR-036).
                         scoring.py is pure -- no I/O, no clock, no model, and (Sprint 33)
                         no settings read either: ScoreWeights is a value passed in, built
                         from configuration by service.py's weights_from_settings(), never
                         read inside the scorer itself. employer.py is the same scorer run
                         in reverse for the console (ADR-037), and (Sprint 33) also holds
                         market_scarce_skills -- the same scarcity query with no tenant
                         filter, for a course provider asking what the whole market needs.
                         provider_routes.py (Sprint 33) is course_role_alignment --
                         a course measured against a role, with no candidate in the
                         comparison at all, so ADR-037 does not apply the way it does
                         to candidates_for_job -- and market_router, the provider-facing
                         read of market_scarce_skills.
    applications/        Applying, withdrawing, saving a vacancy, and the employer's
                         inbox. Holds the product's **one deliberate disclosure**:
                         a candidate's contact reaches an employer because they
                         applied, and goes when they withdraw. Depends on
                         marketplace and matching; nothing depends on it.
    interests/           Registering interest in a course, and the provider's
                         view of who did. A **sibling** of applications/, not an
                         extension: a course publishes what it teaches, so an
                         interested learner cannot be scored, and a shared
                         abstraction would need the second scorer ADR-037 forbids.
    notifications/       The outbox (ADR-006): queued inside the request, sent by the
                         worker. The row names a recipient and never holds an
                         address -- that is resolved at send time.
    alerts/              Telling a candidate about a vacancy they did not go
                         looking for, and closing one whose date has passed.
                         Both run in the **worker**, never in a request. Uses
                         the one scorer through `matching.candidates_for_job`
                         (ADR-037) -- there is no second, looser "close enough
                         to email about" rule. Nothing depends on it.
    privacy/             DPDP export, deletion preview and erasure (ADR-023 adjacent).
                         Spans every module; nothing depends on it.
    operations/          The back office (ADR-042): tenant_verification_events, the
                         verification queue and decision routes, `require_operator()`'s
                         permissions, and (Sprint 33) the government-agency programme
                         report -- an operator stands in for an agency login that does
                         not exist yet. A second leaf beside privacy/ -- depends on
                         identity, marketplace and, since Sprint 33, matching (for the
                         report's serious-match count) -- nothing depends on it. No
                         staff-management endpoint, ever, by decision;
                         `scripts/grant_staff.py` is the only writer of `users.is_staff`.
    analytics/           analytics_events (ADR-025). record() COMMITS. course_dismissed
                         (Sprint 33) is course_opened's negative half -- precision@5's
                         missing class, same shape, its own handler for the same reason.

    Not built. ADR-008's career_paths/ (graph-based role transition) and
    ADR-005/013/018's intelligence/ (LLM extraction, embeddings) have an ADR
    each and no code. They were listed here as though they existed until
    Sprint 15. Everything else in this tree is real; check before assuming.

  adapters/              External integrations behind interfaces (ADR-017)
    notifications/       NotificationProvider protocol + console impl (the reference)
    nsqf/                NsqfSource port, Mongo and JSON-file sources, shared document
                         parsing, normalisation and the importer (ADR-034)
    payments/            PaymentProvider port (Sprint 34, ADR-043). Its console impl
                         refuses unconditionally, not only in production -- there is no
                         course-checkout feature calling it yet, so succeeding would
                         fabricate a transaction for a flow that does not exist.
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
  database in tests. **`api/main.py` is the single exception, and the only one admissible**: the
  app object is assembled once per process and cannot be built without a title, an allowed origin
  and an environment. What makes it safe is not that it is unavoidable but that it is *tested* —
  `tests/test_security_hardening.py` boots a fresh subprocess per `ENVIRONMENT` and reads the
  resulting route table, which is how a guard on the app's own assembly has to be tested. A second
  module-level binding without that is the thing this rule forbids.
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
- **"No business logic in route handlers" is enforced, not asserted.**
  `tests/test_route_delegation.py` parses every route module and fails when a handler -- or a
  helper inside a route module -- calls `db.*`, `select()` or `record()`. Audited 2026-09-24 at
  **17 violations in 107 handlers**; Sprint 32 moved all of them and the guard keeps the number at
  zero. It asserts it **found** modules and handlers before asserting anything about them, and a
  second test feeds the detector a known-bad snippet, because a matcher that matches nothing
  reports a clean route layer for ever.
- **The fix for an analytics call in a handler is to move it into the service, never to delete the
  ordering.** `record()` **commits**, so it must run *after* the business commit and outside it:
  calling it with uncommitted work pending commits that work as a side effect, and a failure inside
  it rolls the work back and returns silently, because `record()` never raises. Fifteen of the
  seventeen violations were handlers reasoning correctly about exactly this. Each service function
  now commits and then records, with the reason written beside it — see
  `invitations._record_for_tenant` and `publishing._record_for_job`.
- **A service that measures an act must be the function that is only ever that act.**
  `matches_for` wraps `match_jobs` rather than recording inside it, because `match_jobs` is also
  called by the golden-set harness and the alert sweep — recording there would count a nightly cron
  as somebody viewing their matches. Same for `console_ranking` over `rank_candidates` (the alert
  sweep reaches it through `candidates_for_job`) and `standards_for_role_viewed` over
  `standards_for_role`.
- **Moving a record into its single writer can close a measurement gap, and did.** `member_removed`
  was recorded by the handler an owner uses to remove a colleague; `POST /leave` reaches the same
  service function through a different handler, so **every self-departure was invisible**. It now
  records one, with `{"self": true}` in the payload to keep the two apart — the `job_closed`
  / `automatic` move, and `accept()`'s lesson one table over.
- **The feature crons live in `api/worker.py`, not `api/core/tasks.py`, and that split is a trap.**
  Core registers the heartbeat alone because it must not import a feature module (ADR-014). So
  pointing the Makefile at `api.core.tasks.WorkerSettings` yields a worker that starts cleanly,
  answers the health probe, and silently runs **none** of `drain_notifications`, `send_job_alerts`
  or `close_expired_jobs` — no notification is ever sent, no candidate is alerted, and a closing
  date never closes anything. Nothing asserted this until `tests/test_worker_schedule.py`, which
  names what stops running when a cron goes missing.
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
- **The exception is a closed set the database itself enforces**, and only while a test says the
  two agree. Fifteen `Literal` unions sit on output models because a permissive `str` would leave
  the generated TypeScript client typing every status as `string`. Alembic does not diff CHECK
  bodies, so a widened constraint is invisible both to autogenerate and to the schema beside it;
  `tests/test_enumerations.py` compares each union against the constraint on its column and fails
  on a union with no CHECK at all. Writing it found two — `education_level` and
  `preferred_employment_type` — closed set in the schema, open column in the database (0017).
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
- **A district name is not unique, and `.limit(1)` with no ORDER BY is how that becomes a wrong
  answer.** Three names in the NSQF master belong to two districts each — Bilaspur (Chhattisgarh /
  Himachal Pradesh), Hamirpur (Himachal / Uttar Pradesh), Pratapgarh (Rajasthan / Uttar Pradesh) —
  and `resolve_location` looked one up by name alone while computing, and ignoring, the state
  beside it. `matching._locality` compares ids and nothing else, so a Himachal vacancy scored 2,
  "in your district", for somebody in Chhattisgarh. **`PlaceIndex` in
  `api/modules/geography/service.py` is the one rule**: a resolved state constrains the district, an
  unconstrained ambiguous name resolves to **nothing**, and the alias is applied *inside* the state
  filter so it cannot reach across a border either. **No id is better than a wrong one** — the free
  text sits beside the key and still reads correctly, while a wrong id is a factual claim the data
  does not support. `("Karnataka", "Pune")` therefore resolves the state and not the district: a
  contradiction is not a Pune.
- **A backfill must test whether anything changed, not whether anything resolved.**
  `_backfill_geography`'s only guard asked "did either half resolve", so every `make import-nsqf`
  rewrote every job and profile with identical ids — and `updated_at` is an `onupdate` column, so
  the whole catalogue looked freshly edited after a read-only operation. It reports `(resolved,
  updated)` now, and the second number is the only way to see the fix hold: two consecutive imports
  give `updated=20` then `updated=0`, with digests over `(id, state_id, district_id, updated_at)`
  identical.
- **`scripts/seed_candidates.py` resolves geography too, and did not until Sprint 28.** Sprint 15
  taught this to `seed_marketplace.py` and stopped there, so all twenty seeded preferred locations
  carried NULL on both foreign keys — and `candidate_facts` reads exactly those two columns, which
  means half of Sprint 23's locality tie-break had **no input at all**. The same probe proves it:
  clear the twenty and run the seed alone — 20 unresolved before, 0 after.
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
- **`Card` is the border; `CardBody` is the padding.** A `<Card>` with children and no `<CardBody>`
  renders its text flush against the border. Sprint 11 rebound the name — the old padded `Card`
  became `Panel` and `ui/card.tsx`'s unpadded one took the name — without migrating the call sites,
  so `BrowsePanels` and `Audiences` sat unpadded on the **homepage** for four sprints. Nothing
  caught it: the import still resolved, tsc passed, the build passed, and no test renders a page.
  **A rename that keeps compiling is the kind that ships.**
- **In a card grid, one element must take `flex-1`.** Cards stretch to the row height, so without it
  a two-line description leaves that card's button floating mid-card while its neighbours' sit
  lower — the row reads as crooked even though every box is identical.
- **`divide-y` does not work in this build.** `divide-border-token` resolves the *colour* and emits
  no border *width* — computed `borderTopWidth` was `0px` on every row of `RoleChooser`, so the
  list rendered as one undivided block while the class string looked correct in the markup. Use
  `border-t border-border-token first:border-t-0` on the children instead.
- **A two-column hero track must be `minmax(0,1fr)`, never `1fr`.** A `1fr` track has
  `min-width:auto`, so the hero's search row — a `w-full flex-1` input beside an unshrinkable
  `size="lg"` submit — can force the track past the container. The hero section carries
  `overflow-hidden`, so the overflow produces **no scrollbar and no error**: the right-hand column
  silently disappears at some widths.
- **The hero has a fold budget, and Hindi is the binding case.** `globals.css` sets
  `html[lang="hi"] body { line-height: 1.7 }`, so Devanagari runs ~15% taller than the same copy in
  English. Before Sprint 16 the hero's Search button sat below the fold at 360×640 in Hindi while
  passing in English. Measure `getBoundingClientRect().bottom` of the submit button on `/hi` at
  360×640 before adding anything above it.
- **`backdrop-filter` on an ancestor is a containing block for `position: fixed`.** `Header` has
  `backdrop-blur`, so the create-organisation dialog's `fixed inset-0` resolved to the header's box
  — measured at **1280×64 against a 1280×800 window**, clamped into the strip at the top of the
  page. No `z-index` or offset would have helped. **Anything modal goes through
  `ui/dialog.tsx`**, which portals to the body and brings the focus trap, Escape and scroll lock
  the hand-rolled overlay never had. `Dialog` is deliberately **not** re-exported from
  `ui/index.ts`: almost everything imports that barrel for a Button, and Radix's dialog is ~33 KB
  of the first-load budget.
- **`globals.css` is the only file that may name a colour**, and `web/src/lib/tokens.test.ts` now
  enforces it. The rule had been stated since Sprint 11 and broken **305 times across 38 files**;
  every one of those re-derived its own light/dark pair by hand. Use the semantic tones —
  `--success-*`, `--warning-*`, `--danger-*`, `--info-*`, each carrying surface, border and text —
  and `Alert`/`Badge` rather than a new class string. The test caught one straggler in
  `button-variants.ts` the migration missed, because that file is `.ts` and the sweep was `.tsx`.
- **The Devanagari webfont is scoped to `html[lang="hi"]`, and that is not cosmetic.** **Noto Sans
  Devanagari ships three subsets, one of which is Latin**, so merely naming it in `body`'s stack had
  English pages fetching ~80 KB of it. Measured against a production build: an English page requests
  **one** font file (47 KB), a Hindi page **two** (166 KB). `LocaleSwitcher` uses `font-system` for
  the same reason — one `हिंदी` in a dropdown was enough to pull the whole face onto every page.
- **A control that lists what an account owns has to survive the account that owns a lot.** The
  context switcher rendered every organisation with no bound: measured at ten, **656px of a 720px
  laptop screen**, and on the 360x640 phone the open mobile nav came to **1311px — more than twice
  the screen**, with "Create an organisation" below all of it. Sprint 26 deliberately refused to cap
  how many organisations one account may hold, so the *control* has to cope. The shape that works:
  **the list scrolls inside a bounded box, the things that must never be pushed away sit outside
  it**, a filter appears once there are enough to be worth filtering, and the order is current →
  recently used → alphabetical. It had **no test file at all**, which is how it got there.
- **401 and 403 are opposite answers, and a panel must not collapse them.** 403 is "this is not
  yours" and the right response is silence — a control that always fails is worse than none.
  **401 is "you are signed out"**, which is not a permission problem and has to say so. Every
  organisation screen used to render "no access", or nothing at all, for both: an owner following
  written instructions to delete their own organisation found the control simply absent, because a
  fifteen-minute token had expired. Use `isSignedOut()` from `lib/http.ts` and the `SessionExpired`
  panel; queries carry the status by throwing `new Error(String(response.status))`.
- **Never throw away what the server said.** The job editor threw
  `new Error(String(error ?? "create failed"))` — `String()` of a parsed body is `"[object Object]"`
  — and the workspace then rendered a fixed "Could not save. Check the details and try again." for
  every failure. A two-character title produced that sentence while the API had said
  *"String should have at least 3 characters"*, and an unknown standard produced it while the API
  had named the standard. Write failures throw `ApiError(status, readDetail(error))` from
  `lib/http.ts`, and the screen shows `detailOf(...)` with the generic line as the **fallback for a
  failure that carried nothing**, not the default.
- **`web/src/lib/constraints.test.ts` is the guard, not a memory.** It reads each form's source and
  asserts every server limit is mirrored on the input that can break it. Writing it found three
  more the hand patch had missed, and the seeker side had thirteen: the six profile collections
  share one editor and it enforced no length at all. **Add a `min_length`/`max_length` to a schema
  and add it to that table in the same change.**
- **A count is a claim, and a claim nobody shares reads as a fault.** The *same* report arrived a
  second time against a correct number and an empty cache. The panel counted **open** vacancies,
  and `scripts/seed_marketplace.py` closes one on every run, so publishing a twenty-first moved the
  figure 19 → 20 — right, and irreconcilable with what the employer had just done. The fix was not
  arithmetic: the panel leads with `jobs_posted` and names `jobs_open` underneath **when they
  differ**, so the number and its definition arrive together. `posted_job()` is the count's
  predicate and `open_job()` stays the listings'; **both payloads carry both names**, because
  `jobs` meaning two different things in two responses is the trap. The second line is gated on the
  payload, not on the comparison alone — two `undefined`s compare equal and would hide it while
  loading for a reason nobody chose — and that hidden branch is the one a seeded database never
  shows, so it has its own test. `posted_job()` is **not monotonic**: unpublishing removes the
  page and removes the row from the figure, which is what keeps it from ever naming a vacancy a
  visitor cannot open.
- **A constraint the form does not know about is one the person finds out the hard way.** `JobIn`
  and `CourseIn` set `min_length=3` on `title`; neither form had `minLength`, so the browser
  accepted two characters and the server refused them. Mirror every server limit on the input
  (`minLength`, `maxLength`, `min`, `max`) — the browser then says *"Please lengthen this text to 3
  characters or more"* before a request is ever made.
- **A live number has to be invalidated by the thing that changes it, and a count is not a
  catalogue.** The homepage's "Explore the marketplace" panels read `/marketplace/counts` and the
  band above them `/marketplace/stats`; both are computed live. Reported as "I added a job and the
  number did not move" — and the count was right. **Two caches in front of it were not.** `useOrgJobMutations` and
  `useOrgCourseMutations` refreshed `["org-jobs", slug]` and stopped, so publishing a vacancy and
  clicking back to the front page painted the figure fetched *before* the publish; and the service
  worker served everything under `/marketplace/` with **stale-while-revalidate**, so on a
  production build the number was permanently one visit behind and corrected only on the *next*
  load. The keys live in `web/src/lib/counts.ts` and every catalogue mutation calls
  `invalidatePublicCounts` — **including close and reopen**, which move `jobs_open` while leaving
  `jobs_posted` alone and therefore read like nothing to do with a catalogue. The three count endpoints are `LIVE_DATA` in `sw.js`: network
  first, cache only as the offline answer. `/skills/count` must be matched **before**
  `CACHEABLE_DATA`, whose `/skills` prefix would otherwise swallow it.
- **Never match an endpoint by substring.** `api.ts` skipped refreshing on
  `request.url.includes("/auth/")` to avoid looping on `/auth/refresh` — and caught **`/auth/me`**,
  the one call every signed-in screen depends on. So a 401 there was handed straight back, the app
  decided the person was signed out, and a thirty-day refresh token sat unused: a whole day of API
  logs contained **zero** calls to `/auth/refresh`. `shouldTryRefresh()` now compares exact
  pathnames against a named list, and `lib/api.test.ts` pins it.
- **A golden set's labels must be derivable from the inputs, never from what the scorer answers.**
  Sprint 29 took it from five pairs to 34 pairs, 7 orderings and 16 course expectations, and every
  label is either a coverage fact computable from `CANDIDATES` and `JOBS` without scoring anything,
  or an ordering the scorer's own documentation promises. Recording the scorer's output would
  measure the tuning and would agree with a broken scorer. **Nine labels failed on the first run and
  all nine were wrong, not the scorer** — which is the outcome to want.
- **`capped_missing_mandatory` and `missing_mandatory` are not the same claim.** `capped` is
  `raw > MANDATORY_GAP_CAP` in `scoring.py`, so it is true only for somebody who would otherwise
  have scored *above* 45. A candidate already at 39 is missing a mandatory standard and was never
  capped; asserting the flag there asserts the wrong thing.
- **Never label a vacancy the seed closes.** `scripts/seed_marketplace.py` closes
  `inventory-clerk-nagpur` as filled on every run and `match_job_by_slug` filters on `open_job()`,
  so four labels naming it could not be evaluated at all — they reported "job not found" rather
  than failing on their own terms.
- **`make evaluate` cannot run in CI, and a nightly workflow would be worse than none.** It needs
  the 21,303-standard corpus, which lives in MongoDB and is not in the repository;
  `tests/fixtures/nsqf_sample.json` holds nine invented codes and none of the thirty-five the seed
  maps onto. A build that is red every morning for a reason nobody can fix from CI teaches people
  to ignore red builds. **`tests/test_golden_set.py` runs instead** — it checks everything about the
  set that is true without a scorer, and it catches both mistakes above statically.
- **Every write must be able to report its own failure, and
  `web/src/lib/mutation-errors.test.ts` is the guard.** It reads the source and fails when a
  `useMutation` has neither an `onError` nor anything reading its `.isError`. Eleven paths had
  neither: `SkillsSection` — *the one control in the profile that moves a match score* — held no
  `error`, `isError` or `onError` at all, so the 60-standard cap produced no chip and no
  explanation; `Notices.markRead` never read `error`, and **openapi-fetch resolves on a non-2xx**,
  so `onSuccess` ran on a 500 and the button did nothing for ever. None of that is visible to
  `tsc`, to `eslint`, or to a render test that does not make the server refuse.
- **A fixed sentence that is wrong about *why* is worse than admitting you do not know.**
  `org.ts` threw `new Error("publish-refused")` under a comment saying the server's refusal "is the
  message the employer needs to see", and the screen mapped **every** failure to one line about
  required standards — so an employer whose fifteen-minute token had expired was told their vacancy
  needed a standard it already had. Mutations throw `ApiError(status, readDetail(error))`; a 401
  goes to `SessionExpired`, the server's own sentence goes on screen, and the generic line is the
  fallback for a failure that carried **nothing**. `FIELD_NAMES` in `lib/http.ts` must name any
  field a form can break, or the person reads a database column.
- **A docstring that claims a fix nobody made stops anybody looking.**
  `ProviderWorkspace.tsx` described its signed-out branch in the past tense — "there was no
  signed-out branch at all, so a provider whose token had expired was told they had no access" —
  and `isSignedOut` was never imported in that file. The claim outlived the gap by four sprints.
- **Every branch on who is signed in gets a component test.** `tsc`, `eslint` and `next build`
  cannot see a conditional that picks the wrong actor — it compiles perfectly — and all ten Sprint
  18 defects were exactly that. Mock the three seams through `src/test/harness.tsx`, set `world`,
  assert on rendered links and text.

## Current state

> **What to build next lives in [projectContextForMe.md](projectContextForMe.md) §11**, with §0 as
> the two-minute orientation: branch, test counts, how to run it, demo logins. This section is the
> record of *what was learned* sprint by sprint — read it for the rules that must not be broken,
> not for the queue. **Sprints 28-34 are done** (geography and operator authority, the back
> office and the golden set, the silent-failure sweep, the scope ledger, the delegation
> refactor, Sprint 33's actor-breadth MVP — thin-slice government-agency and external-system
> actors, course-to-role alignment, and the rest of Epic B2 pulled forward alongside it:
> configurable match weights, the `course_dismissed` signal, and market-wide scarce-skills for
> course providers — and Sprint 34's ADR-043 with a payment adapter port). **Sprint 35 is next:
> Epic B3, the Assessment Provider** (`docs/IISM-Product-Backlog.docx` §4). The payment port —
> a `PaymentProvider` protocol plus a console implementation that refuses unconditionally — has
> no caller anywhere yet and no billing code, no `Order`/`Entitlement` table; it does **not**
> claim ADR-025's deferral gate is satisfied, and the ADR says so plainly: two of its three
> metrics are still thin. §11 also carries a standing assessment of the three pillars the owner is
> building toward — jobs, sellable courses, gig work — and what each actually needs.

**Deleting one organisation** (reported 2026-09-23, fixed the same day). A job seeker who had
created an employer *and* a training provider wanted rid of only the first, and found that the one
control on offer deleted their whole account. The reproduction was worse than the report:
`DELETE /org/{slug}` was **405** — no such route — and `POST /org/{slug}/leave` is **409** for the
only owner, which Sprint 25 added on purpose. **Creating an organisation was one request; undoing
it was impossible.**

- **`DELETE /org/{org_slug}` and its preview live in `privacy/`, not `identity/`.** `_delete_tenant`
  is the single function that knows all eleven tables a tenant owns, and a second copy is how one of
  them starts being missed. It also keeps ADR-014 intact — privacy depends on every module and
  nothing depends on privacy — so the module gained an `org_router` rather than an outward import.
- **`ORG_DELETE` is the owner's alone**, separate from `ORG_UPDATE` for the reason `JOB_DELETE` is
  separate from `JOB_UPDATE`: an update reverses and this does not. An admin is a member, so they
  get **403**; a stranger still gets **404** (ADR-038). A personal workspace is unreachable through
  this route because `_context_for` filters to `ORGANISATION_TYPES`.
- **The preview excludes the caller from `other_members`.** Counting yourself tells a sole owner
  that one other person is affected, which is nobody.
- **Live applicants are told**, which closes a gap recorded since Sprint 24: an organisation could
  vanish and the people waiting on it heard nothing. `vacancy_closed` is reused rather than given a
  near-identical sibling — what the applicant needs to know is the same either way.
- **The UI requires the name typed, not a `confirm()`.** This is the only irreversible control in
  the product that destroys *other people's* records, and a dialog is one stray Enter from doing it.
  It also states what survives, because not knowing that was the actual complaint.

Sprint 27 (a vacancy that ends, and alerts that reach people) is done. Two things this product
could compute and would not act on: **"hired" did nothing to the vacancy** -- it stayed published,
kept ranking in strangers' matches and kept taking applications nobody would read -- and
**`match_jobs` ran only inside a request handler**, so a vacancy published on Monday reached a
matched candidate only if they happened to open `/matches`.

- **Closing is not unpublishing, and it is not a third `status`.** Fourteen queries compared
  `status == "published"`, so folding closure into that column would have left a closed vacancy
  visible in whichever one was missed. `closed_at` + `close_reason` are separate columns and
  **`open_job()` in `marketplace/models.py` is the one predicate every public listing uses** --
  browse, the homepage's *open* figure, matching retrieval, the match detail. **Its sibling
  `posted_job()` is the count's**, and a bare `status == "published"` there is deliberate rather
  than a listing that was missed. `ck_jobs_closed` refuses a row carrying one without the other.
- **A closed vacancy keeps its page and its inbox.** Its detail route deliberately does *not* use
  `open_job()`: people have it bookmarked and it is in their application list, and a 404 on a row
  we kept on purpose would be a broken link of our own making -- the rule retired skills already
  follow. Applying is a **409, not a 404**, because "closed" is a state worth naming and the
  candidate can disprove a 404 by pressing Back.
- **`positions` is what makes "hired" mean something.** `_close_if_filled` counts hired rows rather
  than incrementing a counter, so it stays correct after an un-hire or two hires landing together,
  and closes at the head-count with reason `filled`. Hiring a sixth against five positions is not
  refused -- the vacancy simply closes at five and the employer reopens it if they meant more.
- **Expiry belongs to the worker.** A closing date enforced only when somebody loads the page is
  not a closing date: the vacancy would sit in browse until a visitor arrived, and two people a
  second apart would see different answers. `close_expired_jobs` runs hourly; `expired` is the one
  reason an employer cannot claim, because claiming it would make the record untrue.
- **Reopening clears a `closes_at` already in the past**, or the worker closes the vacancy again
  within the hour and the employer watches their own action be undone.
- **The alert sweep claims a job before it queues anything.** `alerted_at` is stamped first, so a
  crash halfway costs the rest of that vacancy's alerts rather than re-sending the first few:
  under-alerting is recoverable by hand, double-alerting is not. `JobAlert`'s unique
  `(job_id, profile_id)` makes "told once, ever" a constraint rather than an intention.
- **Migration 0027 backfills `alerted_at = now()` on every existing vacancy**, and the seed does
  the same. Without it the first sweep treats the entire back catalogue as new and mails every
  candidate about every job ever published — the difference between switching a feature on and an
  incident.
- **In-app is the channel that lands, and the docstring says so.** 39 of 40 seeded candidates are
  phone-only and SMS waits on DLT registration, so email is queued only where an address exists.
  Two caps keep a busy Monday from being the reason somebody stops reading: `max_alerts_per_job`
  and `max_alerts_per_candidate_per_day`. `job_alerts_enabled` on the profile is the opt-out, and
  it is the only message this product sends that somebody did not ask for in the moment.
- **`candidates_for_job` is exported from `matching` so the sweep cannot grow its own scorer.**
  "Close enough to write to" is the same question as "close enough to rank" (ADR-037).
- **`tenants.created_at` is a naive `TIMESTAMP`** while `course_interests.created_at` is
  `timestamptz`. Comparing the naive one against an aware datetime makes asyncpg refuse the query
  outright — found by Sprint 26's organisation cap and worth remembering before writing the next
  rolling-window query.

Sprint 26 (a surface you would show somebody) is done. No new product surface: the theme made
systematic, one UI bug traced to its actual cause, and the organisation policy settled.

- **The dialog bug was a containing block, not a style.** See the frontend conventions above for
  the rule and the measurement. Three more defects sat on the same component and went with it:
  focus never entered a thing claiming `aria-modal="true"`, the body still scrolled behind it, and
  **there was no `keydown` handler anywhere in `web/src`** — so Escape, the first thing anybody
  tries, did nothing in any dropdown either. `lib/use-dismiss.ts` is the small hook for menus; a
  modal gets the Radix primitive, because a focus trap is not worth hand-rolling and a menu is not
  worth 12 KB.
- **The regression test asserts the DOM relationship, not a rectangle.** jsdom has no layout, so
  every rect is 0×0 and a measurement there would prove nothing. It renders the dialog inside a
  wrapper and asserts it escapes. The first version rendered the header and the form as *siblings*
  and could never have failed — **a test that cannot fail is worse than no test**, so it was
  deleted rather than kept for comfort.
- **Typography was the single biggest reason this looked unfinished**, and Hindi was the real
  problem rather than a cosmetic one: the system stack resolved Devanagari to Noto on Android,
  Nirmala UI on Windows and Devanagari Sangam MN on macOS. Inter and Noto Sans Devanagari are now
  self-hosted by `next/font/google` at build time, so no request reaches Google and
  `font-src 'self'` needs no change.
- **305 hardcoded colours are gone and cannot come back.** The migration is worth one warning: the
  first attempt collapsed runs of whitespace and ate the space in `from "next-intl/server"` across
  **624 lines**. It was reverted and redone touching only class tokens. **Never regex whitespace
  across a tree**; extra spaces in a `className` are harmless and guessing where they belonged is
  not.
- **The header lost three controls.** Ten in one flat row, with "My matches" as a filled brand
  button competing with whatever the page's own primary action was. The account items are behind
  one trigger now — as a **disclosure, not an ARIA `menu`**: `role="menu"` promises arrow-key
  navigation and typeahead, and `<a role="menuitem">` stops being a link to assistive technology,
  which is also what broke three tests until it was removed.
- **Organisations per account: no cap, and that is the decision.** One employer and one provider
  would force a staffing agency or a multi-centre training partner into a second account — the fork
  ADR-038 exists to prevent and Sprint 25 spent a sprint making unnecessary. What was actually
  missing is guarded instead: a **duplicate-name refusal** (409 naming the existing organisation and
  pointing at its slug, compared on the slug so "Apollo Care" and "apollo care." are one name), and
  a **rolling 24-hour creation cap** — tenant creation was the only write path here with none,
  while applications, interests and invitations all have one. Both live in
  `provision_organisation`, because **three call sites reach it** and a check in one handler is a
  check the other two do not make.
- **`tenants.created_at` is a naive `TIMESTAMP`**, unlike `course_interests.created_at`. Comparing
  it against an aware datetime makes asyncpg refuse the query outright. The cap passes a naive UTC
  value and says why.
- **Radix Dialog costs ~33 KB of the 684 KB budget**, which is now at 668. `next/dynamic` was tried
  and made it *worse* (+3 KB of loader for no saving, because the header mounts the dialog on every
  route anyway); keeping it out of the `ui/index.ts` barrel is what helped. **Headroom is 16 KB —
  the next component added to the header will breach it.**

Sprint 25 (an organisation that outlives its owner) is done. For twenty-four sprints this product
modelled organisations and could hold exactly **one person** in one: all three writers of
`Membership` hard-coded `role="owner"`, so `admin` and `member` were fully mapped permission sets
that nothing on earth could reach, and no endpoint anywhere touched the table.

- **The bug was data loss, not inconvenience.** A sole owner deleting their account hard-deleted
  the tenant, its vacancies and courses, and by cascade **every application to them**, telling
  nobody. The 409 in `privacy/service.py` that should have stopped it was **unreachable** -- it
  needs a second owner to exist -- and its instruction, "pass ownership to someone else", named an
  act the product could not perform. Verified live after the fix: the seeded owner of Apollo Care
  deleted their account and the organisation survived with all 5 vacancies and all 5 applications.
- **An `Invitation` is a row, not a pending `Membership`.** Writing the membership up front would
  have been fewer moving parts and one serious defect: an unaccepted invitation would count
  everywhere members are counted, including the sole-owner guard, which would then pass while the
  organisation still held one actual human.
- **State is derived, never stored.** `pending`/`accepted`/`revoked`/`expired` is a function of
  three timestamps, so no status column can drift from them. `CourseInterest.contact_is_visible`'s
  reasoning, one table over.
- **Three rules, each in exactly one function** (Sprint 15's finding). *Escalation* -- an admin may
  invite a `member` only, or `MEMBER_INVITE` becomes a route to promoting yourself by proxy. *The
  last owner* -- nobody may be removed, demoted **or** leave if they are the only one, asked once
  and reached by three routes. *Enumeration* -- the invite response is byte-identical for a known
  and an unknown address, which is Sprint 12's oracle restated.
- **`verify_email_and_sign_in` gained an account-creating branch, and its 401 is still
  load-bearing.** An unknown address with a valid code and no invitation still gets 401; the only
  thing that permits creation is a `PENDING_INVITE_KEY` in Redis, written by `claim` and consumed
  with `getdel` -- the **same mechanism** Sprint 18 built for pending organisations, not a new one.
  Proved non-vacuous: neutering the check fails exactly one test, and that test is why the function
  is shaped the way it is. **Consent is recorded on the create branch**, or every later request
  from the new account 428s.
- **The claim endpoint does not take an address.** It reads it off the invitation, so a forwarded
  link cannot mint an account at an address of the holder's choosing, and the invitee still has to
  read the code out of that mailbox. `GET /invitations/{token}` returns the organisation and the
  role and nothing else: the token is a capability to *join*, never one to read.
- **The outbox keeps its rule by gaining a third recipient kind, not an exception.** An invitee may
  have no account, so `recipient_kind="invitation"` points at the row that legitimately stores the
  address, and `_address_for` resolves it at send time. That buys something storing it would not:
  **revoking an invitation stops its mail**. Verified in a drain -- `sent: 1, skipped: 1`.
- **`accept()` records the analytics event, not the route.** The first version recorded it in the
  route only, so the *other* acceptance path -- the invited stranger, inside
  `verify_email_and_sign_in` -- went unmeasured, and that is the half the sprint is about. One
  writer of a `Membership` from an invitation, one place to measure it.
- **`uq_invitations_live` is a partial index** (`WHERE accepted_at IS NULL AND revoked_at IS NULL`)
  created with `op.execute()`, so it is in `MANUALLY_MANAGED_INDEXES`. Confirmed by autogenerating
  against a live database: no drift, and no proposal to drop it.

Sprint 24 (somebody is interested) is done. The product's pitch is "here is your gap, and the
courses that close it" — and for twenty-three sprints the learner could then do **nothing**. The
course page ended in a back link and skill chips; the provider who published it was told nothing,
ever. This is Sprint 21's loop, closed for the third actor.

- **Interest, not enrolment.** Whether somebody enrolled is a fact the provider owns in their own
  system; a status this platform cannot verify would drift from reality in a week. What it can know
  is that a learner said "I want this".
- **The product's second deliberate disclosure**, and the learner makes it. Name, phone, email,
  district and their own note reach **that** provider for **that** course, recorded as
  `contact_shared_at` (DPDP). Withdrawing sets `contact_revoked_at`, keeps the row so the provider's
  history is not rewritten, and takes the details back — **including the note and the district**. A
  withdrawn interest cannot be moved along (409), or marking it "contacted" would put contact back
  on screen by a side door.
- **`api/modules/interests/` is a sibling of `applications/`, not an extension** (ADR-026's
  precedent). A vacancy publishes required standards, so an applicant can be scored; a course
  publishes what it *teaches*, so there is nothing to rank against. **The provider inbox therefore
  has no candidate card and no score at all** — building one would be the second scorer ADR-037
  forbids. A test asserts no `score`, `coverage`, `matched` or `missing` ever reaches a provider.
- **`LEARNER_CONTACT` is gated by `require(..., "course")`.** `PUBLISHES["course"]` is
  `course_provider`, so one declaration refuses an employer (403) and a non-member (404) — the exact
  mirror of the provider being refused the candidate pool. `require()`'s 403 message now names the
  tenant type rather than the verb, because that gate guards reads too.
- **`course_recommended` was unattributable, and is fixed.** It recorded `subject_type="job"` and a
  bare count, while `course_opened` has always written `{"from_job": slug}` — the join key existed
  on one side only, so ADR-025's click-through was uncomputable from Sprint 10 to Sprint 24. It now
  writes one row per course, subjected to the course. **Rows written before 0025 carry the same name
  with `subject_type="job"` and are not backfilled** — an event is a fact about what happened — so
  any query must filter on the subject type.
- **`record_many()` exists because `record()` commits.** Five suggestions would have been five
  commits on a hot read path. Same contract: unknown names dropped, failures swallowed, never the
  reason a page fails.
- **`_delete_tenant` now deletes applications explicitly.** It never did — they went by FK cascade
  alone, against this module's own stated rule, while a comment claimed they were removed "exactly
  like the applications above", which were not there. The cascade did the right thing and nothing
  said so.
- **The worker does not reload, and this sprint proved it again.** The first drain after adding a
  template failed with `KeyError: 'course_interest_registered'` — the worker had been running since
  before the template existed. Restarting it drained `{"sent": 1, "skipped": 0, "failed": 0}`.
  **Restart `make worker` after any `api/` change.**

Sprint 23 (say what you do, and we'll name the standards) is done. It began as "should a CV
populate the profile?" and found something sharper: **exactly one thing on a candidate profile
changes a match score** — `candidate_skills` — and the only way to add one was to type a search
against 21,303 standards named like *"Follow infection control policies & procedures including
biomedical waste disposal protocols"*. A ward attendant will never type that. Now they type "ward
boy", tick what they can do, and have matches.

- **Role search is the corpus, not a model.** All 4,424 qualification packs carry a `job_role`
  (median 6 standards). `GET /roles/search` → `GET /roles/{slug}/standards` is
  `entry_routes_for_job` reversed. Tiers mirror `_SEARCH_SQL` — exact, prefix, contains, then
  `0.9 × word_similarity` so a guess can never outrank something typed. Key on the pack's **slug**,
  never `qp_code` (it contains a slash). One row per role: base code before `-SI` variant, then
  fewest `/` segments (the SSC's own code over a reissuer's), then most standards; `variants` says
  what was collapsed. Packs with no standards (84) are never offered.
- **`role_aliases.py` exists because "ward boy" shares no letters with "General Duty Assistant".**
  Fuzzy matching cannot bridge that; a list can — the `DISTRICT_ALIASES` move. Values must name a
  current pack with standards; `unresolved_aliases()` checks them against the real corpus. Point at
  the general pack, never a disability-track variant, and **check the prefixes of any key you add**
  — this is a typeahead, so "nurse" reaches the nursing-assistant certificate as a prefix of "nurse
  aide". The starter list awaits review by someone who knows the labour market.
- **A ticked suggestion is `self_declared`, never `inferred`.** `inferred` scores 0.7 against 0.6,
  so routing the easy path through it would reward acquiescence: golden candidate 3 would score 87
  against candidate 1's 88, one point from failing the ordering that makes evidence outrank
  self-claims. `_write_skills` is the **one** construction site for a candidate's `CandidateSkill`;
  single and bulk adds both go through it. Nothing in the picker starts ticked, for the same reason.
- **Bulk add is all or nothing.** A batch crossing the 60-skill cap is refused whole and writes
  nothing — eight ticked and three landing, with nothing saying which, is worse than a refusal.
  The role the candidate named becomes a preferred role, which finally connects the completeness
  meter's heaviest weight to the core loop.
- **A profile's location resolves on write.** `update_profile` was a bare `setattr`, and the only
  writer of `CandidateProfile.state_id` was the NSQF importer's backfill — Sprint 15's bug one table
  over. Seeded profiles looked fine because the import happened to run after them.
- **Experience scores; location only orders.** `LEVEL_WEIGHT` 0.15 became 0.08 + `EXPERIENCE_WEIGHT`
  0.07, which is identical for anyone meeting both floors — `make evaluate` is bit-identical. (In
  floating point `0.08 + 0.07 != 0.15`; the test uses a tolerance.) Exceeding a job's maximum is
  never penalised (ADR-037). Locality — district 2, state 1 — is a **tie-break in `match_jobs`**,
  never in `scoring.py`, because that scorer ranks candidates for employers too and a location term
  there would rank people by proximity. `CandidatePreferredLocation` finally has a reader.
- **`skills` and `marketplace` import `analytics` inside the handler.** `analytics` loads its routes,
  which load `marketplace.models`, which load `skills` — a module-level import is an ImportError at
  boot. `tests/test_import_order.py` imports every entry point first in a fresh interpreter, because
  inside the test process everything is already in `sys.modules` and a cycle passes unnoticed.
- **`migrations/env.py` had been wrong since 0022.** It listed the dropped `ix_skills_name_en_trgm`
  and not the live `ix_skills_name_trgm`, so the next autogenerate would have dropped the index
  behind every fuzzy skill search. Verified by autogenerating with the old file.
- **The homepage search answers a job title with jobs.** It posted to `/skills`, so "General Duty
  Assistant" returned 24 technical units and no vacancy. `/search` shows open jobs, then job roles,
  then standards, each linking to its full page with the query kept (`/jobs` now takes `?q=`).
- **A standard card says where it comes from.** 1,778 names are shared by 4,838 standards — a
  quarter of the corpus — and two identically named cards could only be told apart by opening them.
  Browse and search now carry `context` (qualification, awarding body, sector, batched in one query,
  representative pack chosen by role search's rule), the card shows the NOS code, and same-named
  results on a page are flagged "compare the codes". Some twins really are near-identical reissues
  (same qualification name, zero recorded hours); code and level are then all there is, and the card
  does not invent more.
- **Migrations freeze their own value lists.** 0024 builds its CHECK with `one_of()` over a tuple
  written *in the migration*, not the imported `EVENT_NAMES` — importing it would make 0024 produce
  a wider constraint the day a later sprint adds a name.

Sprint 22.5 (demo readiness) is done. No new product surface: the demonstrable product, made
demonstrable. The readiness check had found that **all six seeded applications belonged to
organisations with no members** — which is to say the whole of Sprint 21 could not be shown from a
cold start, because nobody could sign in and look at an inbox.

- **Every seeded organisation has an owner account.** `hiring@apollo-care.example` and its nine
  siblings, on the reserved documentation domain so none can be a real mailbox. `_owner_for` in the
  seed mirrors `provision_organisation` — `User` + `Tenant` + `Membership(role="owner")`, consent
  recorded, email marked verified — because a seeded organisation that behaves differently from a
  registered one is a fixture, not a demonstration. **Sprint 12's lesson applied one level up**: a
  tenant with no membership is invisible to everything that reads one.
- **Every one of the five employers has an inbox.** Sixteen seeded applications in mixed states
  across all five, not six across three. MedLife and Swift Logistics had none at all.
- **Fifty courses, chosen by what the vacancies require.** Thirty new ones, and the count is not the
  point: **every mandatory standard across the twenty vacancies is now taught by at least one
  course** — two at worst. Two had **none**, so the gap panel naming them offered nothing:
  `SSC/N9001` (`time-management`) and `SSD/VSQ/N0104` (`emergency-response-coordination`). The
  acceptance test is the coverage query, not the number of rows.
- **`scripts/clean_fixtures.py` names its thirteen slugs explicitly and never deletes an account.**
  `--dry-run` is the default. Pattern-matching fixture organisations in a database that also holds
  the owner's own is how a cleanup script becomes an incident.
- **Malay left the switcher, not the codebase.** `LocaleDefinition.visible`; routing, the messages
  file and the parity test still carry all three, so `/ms` resolves and the machinery stays proven
  beyond two languages. One line to reverse.
- **A missing message key now fails a test.** `employerConsole.matchScore` never existed — the key
  lives in `matchesPage` — so the employer's inbox rendered the literal string
  "employerConsole.matchScore" where the score belonged. It compiled, `tsc` was clean, and no test
  rendered that component. `renderUi` now throws on `MISSING_MESSAGE`, which makes **every** test in
  the suite a guard against this, and `EmployerInbox.test.tsx` covers the screen itself.
- **`renderUi` pins `timeZone="Asia/Kolkata"`.** A formatted date must not depend on where the test
  runs.

Sprint 22 (many languages, and something arrives) is done. The product was bilingual **by
construction**: 18 `_en`/`_hi` column pairs across 14 tables, 16 `_hi` fields in the API schemas and
37 two-language ternaries in the client. A third language was a schema migration. It is now an
entry in one file, a messages file, and rows.

- **The API resolves language; the client never picks** (ADR-041). `Accept-Language`, then an
  explicit `?locale=`, then the account's `preferred_locale` — which had existed since Sprint 4 and
  been read by nothing. Responses carry `title`, not `title_en` *and* `title_hi`.
- **Translations are applied at serialisation, never by assigning to the loaded row.** Several read
  endpoints call `record()`, which commits, so a translated title on an ORM instance would be
  written back as though somebody had edited the listing.
- **`locale` is the one closed set with no CHECK.** Every other one in this project has a
  constraint; constraining this would put "add a language" back into a migration.
- **The base column holds the row's own text**, with `source_locale` on jobs and courses saying
  which language that is. The corpus is English; a vacancy posted in Hindi is source-Hindi, which
  is why the rebuilt search vectors index the *same* column with both the `english` and `simple`
  configurations. Postgres still ships no Hindi stemmer.
- **A generated column blocks dropping what it reads.** `skills`, `jobs` and `courses` each carried
  a `search_vector` GENERATED over four of the columns 0022 removes, so each had to be dropped and
  rebuilt — and `ix_skills_name_en_trgm` with them. Migration 0022 was rehearsed against a full copy
  of the development database before touching it; down and up again restored exactly 52/22/21 Hindi
  values. **Rehearse anything of this shape.**
- **Two is the number that hides the assumption.** A Malay skeleton ships as a third locale —
  navigation translated, everything else visibly English — because a two-locale product proves
  nothing about a third. A test holds every locale's messages file to the same key set.
- **Server components run no client middleware.** The three detail pages were asking the API for the
  default language on a page that was not in it; each passes `accept-language` explicitly now.
- **Notifications are queued, never sent inline** (ADR-006). An SMTP timeout while somebody applies
  must not lose the application, and a test applies through a provider that always raises.
- **The outbox row names a recipient and never holds an address.** It is resolved at send time, so
  contact details stay out of a dumped table and out of any log line (ADR-023) — and erasure deletes
  notifications explicitly, because there is no foreign key to cascade from.
- **`Tenant.contact_email` is usually empty.** Registration puts the address on the `User` who
  registered; the organisation profile is where that field is filled in, and most never are. Sending
  to an organisation falls back to its owner. Do **not** "fix" this by copying the registrant's
  address into `contact_email`: that field is the organisation's stated inbox, and filling it in on
  somebody's behalf publishes a personal address they never offered.

Sprint 21 (the loop closes) is done. For twenty sprints the product could **compute** an outcome and
not **produce** one: a candidate saw ranked vacancies with no button, and an employer saw a pool it
could not reach. A candidate now applies, withdraws and saves; an employer sees who applied, with
the contact details to act on it.

- **Applying is the product's one deliberate disclosure, and the candidate makes it.** ADR-037's
  "no employer-facing payload identifies a candidate" still holds for every *pool* and *ranking*
  endpoint. An application is the single exception: the name and contact reach **that** employer,
  for **that** vacancy, recorded as `contact_shared_at` (DPDP Act 2023). Withdrawing sets
  `contact_revoked_at`, keeps the row and takes the details back, and a withdrawn application
  cannot be moved along (409) — otherwise shortlisting would put contact back on screen by a side
  door.
- **`candidate_card()` is the only construction site for the de-identified payload**, exported from
  `matching` and used by both the pool and the inbox. That invariant is a property of one function;
  a second copy is how it stops being true. A test asserts the pool still names nobody.
- **`score_profiles()` scores named applicants through the same `score_match`.** An applicant need
  not be in the retrieved pool — anyone may apply, and refusing the under-qualified would be a
  hiring decision this product does not get to make. **Do not add a second scorer** (ADR-037).
- **`matching` imports `applications` lazily, inside the counting function.** The two import each
  other; this is the fix `core/authorization.py` already uses. The failure is an ImportError at
  boot, not a wrong answer. *(This entry claimed a test asserted both import orders; none did until
  Sprint 23's `tests/test_import_order.py`.)*
- **Applying is gated by `get_current_candidate`**, so pressing Apply can never create a candidate
  profile for an organisation-only account — and the interface offers that account no button at all,
  rather than one that always fails.
- **A row you just created has no loaded relationship.** `save_job` returned the new `SavedJob` and
  the handler touched `.job`: a lazy load in async context, `MissingGreenlet`, a 500. It passed in
  one test file only because that job was already in the identity map. Re-query with
  `populate_existing` before returning anything a handler will serialise.
- **The analytics CHECK is generated from `EVENT_NAMES` with `one_of`.** It was spelled out beside
  the tuple as a literal and drifted the moment four names were added. Migration 0020 widens the
  database's copy; the model no longer has a second copy to drift.
- **A rolling 24-hour cap on applying** (`MAX_APPLICATIONS_PER_DAY`, default 50) answers patient
  spraying, which the per-minute write limiter does not. Counted over 24 hours, not a calendar day,
  so it cannot be doubled by waiting for midnight.
- **A listing renders the Hindi title when there is one.** `/hi/applications` shipped showing
  English titles on a Hindi page because the new list read `title_en` unconditionally; every other
  listing in `web/src` already picked by locale. Found in the browser, not by a test.

Sprint 20 (safe to deploy) is done. No new product surface: the non-functional requirements that
need no outside account — privacy law, web security, abuse protection, recovery, quality gates —
closed before the first deployment in Sprint 21.

- **Consent is a server-side record, not a checkbox.** `users.consent_version` / `consented_at`
  (0018) hold which notice was agreed and when; a checkbox the API never hears about proves
  nothing. Nullable and **not backfilled** — writing a version into old rows would fabricate
  consent nobody gave. `PRIVACY_NOTICE_VERSION` lives in **both** `api/core/config.py` and
  `web/src/lib/legal.ts`; a test compares them, because drift makes every signup fail with 428.
  Change both together, and only when people must agree again.
- **The phone path asks for consent *after* the code, never before.** Verification creates the
  account, so an unknown number without the current version gets 428 `consent_required` — after
  the code proves the caller holds the phone. Asking earlier would answer "is this number
  registered?" to anyone (ADR-038). Org registration checks it up front, before any lookup, so the
  answer is the same for a known and unknown address. **Sign-in never creates an account**: the
  428 is shown as "no account yet — sign up".
- **`api/modules/privacy/` depends on every module and nothing depends on it.** Export and erasure
  span identity, the profile, listings and analytics; letting any of those reach into the others
  would break ADR-014. Erasure deletes table by table rather than trusting cascades, clears
  `analytics_events.user_id` (the events identify nobody once the account is gone), and revokes
  refresh tokens **after** the commit. The only owner of an organisation others belong to is
  **refused** (409) — deletion never leaves an organisation nobody can run.
- **Hardening is middleware, for the Sprint 15 reason** — a guard each handler must remember is one
  that eventually is not there. `SecurityHeaders`, `BodySizeLimit` and `RateLimit` are pure ASGI
  like `RequestContextMiddleware`. **The limiter fails open**: an unreachable Redis must not become
  an unavailable platform. Signed-in callers count per account, anonymous ones per IP, because
  carrier-grade NAT puts many strangers behind one address. **`X-Forwarded-For` is ignored unless
  `RATE_LIMIT_TRUST_FORWARDED=true`** — honouring it from anyone lets a client pick a fresh identity
  per request; set it only behind the ALB. Tests disable the limiter in `conftest.py`; its own
  tests switch it back on.
- **`/docs` and `/openapi.json` exist in local environments only.** `make gen-api` reads the local
  one. CORS no longer grants credentials — auth is a bearer header and no route uses a cookie.
- **A 15-second statement timeout applies to every connection.** The seed, evaluate and
  import-nsqf targets run with `DB_STATEMENT_TIMEOUT_MS=0`; a new long-running script needs the same.
- **The web CSP ships report-only**, and still allows `'unsafe-inline'` scripts: Next's inline
  bootstrap carries no nonce on statically rendered pages, and nonces force dynamic rendering.
  Enforcing it is a deliberate trade against static rendering, not a header rename. Verified clean
  in the browser console; switch the header name once a production build is clean too.
- **A detail page calls `notFound()` only on a 404.** Every failure used to land there, so an API
  outage told visitors the listing did not exist. `error.tsx` says "unavailable"; `global-error`
  reads `messages/fatal.json` rather than both full catalogues.
- **Form controls use `border-input-border`, not `border-border-token`.** The shared border is
  1.23:1 on white — fine for a card, a WCAG 1.4.11 failure for an input you must find to type in.
- **`a11y.test.tsx` runs axe with `color-contrast` off** — jsdom has no layout, so it would pass
  everything. It includes a case proving axe *does* report a violation; keep it.
- **The employer overview costs the same for one vacancy or forty.** It scored per job: 18
  statements for one, 57 for four. `_candidates_for_jobs` batches; a test counts statements.
- **Backups are encrypted and live outside the tree** (`~/iism-backups`, `IISM_BACKUP_PASSPHRASE`),
  and MongoDB is finally covered. `make restore-drill` restores both into scratch databases and
  compares exact counts — run and passed 2026-09-11. See `backups/README.md`.
- **CI installs from `uv.lock` (`--locked`)** and audits both dependency trees; Dependabot opens
  grouped weekly updates; a first-load JS budget (700 KB) runs after the build.

Sprint 19 (every door opens onto all three) is done. `/signup/[type]` rendered exactly one form,
fixed by the URL: arrive at `/signup/seeker` — from the chooser's first row, a bookmark, a typed
address — and the page offered phone registration and nothing else, so an employer or a training
provider who landed there had to find the Back button.

- **The registration page carries its own type switch** (`SignUpTypeSwitch`): *Find work · Hire ·
  Offer training*, framed as what you are here to do, like `RoleChooser`. **Plain links, not a
  client toggle** — the type is still in the URL, so `/signup/employer` stays linkable from the
  audience pages; switching needs no JavaScript on the target device; and `replace` keeps three taps
  from becoming three Back presses.
- **`SignUpForm` is keyed by `type`.** Switching reuses the same route with a new param, and without
  the key React keeps the form's state — a phone number typed as a job seeker reappears in the
  employer's email field, and a code already sent stays on screen. Verified in a browser: type a
  number, switch to Hire, and the email field is empty.
- **`/signup` stays the neutral entry** — the header, the closing band and sign-in all point there.
  The switch is for people who arrived at a specific type and meant another.

Sprint 18 (one identity, honestly) is done. Three defects found by hand in one sitting were one
defect: the product models three actor types and one identity holding several roles, and the
interface assumed the job-seeker case. A scan found seven more of the same family.

- **`POST /auth/org/register` never mints a second account for a signed-in caller.** It ignored who
  was calling, so a candidate who opened `/signup/employer` and typed a work email became two
  `User`s — the fork ADR-038 exists to prevent. Sprint 13 documented it, removed the button and left
  the route open; Sprint 16's homepage `RoleChooser` then put a more prominent button back. The
  route takes `get_optional_user`: signed in, the organisation becomes a second *membership*.
  **Guard the route, not the button** — a public page will always find its way back to a public
  endpoint.
- **A signed-in surface branches on membership, never on "signed in" alone.** `get_current_user`
  answers *is someone signed in*; `get_current_candidate` answers *did they sign up to look for
  work*, and gates `/me/profile*` and `/me/matches*`. Before it, an organisation-only account that
  opened `/profile` had a `CandidateProfile` created and committed by `ensure_profile` and was walked
  into the candidate wizard. `ensure_profile` stays lazy — for candidates who have not got round to
  it, not for accounts that never asked.
- **What a sign-in reveals, it reveals on *verify*, never on request.** `SignInOut` carries
  `created` and `organisation_slug`; the caller has just proved they hold the phone or mailbox, so
  nothing is disclosed that their own messages would not. `OtpRequestResponse` still carries
  nothing, and the request-time oracle stays shut (ADR-038). `created` had been computed and
  thrown away by the route while its docstring claimed a client read it.
- **A known address registering a new organisation keeps the name it typed.** Held in Redis at
  `auth:pending_org:{address}` and provisioned on the existing account at verification — never at
  request time, which would let anyone who knows an address attach an organisation to someone else.
- **The header's profile slot follows the context.** `AuthNav` rendered "My matches" / "My profile"
  for every signed-in identity; inside `/employer/{slug}` it now offers **Organisation profile**,
  and an organisation-only account never sees the job-seeker side anywhere. `nav.settings` is gone
  from `ORG_NAV` because that control *is* the organisation profile. `Header` renders no org nav
  until it knows the org's type — `ORG_NAV[orgType ?? "employer"]` flashed "Vacancies" at providers.
- **Landing lives in one pure function**, `landingFor` in `web/src/lib/context.ts`. Sign-in sent
  every dual-role person to `/matches` and `.find()`-ed an unordered `memberships` array for everyone
  else, while a comment claimed "newest". The last-used context is remembered in localStorage as a
  *preference*, honoured only if this account still holds it — which is what makes it safe on a
  shared phone.
- **`web/` has a test runner.** `npm test` (Vitest + Testing Library) runs in CI. Tests mock exactly
  three seams — `@/lib/auth`, `@/lib/org`, `@/i18n/navigation` — through `src/test/harness.tsx`,
  because *who is signed in, what they hold and which URL they are on* is what varied in every
  defect. Proved non-vacuous by swapping the pre-sprint components back in: 10 of 15 fail. The
  provider-nav test passes against the old code once memberships have loaded — the *loading-state*
  test is the one that detects that defect; do not delete it as redundant.
- **Never gate a commit on `make check | grep`.** The pipeline's exit status is `grep`'s, so
  `make check | grep … && git commit` committed a failing lint this sprint. Capture `make check`'s
  own exit code and branch on that.

Sprint 17 (logging you can run a customer on) is done. One JSON stream on stdout, a redaction
filter that cannot be bypassed, and a request id, user id and tenant id on every line.

- **`Card` is the border; `CardBody` is the padding** — see the frontend conventions above.
- **The redaction filter is a processor, not a convention.** ADR-023 always specified "an explicit
  redaction filter"; there wasn't one. It sits in the **shared processor tail**, which is the only
  position that covers both structlog and `logging.getLogger()`. It **masks, never drops and never
  raises**: dropping deletes the evidence you need to find the leaking call site, and raising fires
  inside `Handler.emit` where `logging.raiseExceptions` swallows it to stderr. Touched records are
  marked `redacted=True`, so one query enumerates every leak.
- **Never use `structlog.processors.dict_tracebacks`.** Its `ExceptionDictTransformer` defaults to
  `show_locals=True`, and `code = generate_otp()` is a plain local in four functions in
  `identity/service.py` — any raise beneath them would write a live OTP into the log. The
  configuration passes `show_locals=False` and a test asserts both that ours does not leak and that
  the default recipe *does*.
- **A redaction pattern must be narrow enough not to eat a timestamp.** The obvious phone regex
  `\+?\d[\d\- ]{8,14}\d` matches `2026-09-10` and rewrites it to `20260910` — and `timestamp` is
  on every line, so the loose form corrupts the whole stream and marks every record redacted.
- **`RequestContextMiddleware` is pure ASGI, not `BaseHTTPMiddleware`.** The latter runs the app in
  a child task and anyio *copies* the context, so `bind_contextvars` inside `get_current_user` and
  `_context_for` — both dependencies, both downstream — would be invisible when the access line is
  written. Every access line would be anonymous. **Do not convert it.**
- **Log the route template, never the path.** `/org/{org_slug}/jobs`, not the interpolated slug: a
  customer's name in every line is both a leak and a new CloudWatch field value per request. An
  unmatched path falls back to a constant, so a 404 flood cannot become a cardinality flood.
- **The worker's entrypoint is `api/worker.py`.** ARQ's CLI imports the settings module and *then*
  runs its own `dictConfig`, so configuring at import time is clobbered and every line is emitted
  twice. The Makefile also passes `--custom-log-dict`, because ARQ logs two lines before any hook
  exists.
- **`arq.worker` is pinned to WARNING.** The 5-second heartbeat cron emitted ~34,560 INFO lines a
  day. At WARNING what survives is exactly the signal: job raised, retries exceeded, job expired,
  function not found, deserialisation failed.
- **An authorization denial is logged.** `_context_for`'s 404 and `require`'s two 403s were silent,
  so a multi-tenant product could not answer "who was refused which organisation". What the log may
  say and what the response may say are different questions — the caller still gets the same
  uninformative 404.

Sprint 15 (consolidation) is done. No new product surface: four unpushed sprints reached the
remote, the tree lost what earned nothing, and the documents were made to agree with the code. What
it found is more useful than what it deleted.

- **`record()` raised.** Its docstring says "Never raises" and its unknown-name guard called
  `log.warning("analytics.unknown_event", event=name)` — structlog's bound logger takes the first
  positional argument as `event`, so the keyword collided and raised `TypeError`, from *above* the
  `try/except` that exists to absorb exactly this. The same collision sat in the `except` branch,
  where it would have raised out of the handler whose whole job is to swallow. `analytics/` had no
  test file; writing one found it in the first run. **Measurement must never be the reason a page
  fails, and for two sprints it could have been.**
- **A guard a handler must remember to call is one that eventually is not called.** Three of the
  eight publishing writes shipped without the tenant-type check while this file asserted all eight
  had it. The fix was structural: `require(Permission.JOB_UPDATE, "job")` now asks both questions in
  one declaration and `require_publisher_of` no longer exists as a separate function. Never
  reintroduce the separate form.
- **A closed union on an output model is safe only while a test says the CHECK agrees.**
  `tests/test_enumerations.py` compares all fifteen against their constraints and found two columns
  with no constraint at all. See the convention above; migration `0017` closes them.
- **`api/modules/marketplace/listings.py` is the shared *policy*, not a shared entity.** ~22
  byte-identical lines of standard-existence and retired-row validation lived in both publishing
  modules with **no test in either copy** — the most drift-prone construct in the pair, and the one
  thing ADR-026 explicitly requires both paths to agree on. The merge rules stay apart, because
  those genuinely differ.
- **The seed now resolves geography itself.** It wrote jobs with a NULL `state_id` and relied on
  `_backfill_geography` inside `make import-nsqf` — but the seed *requires* the import to have run
  first, so the documented order is import → seed and the backfill fired **before the rows it
  needed to fix existed**. A clean `make import-nsqf && make seed` left every seeded job findable
  at `/jobs` and invisible to `match_jobs(state_id=…)`. Proved by clearing the FKs on 11 seeded
  jobs and re-running the seed alone: 11 unresolved before, 1 after.
- **`DISTRICT_ALIASES` existed twice; there is one copy now.** A test asserted the two maps were
  identical, which kept the *letters* in step and not the algorithm: the service tried the literal
  name then the alias, the importer tried both in one expression, and neither constrained by state.
  Sprint 28 deleted the importer's copy and routed both through `PlaceIndex`. **Duplicating a rule
  and testing that the data agrees is not the same as having one rule.**
- **The dev panel moved to `/status`**, which `notFound()`s in production and is linked from
  nowhere. It was rendering unconditionally below the fold on the landing page, captioned "Not part
  of the product surface", over a live Postgres/Redis/worker grid.
- **37 message keys were dead**, `orgAuth` entire — orphaned when Sprint 14 deleted
  `OrgSignInForm.tsx`. Three rounds of the audit produced false positives before the real number:
  template-literal prefixes split on `.`, and two `useTranslations` bindings in one file were stored
  in a dict keyed by variable name, so the second silently overwrote the first. **Do not delete an
  i18n key on a grep alone.**

Sprint 14 (three ways in, one way back) is done. The homepage offers three
registration paths, a training provider can finally publish courses, and sign-in is one door that
takes either credential.

- **Registration is type-aware; sign-in is not.** ADR-032's rule that the *credential* follows the
  actor type still governs signup. But one identity can hold both credentials and several roles, so
  at sign-in the credential no longer says who you are — `/signin` detects an `@` and routes on what
  the account holds. Two doors would ask a question the account can already answer.
- **`api/modules/marketplace/course_publishing.py` is a sibling of `publishing.py`, not a
  generalisation.** A `JobSkill` carries importance and mandatory because a match is scored against
  them; a `CourseSkill` carries only `level_taught`. Duplicates therefore collapse on the **highest
  level**, not the strongest signal — the seed's own rule. Do not merge the two modules.
- **A write route declares what it publishes, and the dependency asks both questions.**
  `require(Permission.JOB_UPDATE, "job")` checks the permission *and* the tenant type, because
  membership answers *may this person act here*, never *is this the right kind of organisation*.
  The two were separate until Sprint 15 — a `require(...)` in the signature and a
  `require_publisher_of(...)` call in the body — and three of the eight publishing writes shipped
  without the second while this file asserted all eight had it. **A guard a handler must remember
  to call is one that eventually is not called.** Never reintroduce the separate form.
- **`/org/{slug}/candidates` requires an employer.** It used to answer 200 to a provider with two
  empty arrays and `candidates_total`, which has no tenant filter — so the only number on screen was
  a global count of every candidate on the platform, presented as a pool they could reach.
- **Every mutation that can 403 needs an `onError`.** `EmployerWorkspace.save` had only `onSuccess`,
  so a provider filled in a whole vacancy, pressed save, and the form sat there having silently done
  nothing. That is worse than the 403.
- **The header nav and the workspace heading both follow `tenant_type`.** Nothing in `web/src` read
  it before, which is why a training provider was shown "Vacancies" and "Post a vacancy against the
  National Occupational Standards".
- **"Job seeker" appears only for an account with a personal membership.** An organisation-first
  signup creates no personal tenant, and offering it a job-seeker context it never chose is the
  assumption this sprint removed. That is also the personal tenant's first real job — it had been
  written once and read nowhere since Sprint 4.
- **`useMemberships` returns every organisation, not just employers.** Filtering to employers
  dropped providers out of the switcher, so one created through `CreateOrgForm` was navigated into a
  workspace it could never return to.
- **No migration.** `tenant_type` already permitted `course_provider`, `Course.status` already had
  the draft/published CHECK, and `CourseSkill.level_taught` already existed.

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
  A job needs an `employer`, a course a `course_provider`; nothing enforced this before. The check
  arrived here as a separate `require_publisher_of` call and was folded into `require()` itself in
  Sprint 15, after three of eight writes turned out never to make it — see that sprint's entry.
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
- **`is_verified` is derived from `verified_at`, and an operator is not a role** (ADR-042).
  `api/core/authorization.py` now answers two questions, not one: `require()` resolves a tenant from
  the path, `require_operator()` resolves only the caller and returns an `OperatorContext` **with no
  tenant on it**. Widening `TenantContext` with a nullable tenant would have made "every org-scoped
  query filters on `context.tenant.id`" conditional at forty call sites. `OPS_*` permissions are
  members of the same closed enum — ask for a Permission, never for the flag — and
  **`ROLE_PERMISSIONS` may never contain one**, because `owner` is the widest role there is and an
  organisation's owner must not be able to verify their own organisation. A test asserts the two
  sets are disjoint, and asserts both are non-empty first.
- **`users.is_staff` has no writer over HTTP, in this or any later revision.** `scripts/grant_staff.py`
  is the only one, it needs database credentials, and it **refuses to create an account** — a script
  that can mint a user *and* make them staff is a one-command account takeover. A test scans the
  OpenAPI schema for any request body carrying the name, and asserts it **finds** `is_staff` on
  `UserOut` first, so a rename cannot make it pass by finding nothing anywhere. **A back office
  whose first feature is its own escalation path is what that rule prevents.**
- **403 only where the caller has already established standing in the thing they are refused; 404
  otherwise.** That generalises ADR-038's tenant rule rather than contradicting it. A non-operator
  gets a 404 whose body is **byte-identical** to an unrouted path — a different `detail` string is
  as good an oracle as a 403, and this product has shipped one of those before. The test compares
  the refusal against `/ops/definitely-not-a-route`, and a sibling asserts an operator gets **200 on
  the same URL**, without which a typo in the path would make every 404 assertion pass for ever.
- **The back office mounts in every environment.** The *demonstration* console is guarded because it
  is **unauthenticated**, not because it is non-production. Verifying an organisation is a
  production activity, and a badge grantable only on a laptop is the absent writer in a new costume.
- **This FastAPI keeps an included router nested**: `app.routes` holds `_IncludedRouter` objects and
  only two bare `APIRoute`s, so walking it for `APIRoute` finds almost nothing. Recurse through
  `route.original_router.routes`. The route-guard test found this the moment it ran, because it
  asserts the list it walked is **non-empty** before asserting every member is guarded — an empty
  list satisfies `all()`.
- **`is_verified` was set by an operator and written by nobody** — for sixteen sprints, until
  Sprint 28 gave it a writer. It and its three provenance columns are absent from
  `OrganisationIn`, so no request shape can set them — as are `slug` (a published URL) and
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

*(This paragraph listed what was still to come as of Sprint 1. Matching, analytics, the golden-set
harness, organisation/email sign-in, self-serve publishing for both actor types and the whole NSQF
hierarchy above Skill have all since shipped — Sprints 6–14. **Typed `SkillRelation` edges and
embeddings remain unbuilt**, with an ADR each and no code. Do not assume every module named above
ships in v1; confirm scope before building out a module's business logic.)*

## Local development

See [README.md](README.md) for setup (Docker Compose for Postgres/Redis, running the app,
running tests).
