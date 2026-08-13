# CLAUDE.md

Guidance for Claude Code (and any future contributor) working in this repository.

## Project

**Intelligent Integrated Skill Marketplace (IISM)** — evolving toward a **Workforce Mobility OS**.

A marketplace connecting skills, jobs, courses, and assessments, with an intelligence layer
that matches candidates to opportunities and recommends career paths. India-first,
single-sector rollout for initial validation (ADR-015).

Full architecture rationale lives in [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md)
(23 ADRs, all `Accepted`). Read it before making any structural decision — the summary below
is a condensed index, not a replacement.

## Architecture at a glance

- **Layered system** (ADR-001): Marketplace Layer (CRUD, transactions) + Intelligence Layer
  (AI, graph, scoring). Keep these decoupled — the intelligence layer consumes marketplace
  data, it doesn't own it.
- **Modular monolith** (ADR-014): one deployable app, organized into clearly bounded modules
  under `app/modules/`, so it can be split into microservices later without a rewrite. Don't
  let modules reach into each other's internals — go through their public interface.
- **API-first, REST** (ADR-016): no GraphQL for now. Every capability should be reachable via
  a documented REST endpoint, including internal ones consumed by other modules.
- **Event-driven** (ADR-006): async work (matching, scoring, embeddings) goes through workers,
  not inline in request handlers. Redis/Celery initially, Kafka is a later migration, not a
  day-one dependency.
- **Adapter pattern** (ADR-017): every external system (payment providers, assessment
  providers, Aadhaar verification, government systems) sits behind an adapter in
  `app/adapters/`. Business logic never calls a third-party SDK directly.
- **Hybrid AI** (ADR-005, ADR-018): LLMs (external, not self-hosted/custom-trained) for
  extraction and explanation; deterministic logic for actual decisions (matching, scoring).
  Don't let an LLM call be the thing that decides a match score — it should explain a score
  computed deterministically.

## Tech stack (from the ADR — don't substitute without a new ADR)

| Concern | Choice | ADR |
|---|---|---|
| Backend | Python + FastAPI | ADR-002 |
| Database | PostgreSQL + pgvector | ADR-003 |
| Embeddings | sentence-transformers, stored in pgvector | ADR-013 |
| Async / queues | Redis + Celery (→ Kafka later) | ADR-006 |
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
app/
  main.py              FastAPI app entrypoint
  config.py             Settings (pydantic-settings, env-driven)
  core/                 Cross-cutting: db session, cache, auth/permissions, event bus
  modules/
    identity/           Users, tenants, membership, JWT issuance (ADR-009, ADR-010, ADR-011)
    marketplace/         Jobs, courses, listings, transactions (ADR-001 marketplace layer)
    skills/              NSQF-aligned skill taxonomy / skill graph (ADR-004)
    matching/            Hybrid scoring engine (ADR-007)
    career_paths/        Graph-based role transition engine (ADR-008)
    intelligence/        LLM extraction/explanation, embeddings (ADR-005, ADR-013, ADR-018)
  adapters/              External integrations behind adapter interfaces (ADR-017)
migrations/              Alembic migrations
tests/
docs/adr/                Architecture Decision Records (source of truth for design choices)
scripts/
```

Each module under `app/modules/` should be internally cohesive (its own models, schemas,
service logic, routes) and expose a narrow public interface to the rest of the app. This is
what makes the modular-monolith → microservices path (ADR-014) realistic later.

## Conventions

- Python 3.11+, fully type-hinted, async FastAPI routes and async SQLAlchemy sessions.
- No business logic in route handlers — routes validate input/auth and delegate to a module's
  service layer.
- Every new external dependency (payment, assessment, verification, government API) gets an
  adapter + interface in `app/adapters/`, never a direct SDK call from a module.
- Secrets and config come from environment variables via `app/config.py` (pydantic-settings),
  never hardcoded. See `.env.example` for the expected variables.
- Anything touching Aadhaar data, resumes, or assessment results must go through the
  encryption path described in ADR-023 — don't persist that data in plaintext, including in
  logs.
- New architectural decisions (new datastore, new auth model, new AI approach, etc.) get a new
  ADR entry in `docs/adr/architecture-decisions.md`, not a silent divergence from the existing
  ones.

## MVP scope

Not yet defined in code — this skeleton establishes structure and tooling only. The next step
is scoping which modules/features are in the first sellable slice (see repo README for status).
Do not assume every module listed above ships in v1; confirm scope before building out a
module's business logic.

## Local development

See [README.md](README.md) for setup (Docker Compose for Postgres/Redis, running the app,
running tests).
