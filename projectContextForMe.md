# Project context — read this first

Working notes for Claude Code. Purpose: recover full context on a new session without
re-reading the codebase or the conversation history. Update it at the end of any session
that changes the shape of the project.

**Last updated:** 2026-09-02 · Sprints 1–5 built + a security/perf pass; matching is Sprint 6

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
| `docs/adr/architecture-decisions.md` | **34 ADRs — the source of truth for every design decision.** Read before any structural change. |
| `docs/IISM-Product-Definition.docx` | 20-page product definition: problem, actors, intelligence layer, scope, risks, decision appendix. Written for the founding team, deliberately candid. |
| `CLAUDE.md` | Working conventions, repo layout, current state. Auto-loaded each session. |
| `README.md` | Setup and run instructions. |
| `~/.claude/plans/i-want-to-create-lively-phoenix.md` | **The sprint plan, 1–4.** Sprints 1–2 as built; 3–4 planned in detail with deliverables, on-screen outcome, exclusions, definition of done and verification. Lives outside the repo. |
| This file | Session-to-session continuity, environment quirks, hard-won gotchas. |

ADR-001–023 came from a March 2026 spreadsheet. **ADR-024–033 were written in this project
(Sept 2026)** and cover: multi-sector scope, monetization deferral, supply acquisition, ARQ over
Celery, AWS topology, Next.js client, in-house identity, AI provider abstraction, dual credentials,
language scope. Three repairs were also made: ADR-014's malformed status, ADR-015 marked superseded,
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

**Sprint 6 (NSQF master data) — built, then rolled back.** The corpus was imported from MongoDB
(43 sectors, 4,424 QPs, 21,303 skills, 27,278 links, idempotent, ~16s) and the migrated data was
then deliberately deleted on 2026-09-04.

An audit against the source found the import had taken the taxonomy's **labels** and left its
**content** behind, and had one modelling decision built on a false premise. Rather than patch it,
the data was discarded pending a complete re-migration once the remaining master data — sectors,
Sector Skill Councils, states, districts, awarding bodies — is loaded.

**[docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md) is the record of that
audit and must be read before the re-migration.** Headlines:
- **A NOS does carry its own NSQF level.** All 27,538 do, in a field spelled `nsqf`; a
  qualification spells the same concept `nsqfLevel`. Sprint 6 checked the qualification's spelling
  against standards, got zero, and wrote "a NOS carries no level" into the schema, four commits
  and every doc. It left 4,730 units with no level and contradicted 653 more.
- **~893,000 content records were never imported** — 349,874 performance criteria (with marks),
  292,762 knowledge parameters, 250,281 generic skill criteria, 55,747 element headings.
- **NCO-2015 occupation codes** (`alignedTo`, 3,214 QPs), **entry qualifications** (`minEduQual`,
  4,571) and the **assessment blueprint** (`assmtCrt`, sourced per-NOS weightage) were all missed.
- 4,847 rows shared a duplicated name; "Employability Skills" was 67 separate units.

What is still in place: the schema (migrations 0007–0010), `api/adapters/nsqf/`, server-side
pagination and facets on `/skills`, and the tests. The database is back to the 52 curated skills
and 149 aliases. **Do not run `make import-nsqf`** until the schema is redesigned against the
complete master data.

**Verified at last run (after the rollback):** 140 Python tests pass · Ruff + mypy clean ·
all endpoints 200 · multi-script search still resolves `khoon nikalna`, `रक्त` and `phlebotomy` ·
52 skills / 149 aliases / 8 tenants / 20 jobs / 20 courses / 9 users.

**Not built yet:** matching, typed `SkillRelation` edges, embeddings, analytics instrumentation,
observability, the encryption path, and **Hindi for the national corpus** (§12).

## 5. Repository map

