# Intelligent Integrated Skill Marketplace (IISM)

A marketplace connecting candidates, vocational courses and vocational jobs, with an
intelligence layer that decomposes all three into NSQF-aligned skills so the system can compute
what a person is missing for the work they want, and which training closes that gap.

India-first, Hindi and English at launch. See
[docs/IISM-Product-Definition.docx](docs/IISM-Product-Definition.docx) for what we are building
and [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md) for the 34 ADRs
that govern how.

## Status — Sprints 1–8 complete

**Sprint 8 — the national NSQF corpus.** 4,424 qualification packs, 21,303 National Occupational
Standards, 1,808 occupations and 106 awarding bodies, plus Indian administrative geography — 36
states, 766 districts, 7,100 sub-districts. Open a standard and see what it actually requires:
238,370 performance criteria with their marks, 185,559 knowledge parameters, and the
qualifications that use it with each one's own NSQF level. Open a qualification and see the
alternative ways in — "12th grade Pass with no experience" or "10th grade pass with three years".

Two honest caveats. The corpus is **English-only**: the source contains no Devanagari, so Hindi
covers the interface and the 52 hand-curated skills, not the imported ones. And those 52 curated
skills were kept alongside the national taxonomy, so a handful of concepts exist as two rows.

**Sprint 5 — rich candidate profile.** Work history, education, certifications, languages, target
roles and preferred locations, plus job preferences and optional personal details. First visit is a
guided 5-step wizard; after that it is a sectioned editor with a completeness meter that names the
most valuable thing to add next.

**Sprint 4 — identity and candidate profiles.** Passwordless sign-in with a phone number and a
6-digit code. Build a profile and declare skills against the taxonomy — search in English, Hindi
or transliteration. No SMS provider needed in development: the code is returned by the API and
shown on screen.

**Sprint 3 — marketplace.** 8 organisations, 20 jobs and 20 courses, all bilingual and expressed
as the skills they require or teach. Open any skill and see both the jobs that need it and the
courses that teach it — the taxonomy is now a navigable graph rather than a glossary.

**Sprint 2 — skill taxonomy.** 52 bilingual skills, 149 aliases, and search that resolves a
skill however a real person types it: English, Devanagari, or Hindi in Latin script. Try
`khoon nikalna` at `/skills` — it finds "Blood sample collection" and tells you why it matched.
These 52 remain the only skills with Hindi names and aliases; see the Sprint 6 caveat above.

**Sprint 1 — walking skeleton.** Every architectural layer exists and is connected.

| | |
|---|---|
| ✅ Postgres 16 + pgvector, Redis 7 | via Docker Compose |
| ✅ FastAPI, async end to end | health, deep health, demo task endpoints |
| ✅ Alembic | migration 0001 enables pgvector |
| ✅ ARQ worker | heartbeat-based liveness (ADR-027) |
| ✅ Next.js PWA | mobile-first, Hindi + English |
| ✅ Generated TypeScript client | from the OpenAPI schema |
| ✅ pytest + testcontainers, CI | disposable Postgres/Redis per run |

**Visible deliverables:** the homepage at `localhost:3000/en` (and `/hi`), browsers at `/skills`,
`/jobs` and `/courses`, sign-in at `/signin`, the candidate profile at `/profile`, and the System
Status panel at the foot of the homepage.

Not yet built: matching, Hindi for the imported corpus, a concept layer over duplicated unit names,
organisation/email login, self-serve publishing, a real SMS provider, typed skill relations,
embeddings, analytics instrumentation.

## Prerequisites

- Docker Desktop (running) — Postgres, Redis and MongoDB all run in containers
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node 24 (`nvm install 24`)

## Setup

```bash
cp .env.example .env
make install
make up
make migrate
make seed
```

`make seed` loads the skill taxonomy and the marketplace inventory. It is idempotent — run it
as often as you like.

To load the national NSQF corpus, put it in MongoDB as `iism_nsqf_master_data` and run:

```bash
make import-nsqf
```

Takes about 90 seconds and is idempotent: it upserts on the national codes, keeps only the current
version of each, and prints a summary with counts plus anything it could not import. Everything
works without it — you simply get the 52 curated skills instead of 21,303.

The importer deliberately **does not read the `ssc` collection**: it is a portal account registry
holding personal contact details and bank accounts, and the `sectors` collection supplies the same
organisations with better coverage and no personal data. See
[docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md).

## Run

Three processes, three terminals:

```bash
make api
```

```bash
make worker
```

```bash
make web
```

Then open **http://localhost:3000** — it redirects to `/en`. All four status cards should be
green. "Run test task" enqueues a real background job through Redis; the worker picks it up and
the result appears in the UI.

`make help` lists every target.

## Verify

```bash
make check
```

Runs Ruff, mypy and the test suite. Tests start their own throwaway Postgres and Redis
containers, so they never touch your development data and behave identically in CI.

## Notes

- Host ports are **5433** (Postgres), **6380** (Redis) and **27018** (MongoDB) so pre-existing
  local installs are left alone.
- MongoDB is pinned to **7.0**. 8.0 will not start on this Docker VM's kernel (SERVER-121912).
- NSQF levels are `Numeric(3,1)` everywhere, including in Pydantic schemas. The framework uses
  half-levels and 4.5 alone accounts for 6,532 skills.
- After changing any API endpoint, run `make gen-api` to regenerate the TypeScript client.
- Configuration is always read through `get_settings()`. Never bind `settings` at module import
  time — it cannot then be overridden, and tests silently hit the wrong database.