```
api/                    FastAPI modular monolith
  main.py               app, health, demo task endpoints
  core/                 config, database, cache, tasks (ARQ), health
  modules/skills/       models, schemas, service, routes, __init__ (public interface)
  modules/marketplace/  Job, JobSkill, Course, CourseSkill + browse/detail endpoints
  modules/identity/     User, Tenant, Membership, OTP sign-in, JWT
  core/security.py      tokens, OTP hashing, rate limits, get_current_user
  adapters/notifications/  NotificationProvider protocol + console impl
  adapters/nsqf/        NsqfSource port + Mongo and JSON-file sources, document
                        parsing, normalisation, importer (ADR-017, ADR-034)
  modules/skills/hierarchy.py  Sector, SubSector, Occupation, QualificationPack,
                        QpSkill, ModelCurriculum, ModelCurriculumSkill
web/                    Next.js 16 PWA
  src/app/[locale]/     13 routes, all bilingual
  src/components/       Header, Hero, HowItWorks, Audiences, BrowsePanels, CtaBand,
                        Footer, SkillBrowser, SystemStatus, DevPanel, PlaceholderPage, ui
  src/messages/         en.json, hi.json — no user-facing string is hardcoded
  src/lib/api-schema.d.ts  GENERATED from OpenAPI, never hand-edit
infra/docker-compose.yml   Postgres 16 + pgvector (5433), Redis 7 (6380), Mongo 7.0 (27018)
migrations/versions/    0001 (pgvector + skills), 0002 (taxonomy + search),
                        0003 (tenants, jobs, courses),
                        0004 (users, memberships, candidate profiles),
                        0005 (rich profile), 0006 (list-filter indexes),
                        0007 (widen nsqf_level to Numeric(3,1)),
                        0008 (NSQF hierarchy), 0009 (widen level_taught),
                        0010 (skills.qp_count)
scripts/                seed_skills.py, seed_marketplace.py, import_nsqf.py — all idempotent
tests/fixtures/         nsqf_sample.json — the corpus in miniature, so tests need no Mongo
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
make seed        # load the skill taxonomy + marketplace (idempotent)
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

- Branch **`v2/sprint-1-skeleton`** — name is now misleading, it holds two sprints. Worth renaming.
- **Nothing has been committed.** The whole rebuild is uncommitted working tree.
- The original `app/` (identity module, auth, 8 actor types) was deleted in this branch's working
  tree but **remains in history on `main`** at commit `ef59c4e`. Recoverable if the identity work
  is worth mining when Sprint 3 builds auth.
- `docs/` was carried forward untouched.

## 11. What comes next

**Hindi for the national corpus is the largest open gap.** All 21,303 imported skills are
English-only: the source contains no Devanagari at all, and the 149 aliases still attach only to
the 52 curated skills. Searching `khoon nikalna`, `बिक्री` or `safai` today returns curated skills
and *nothing* from the national taxonomy. This is a real, stated regression against ADR-033.

The planned answer is an ARQ translation job over a prioritised subset — 43 sectors, then 4,424 QP
job roles, then the NOS referenced by seeded jobs — writing back to Postgres and **mirroring into
Mongo so a re-import cannot destroy the translations**. It is blocked on an LLM adapter
(ADR-018/031) and on provider credentials, neither of which exists yet. Do not present the
bilingual story as complete before this lands.

**`scripts/map_legacy_skills.py` was planned and deliberately not built.** Its premise was that the
52 curated skills would be replaced and their 149 aliases had to be carried onto real NOS codes.
They were not replaced, so nothing needs rescuing. Searching the corpus for each of the 52 found a
confident NOS counterpart for only about 11; forcing the rest would attach Hindi aliases to units
that do not mean the same thing, and even the good 11 would produce duplicate search results for
0.05% coverage. The finding worth keeping is that **the hand-written Sprint 2 vocabulary and the
national standard do not align concept-for-concept** — translation, not mapping, is the answer.

**`scripts/seed_marketplace.py` did not need re-authoring** for the same reason: all 170 slug
references still resolve. Pointing the seeded jobs and courses at real NOS codes is still worth
doing, because today no NSQF skill has a single job or course attached to it.

**Matching is the next real sprint** — the payoff, deferred twice. Two things must land with or
before it, and neither exists:
1. **Analytics instrumentation** (`analytics_events`). ADR-025 makes measurement the substitute
   for a revenue signal and nothing currently records anything.
2. **A golden-set evaluation harness** — hand-labelled candidate/job pairs, precision@5 in CI.

Also outstanding: typed `SkillRelation` edges, embeddings, organisation/email login and self-serve
publishing, a real SMS provider, observability, and the ADR-023 encryption path.

## 12a. Measured performance ceiling (audited 2026-09-02)

Load-tested locally. **The bottleneck is Python CPU, not the database.**

- `GET /jobs` — flat at **~137 rps** on one uvicorn worker regardless of
  concurrency; p99 degrades 208ms → 2,192ms from c=10 to c=200.
- `GET /skills/search` — peaks ~420 rps at c=100 then **collapses to 160 rps**.
- The database answers in **1.5 ms** while uvicorn pegs **94.8% of one core**.
- Four workers gave ~255 rps, not 4× (the load generator shares the box, so
  treat all throughput figures as a floor).

**Not ready for 1000 concurrent users.** Fixed in this pass: the four missing
filter indexes. Still outstanding, in order:

1. **No caching.** Redis is present but serves only OTP, refresh tokens and the
   ARQ broker — ADR-020 is unimplemented. The taxonomy is near-static.
2. **Connection pool maths.** 15 connections per process against Postgres
   `max_connections=100` caps you at ~6 processes. PgBouncer before that.
3. **The browsers fetch `limit=200` and filter client-side.** This does not
   degrade with catalogue growth — it stops working.
4. Run uvicorn with multiple workers; it is single-process today.

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

- Two-sided cold start is unsolved; hybrid supply is a bet, not a solution.
- No revenue model, and free may become the permanent default by inertia.
- Multi-sector dilutes GTM focus — a knowing trade, reversible by narrowing GTM only.
- Recommendation quality is **unproven and unmeasured**. Every claim about it is a hypothesis
  until the golden-set harness exists.
- Self-declared skills are unreliable until assessment integration lands.
- Employer-side supply is the weakest link in Indian vocational markets.
- **Two vocabularies now coexist.** 52 curated skills sit alongside 21,303 NSQF units, and for
  concepts like blood sample collection both exist as separate rows. Search returns both. This was
  the price of not breaking five foreign keys and the working demo, and it is a deliberate,
  reversible trade — but it is debt, not a design.
- **The national taxonomy is English-only**, so the Hindi half of ADR-033 currently covers the UI
  chrome and 52 skills, not the 21,303 that matter. Say this plainly.
- **4,732 imported skills belong to no current qualification** and 4,784 have no QP link at all.
  They are real NOS whose qualifications were superseded; they will never surface through sector
  or QP navigation, only through search.
- **Only 45 of 21,303 titles are section-numbered course fragments** ("10.1. Case Studies") but
  they are indistinguishable from real units in the schema. Prominence ordering hides them; it
  does not fix them.
