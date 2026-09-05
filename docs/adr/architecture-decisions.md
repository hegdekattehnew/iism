# Architecture Decision Records — Intelligent Integrated Skill Marketplace

> Workforce Mobility OS — CTO Office, March 2026

> Source: `Intelligent_Integrated_Skill_Marketplace - ADR.xlsx` (converted to Markdown for version control)

> **Amendment record.** ADR-001 to ADR-023 originate from the March 2026 source spreadsheet.
> ADR-024 to ADR-033 were added in September 2026 to record decisions the original set left open —
> concrete stack choices, monetization, supply acquisition, credential model and language scope.
> ADR-034 was added when real NSQF data arrived.
>
> Changes to the original set:
> - **ADR-014** — `Status` was malformed in the source conversion; corrected to `Accepted`.
> - **ADR-015** — superseded by ADR-024. India-first is retained; the single-sector constraint is withdrawn.
> - **ADR-023** — `Final decision` was empty in the source; now resolved.
> - **ADR-006** — amended by ADR-027 (task runner implementation only; the principle stands).
> - **ADR-023** — complemented by ADR-035 (what not to collect, as against what to protect).
> - **ADR-021** — qualified by ADR-033 for Hindi-language search.
> - **ADR-003** — qualified by ADR-034. Its rejection of a second store for *vector search* stands
>   and pgvector is unchanged; ADR-034 adds a document store for *source data* only.

## ADR-001: Overall Product Architecture

**Status:** Accepted

**Context:** System needs to support marketplace initially and evolve into workforce mobility OS with intelligence layer.

**Decision:** Adopt layered architecture:
1. Marketplace Layer (CRUD, transactions)
2. Intelligence Layer (AI + graph + scoring)

**Options considered:** 1. Monolithic marketplace
2. Layered architecture (marketplace + intelligence)

**Trade-offs:**

- Option 1: ✅ Faster to build
❌ Hard to scale intelligence
❌ Tight coupling

- Option 2: ✅ Clean separation
✅ Scalable AI evolution
❌ Slightly higher initial complexity

**Final decision:** Layered architecture


---

## ADR-002: Backend Technology Stack

**Status:** Accepted

**Context:** Need scalable, AI-friendly backend

**Decision:** Use Python + FastAPI

**Options considered:** 1. Node.js
2. Python + FastAPI

**Trade-offs:**

- Option 1: ✅ Good ecosystem
❌ Weak for ML/AI

- Option 2: ✅ Strong AI ecosystem
✅ Faster prototyping
❌ Slight performance tradeoff

**Final decision:** Python + FastAPI


---

## ADR-003: Database Choice

**Status:** Accepted

**Context:** Need relational + vector search capability

**Decision:** Use PostgreSQL + pgvector

**Options considered:** 1. PostgreSQL + pgvector
2. Separate DB (Postgres + Pinecone/Weaviate)

**Trade-offs:**

- Option 1: ✅ Single DB
✅ Lower complexity
❌ Limited scaling initially

- Option 2: ✅ Scalable vector search
❌ More infra complexity

**Final decision:** PostgreSQL + pgvector


---

## ADR-004: Skill Taxonomy

**Status:** Accepted

**Context:** Need structured skill graph aligned to Indian ecosystem

**Decision:** Adopt NSQF-aligned skill taxonomy with multi-framework support

**Options considered:** 1. Custom taxonomy
2. NSQF-aligned

**Trade-offs:**

- Option 1: ✅ Flexible
❌ No standardization

- Option 2: ✅ Govt alignment
✅ Credibility
❌ Initial complexity

**Final decision:** NSQF-aligned, framework-agnostic design


---

## ADR-005: AI Strategy

**Status:** Accepted

**Context:** Need AI for extraction, matching, and explanation

**Decision:** Use hybrid AI:
1. LLM for extraction & explanation
2. Deterministic logic for decision-making

**Options considered:** 1. Full LLM-driven system
2. Hybrid system

**Trade-offs:**

- Option 1: ✅ Fast to build
❌ Unstable
❌ Non-explainable

- Option 2: ✅ Reliable
✅ Explainable
❌ More engineering effort

**Final decision:** Hybrid AI architecture


---

## ADR-006: Event-Driven Architecture

**Status:** Accepted

**Context:** Need async processing for matching, scoring, embeddings

**Decision:** Adopt event-driven architecture with async workers

**Options considered:** 1. Synchronous APIs
2. Event-driven

**Trade-offs:**

- Option 1: ✅ Simpler
❌ Not scalable

- Option 2: ✅ Scalable
✅ Decoupled
❌ Operational complexity

**Final decision:** Event-driven (Redis/Celery initially → Kafka later)


---

## ADR-007: Matching Engine Design

**Status:** Accepted

**Context:** Need accurate job-candidate matching

**Decision:** Hybrid scoring:
1. Skill overlap (primary)
2. Semantic similarity
3. Experience

**Options considered:** 1 .Keyword matching
2. LLM-based matching
3. Hybrid scoring

**Trade-offs:**

- Option 1: ❌ Low accuracy

- Option 2: ❌ Expensive
❌ Non-deterministic

- Option 3: ✅ Balanced
✅ Explainable

**Final decision:** Hybrid deterministic scoring


---

## ADR-008: Career Path Engine

**Status:** Accepted

**Context:** Need workforce mobility intelligence

**Decision:** Graph-based role transition engine

**Options considered:** 1 .Static recommendations
2. Graph traversal

**Trade-offs:**

- Option 1: ❌ Limited

- Option 2: ✅ Dynamic
✅ Scalable

**Final decision:** Graph-based engine


---

## ADR-009: Authentication Architecture

**Status:** Accepted

**Context:** Need common auth across products

**Decision:** Centralized identity service with JWT

**Options considered:** 1. Per-product auth
2. Central auth

**Trade-offs:**

- Option 1: ❌ Duplication

- Option 2: ✅ Reusable
✅ Scalable

**Final decision:** Central auth service


---

## ADR-010: Multi-Tenant Design

**Status:** Accepted

**Context:** Future B2B2C requirement

**Decision:** Global users + tenant + membership model

**Options considered:** 1. Single-tenant
2. Multi-tenant

**Trade-offs:**

- Option 1: ❌ Not scalable

- Option 2: ✅ Flexible
✅ Enterprise-ready

**Final decision:** Multi-tenant from Day 1


---

## ADR-011: Identity Model

**Status:** Accepted

**Context:** Need stable identity layer

**Decision:** Use UUID as primary identity; Aadhaar as optional verification

**Options considered:** 1 .Aadhaar as primary ID
2. UUID + verification layer

**Trade-offs:**

- Option 1: ❌ Compliance risk

- Option 2: ✅ Safe
✅ Flexible

**Final decision:** UUID-based identity


---

## ADR-012: RBAC vs ABAC

**Status:** Accepted

**Context:** Access control complexity will grow.

**Decision:** Start with RBAC, design for ABAC

**Options considered:** 1. RBAC only
2. RBAC + ABAC

**Trade-offs:**

- Option 1: ❌ Limited

- Option 2: ✅ Scalable

**Final decision:** RBAC → ABAC evolution


---

## ADR-013: Embedding Strategy

**Status:** Accepted

**Context:** Need semantic matching.

**Decision:** Use sentence-transformers + pgvector

**Options considered:** 1 .External vector DB
2. pgvector

**Trade-offs:**

- Option 1: ❌ Cost

- Option 2: ✅ Simpler

**Final decision:** pgvector


---

## ADR-014: Deployment Strategy

**Status:** Accepted

**Context:** Need scalable infra

**Decision:** Start with modular monolith → evolve to microservices

**Options considered:** 1. Microservices from start
2. Modular monolith

**Trade-offs:**

- Option 1: ❌ Overhead

- Option 2: ✅ Faster
✅ Controlled complexity

**Final decision:** Modular monolith


---

## ADR-015: Target Market Strategy

**Status:** Superseded by ADR-024 (September 2026)

**Context:** Need focused GTM

**Decision:** India-first, single-sector rollout

**Options considered:** 1. Multi-sector
2. Single sector

**Trade-offs:**

- Option 1: ❌ Diffused

- Option 2: ✅ Faster validation

**Final decision:** Single sector (initial) — **superseded by ADR-024.** India-first is retained and
unaffected; only the single-sector constraint is withdrawn.


---

## ADR-016: API Architecture

**Status:** Accepted

**Context:** Need consistency across all products and future external integrations

**Decision:** API-first architecture using REST initially.

**Options considered:** 1. REST only
2. GraphQL
3. REST + GraphQL

**Trade-offs:**

- Option 1: First users are:
1. Lovable
2. React
3. Internal services

- Option 2: GraphQL adds complexity with limited value initially

**Final decision:** REST-first


---

## ADR-017: Integration Architecture

**Status:** Accepted

**Context:** Future integrations with:
1. Assessment providers
2. Payment providers
3. Aadhaar verification
4. Government systems

**Decision:** All external systems accessed through provider adapters.

**Options considered:** Adapter pattern

**Final decision:** Adapter pattern


---

## ADR-018: AI Model Strategy

**Status:** Accepted

**Context:** Clarity on build vs buy.

**Decision:** Use external LLMs.

**Options considered:** 1. Build custom LLM
2. Use external LLMs
3. Hybrid

**Trade-offs:**

- Option 1: Cost and Time

- Option 2: ✅ Faster
✅ Simpler

- Option 3: Cost, Time and Complexity

**Final decision:** Use external LLMs.


---

## ADR-019: Observability Strategy

**Status:** Accepted

**Context:** Need production support

**Decision:** Adopt:
Structured logging
Metrics
Distributed tracing

**Final decision:** OpenTelemetry
Prometheus
Grafana


---

## ADR-020: Caching Strategy

**Status:** Accepted

**Context:** Match scores and skill lookups will be expensive

**Decision:** Redis-based caching

**Final decision:** Redis-based caching


---

## ADR-021: Search Architecture

**Status:** Accepted

**Context:** Users will search:
Jobs
Courses
Skills

**Decision:** PostgreSQL search

**Options considered:** 1. PostgreSQL search
2. Elasticsearch/OpenSearch

**Final decision:** Start PostgreSQL FTS.
Move to OpenSearch later


---

## ADR-022: Authorization Scope

**Status:** Accepted

**Context:** Need consistent permissions

**Decision:** Permission-based authorization

**Options considered:** 1. Role-only authorization
2. Permission-based authorization

**Trade-offs:**

- Option 1: ❌ Limited

- Option 2: ✅ Safe
✅ Flexible
✅ Scalable

**Final decision:** Permission-based authorization


---

## ADR-023: Data Privacy & Compliance

**Status:** Accepted

**Context:** Potentially handling:
1. Aadhaar verification
2. Resumes
3. Assessment results

**Decision:** Encrypted data

**Options considered:** 1. Application-level encryption of sensitive fields
2. Database/disk-level encryption only
3. No encryption, access control only

**Trade-offs:**

- Option 1: ✅ Protects against DB compromise, backup leakage and operator access
✅ Explicit, auditable boundary
❌ Key management burden
❌ Encrypted columns are not searchable

- Option 2: ✅ Nearly free to enable
❌ Anyone with DB access reads plaintext
❌ Does not satisfy a data-protection audit on its own

- Option 3: ❌ Unacceptable for Aadhaar and biometric-adjacent data

**Final decision:** Field-level application encryption for Aadhaar numbers, resume documents and
their extracted text, and assessment results. AES-256-GCM envelope encryption, data keys wrapped by
a managed KMS; keys never live in application config or environment variables. Ciphertext at rest,
decrypted only in the service layer at the point of use. These fields are excluded from logs,
traces, error payloads and analytics events by an explicit redaction filter — plaintext must never
reach a log sink. Object storage holding resumes and certificates uses server-side encryption under
the same key hierarchy. Data resides in the India region (see ADR-028) to meet DPDP Act 2023
residency expectations. Vector embeddings derived from resume text are treated as sensitive
material in their own right, since embeddings are partially invertible; they inherit the same
access controls as their source document.


---

## ADR-024: Sector Rollout Scope

**Status:** Accepted (September 2026)

**Context:** ADR-015 committed to a single-sector rollout for faster validation. Subsequent product
direction prioritises building the NSQF skill taxonomy as shared base data first. The taxonomy is
the substrate every other capability sits on — matching, career paths, course-to-job alignment —
and it is sector-agnostic by construction. Constraining it to one sector would not make it
meaningfully cheaper to build, but would make the eventual expansion a migration rather than a data
load.

**Decision:** Multi-sector from the outset, taxonomy-first. Supersedes ADR-015.

**Options considered:** 1. Retain single-sector rollout per ADR-015
2. Multi-sector with a sector-agnostic taxonomy and generic ingestion

**Trade-offs:**

- Option 1: ✅ Focused GTM and a narrow cohort to validate against
✅ Lower content-operations cost at launch
❌ Taxonomy would need re-work to generalise later
❌ Little cost saving, since the schema is sector-agnostic either way

- Option 2: ✅ Base data built once, correctly
✅ No sector-specific branching enters the codebase
❌ Larger upfront data-acquisition effort
❌ No narrow cohort to validate against — dilutes GTM focus

**Final decision:** Multi-sector rollout. The taxonomy schema and the ingestion pipeline are
sector-agnostic and generic; no sector-specific logic is permitted in application code. Sectors are
onboarded incrementally as source data becomes available, with three to four Sector Skill Councils
seeded first to prove the pipeline. "All sectors" is a property of the schema and importer, not a
day-one data-entry commitment. India-first (ADR-015) is retained.


---

## ADR-025: Monetization Model

**Status:** Accepted (September 2026)

**Context:** No prior ADR addressed revenue. Direction is B2C first, graduating to B2B2C. Direct
willingness-to-pay among Indian vocational candidates is typically very low, and the product's
core claim — recommendation quality — is unproven. Building billing infrastructure before that
claim is validated risks investing in the wrong revenue model.

**Decision:** v1 is free to all actors. The revenue model is deferred pending traction data.

**Options considered:** 1. Candidate freemium subscription at launch
2. Course-provider referral commission at launch
3. Employer-pays candidate access
4. Free v1, monetization deferred and instrumented

**Trade-offs:**

- Option 1: ✅ Direct revenue signal
❌ Requires payment integration and entitlements before product-market fit
❌ Low willingness-to-pay in the target cohort

- Option 2: ✅ Realistic for the Indian market
❌ Requires enrollment attribution built before there is enrollment volume

- Option 3: ✅ Where the money actually is
❌ Contradicts the B2C-first sequencing

- Option 4: ✅ No billing code written against an unvalidated model
✅ Forces measurement to exist before monetization
❌ No revenue and no pricing signal during v1

**Final decision:** Free v1, no billing implementation. Payment integration exists as an adapter
interface only (per ADR-017), unimplemented. Because nobody pays, instrumentation is the substitute
for a revenue signal and is mandatory, not optional: recommendation precision@5 against a
hand-labelled golden set, candidate-to-course click-through, and provider-reported enrollment
conversion. A successor ADR is required before any billing code is written, and must cite those
metrics.


---

## ADR-026: Supply Acquisition Strategy

**Status:** Accepted (September 2026)

**Context:** Recommendations are worthless without job and course inventory. The platform faces a
classic two-sided cold start: candidates will not come without opportunities, and providers will
not publish without candidates.

**Decision:** Hybrid — operations-curated seeding alongside provider self-serve publishing.

**Options considered:** 1. Manual operations seeding only
2. Provider self-serve only
3. Aggregate public listings
4. Hybrid: seeding plus self-serve

**Trade-offs:**

- Option 1: ✅ Highest data quality, no integration build, fastest to a working demo
❌ Does not scale

- Option 2: ✅ Scales, and is the long-term model
❌ Requires business development to land before any inventory exists

- Option 3: ✅ Volume quickly
❌ Untagged to NSQF, messy, and legally grey depending on source

- Option 4: ✅ Launch inventory exists while the scalable path is built in parallel
❌ More build up front; two ingestion paths to maintain

**Final decision:** Hybrid. Operations seeds launch inventory through an internal curation path,
while tenant-scoped self-serve publishing APIs are built in parallel so partners can contribute as
business development lands. Both paths write through the same service layer and validation rules —
seeded and self-serve inventory must be indistinguishable downstream.


---

## ADR-027: Async Task Runner

**Status:** Accepted (September 2026)

**Context:** ADR-006 specified Redis + Celery for asynchronous work. The application is
asynchronous end to end — FastAPI with async route handlers and async SQLAlchemy sessions. Celery
is synchronous-first; running it against this stack requires a second, synchronous database engine,
duplicated session management, and event-loop workarounds inside task bodies.

**Decision:** Use ARQ as the task runner. Amends ADR-006.

**Options considered:** 1. Celery, as originally specified
2. ARQ
3. Dramatiq

**Trade-offs:**

- Option 1: ✅ Largest ecosystem, most operational precedent
❌ Sync-first; forces a parallel sync DB engine and session layer
❌ Async support is bolted on and awkward

- Option 2: ✅ Asyncio-native; shares the application's existing session machinery directly
✅ Redis-backed, small surface area
❌ Smaller ecosystem and fewer operational integrations

- Option 3: ✅ Simpler than Celery, good ergonomics
❌ Also sync-first

**Final decision:** ARQ. The Redis broker is unchanged and the eventual Kafka migration path in
ADR-006 is unaffected — this amends the implementation choice only; the event-driven principle and
the requirement that async work never run inline in request handlers both stand. Decided before any
tasks were written, when the switching cost is zero.


---

## ADR-028: Cloud Platform and Deployment Topology

**Status:** Accepted (September 2026)

**Context:** ADR-014 settles the modular-monolith shape but names no hosting platform. The system
will hold Aadhaar verification data, resumes and assessment results (ADR-023), making India data
residency under the DPDP Act 2023 a hard constraint. Government-sector credibility (ADR-004) also
carries procurement expectations.

**Decision:** AWS `ap-south-1` (Mumbai), ECS Fargate, infrastructure defined in Terraform.

**Options considered:** 1. AWS ap-south-1 on ECS Fargate
2. GCP asia-south1 on Cloud Run
3. Managed PaaS (Render, Railway, Fly)
4. Kubernetes (EKS/GKE)

**Trade-offs:**

- Option 1: ✅ India residency; managed containers without Kubernetes overhead
✅ Strongest position in Indian government and enterprise procurement
✅ Widest India talent pool
❌ More expensive than scale-to-zero alternatives at low traffic

- Option 2: ✅ Cheapest at low volume, excellent developer experience
❌ Weaker procurement story in this market

- Option 3: ✅ Fastest to deploy, near-zero operational burden
❌ Most have no India region — a direct DPDP problem once real candidate data lands

- Option 4: ✅ Maximum portability, aligns with the ADR-014 microservices endgame
❌ Substantial operational burden for a pre-revenue team

**Final decision:** AWS `ap-south-1` throughout. ECS Fargate running an `api` service and a `worker`
service behind an Application Load Balancer; RDS PostgreSQL 16 with pgvector; ElastiCache Redis; S3
with SSE-KMS for documents; Secrets Manager for secrets. All infrastructure is defined in Terraform
— no console configuration. CI authenticates to AWS via GitHub Actions OIDC; no long-lived access
keys exist.


---

## ADR-029: Client Architecture

**Status:** Accepted (September 2026)

**Context:** ADR-016 names "Lovable, React, internal services" as API consumers but does not decide
what is actually built. The primary user cohort is India-first vocational candidates: predominantly
low-end Android devices, constrained mobile data, frequently not English-first. With no revenue in
v1 (ADR-025), organic search is the cheapest acquisition channel available.

**Decision:** A single Next.js progressive web application, mobile-first.

**Options considered:** 1. Next.js PWA, mobile-first
2. React SPA (Vite), native app later
3. Next.js web plus Flutter mobile from day one
4. Generated frontend (Lovable) to start

**Trade-offs:**

- Option 1: ✅ One codebase; installable without app-store friction
✅ Server rendering gives job and course pages organic search visibility
❌ Less capable than native on very constrained devices

- Option 2: ✅ Simpler build
❌ Loses server rendering, and with it the cheapest acquisition channel

- Option 3: ✅ Best experience on low-end Android
❌ Two clients to maintain pre-revenue; install friction for first-time users

- Option 4: ✅ Fastest to a demoable interface
❌ Would be rebuilt before any real launch

**Final decision:** Next.js (App Router) with React and TypeScript, delivered as an installable PWA
with aggressive payload budgets for low-end Android. The TypeScript API client is generated from the
FastAPI OpenAPI schema, which keeps ADR-016's REST-first, fully-documented requirement honest and
the types permanently synchronised. A native client is deferred until traction justifies it.


---

## ADR-030: Identity Implementation — Build versus Buy

**Status:** Accepted (September 2026)

**Context:** ADR-009 mandates a centralized identity service issuing JWTs but does not decide
whether it is built or bought. The requirements are unusual in combination: eight actor types, a
global-user plus tenant plus membership model from day one (ADR-010), shell accounts for
bulk-imported candidates who claim them later, API-key service accounts for external system
intake, and optional Aadhaar verification (ADR-011) subject to ADR-023 encryption.

**Decision:** Build the identity service in-house.

**Options considered:** 1. Build in-house
2. Keycloak, self-hosted
3. Managed provider (Auth0, Clerk, WorkOS)
4. Supabase Auth

**Trade-offs:**

- Option 1: ✅ The tenant/membership model, shell-account claim flow and service accounts fit natively
✅ Aadhaar and DPDP-governed data stay entirely under our control
❌ Roughly two sprints of build, and security-sensitive code we own forever

- Option 2: ✅ Free, OIDC-standard, realms map reasonably to tenants
❌ Heavy JVM service to operate; bulk-import shell accounts need custom extensions anyway

- Option 3: ✅ Fastest to working login, MFA and social sign-in included
❌ Per-MAU pricing is punitive with free B2C candidates
❌ India residency and Aadhaar handling are difficult on a foreign vendor

- Option 4: ✅ Cheap, Postgres-native
❌ Couples identity to a vendor with no India region

**Final decision:** Build in-house. The combination of requirements defeats the off-the-shelf
options, and the per-monthly-active-user pricing of managed providers is structurally wrong for a
free consumer product (ADR-025). Standard primitives — password hashing, JWT signing, OTP
generation — use vetted libraries; no cryptography is hand-rolled.


---

## ADR-031: AI Provider Abstraction and Embedding Dimensionality

**Status:** Accepted (September 2026)

**Context:** ADR-018 requires external LLMs with no self-hosting or fine-tuning, and ADR-013
requires sentence-transformers embeddings stored in pgvector, but neither names a provider. Model
pricing and quality move quickly, and ADR-017 requires every external system to sit behind an
adapter. A non-obvious constraint applies: pgvector's HNSW index requires a fixed column dimension,
while providers differ natively — MiniLM is 384, OpenAI `text-embedding-3-small` is 1536, Gemini is
768. Without a common dimension, changing embedding provider means a schema migration plus a full
corpus re-embed, which defeats the purpose of the abstraction.

**Decision:** `LLMProvider` and `EmbeddingProvider` adapter protocols with multiple
implementations, and a platform embedding dimension pinned at 384.

**Options considered:** 1. Single provider, called directly
2. Adapter protocols, dimension unpinned
3. Adapter protocols, dimension pinned at 384

**Trade-offs:**

- Option 1: ✅ Simplest
❌ Violates ADR-017; vendor lock-in on a fast-moving market

- Option 2: ✅ Swappable LLMs
❌ Embedding providers remain effectively locked in by the schema

- Option 3: ✅ Genuinely swappable embedding providers with no schema change
✅ Enables shadow-running a candidate model against production traffic
❌ Forfeits any quality gain from higher-dimensional embeddings

**Final decision:** Two adapter protocols. `LLMProvider` (`complete`, `extract_structured`) with
Anthropic as the default implementation, plus OpenAI and Gemini. `EmbeddingProvider` (`embed`) with
self-hosted sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` as the default — 384
dimensions, CPU-only, free at inference, and multilingual, which ADR-033 makes load-bearing.

Every adapter must emit 384-dimension vectors. 384 is chosen because it is MiniLM's native size and
because both OpenAI `text-embedding-3-*` and Gemini support Matryoshka dimension reduction to it via
an API parameter — so all three providers are interchangeable without touching the schema. Any other
choice silently breaks the abstraction. Every stored vector records the provider, model identifier
and model version that produced it, so a shadow model can be run during migration and no vector's
provenance is ever ambiguous. Consistent with ADR-005, embeddings contribute to a deterministic
score; no LLM decides a match.


---

## ADR-032: Primary Credential by Actor Type

**Status:** Accepted (September 2026)

**Context:** ADR-009 and ADR-011 describe an email-centric identity — email and password, Google
OAuth, email verification, email password reset. This is a poor fit for the primary user cohort.
India-first vocational candidates are phone-first; many have no regularly used email address, and
Google OAuth presumes an account they may not hold. Organizational actors — employers, course
providers, assessment providers, government agencies, platform staff — are reliably email-native and
will expect email and eventually SSO.

**Decision:** Phone with one-time passcode for candidates; email and password for organizational
actors. Both linkable on a single account.

**Options considered:** 1. Email-first for all actors, per ADR-009 as written
2. Phone and OTP for all actors
3. Phone/OTP for candidates, email for organizations
4. Email primary with phone as a second factor

**Trade-offs:**

- Option 1: ✅ Cheapest build; no SMS vendor or per-message cost
❌ A signup wall for precisely the candidates the product exists to serve

- Option 2: ✅ One authentication path to build and reason about
❌ Organizational users expect email and SSO; weakens the eventual B2B2C story

- Option 3: ✅ Matches how each cohort actually behaves
❌ Two authentication paths to build, test and secure

- Option 4: ✅ Preserves the existing ADR-009 design
❌ Does not solve the problem; candidates without email still cannot register

**Final decision:** Dual credential. The user record carries both phone and email as independently
nullable, independently verified, independently unique identifiers — neither is mandatory, and the
UUID remains the primary key per ADR-011. Both login paths converge on a single token issuance
path, so nothing downstream of authentication knows or cares which was used. Which credential is
required is determined by actor type at registration, in the service layer, not scattered across
route handlers.

This promotes SMS to the critical path: one-time passcode delivery becomes a login availability
concern rather than a notification convenience. It requires per-phone rate limiting, a second SMS
provider configured for failover behind the same adapter (ADR-017), and DLT registration for Indian
transactional messaging. The bulk-import shell-account claim flow becomes SMS-first for candidates,
keyed on phone rather than email.


---

## ADR-033: Language Scope at Launch

**Status:** Accepted (September 2026)

**Context:** The product is India-first with later global adaptation. The candidate cohort is
substantially not English-first. ADR-021 specifies PostgreSQL full-text search, and ADR-004
specifies an NSQF-aligned taxonomy whose source material is largely English-only.

**Decision:** Hindi and English both live at launch.

**Options considered:** 1. English only, internationalisation deferred
2. English at launch, internationalisation scaffolded
3. Hindi and English at launch
4. Hindi, English and two to three regional languages at launch

**Trade-offs:**

- Option 1: ✅ Leanest v1
❌ Retrofitting internationalisation is an expensive refactor

- Option 2: ✅ Cheap now, inexpensive to extend later
❌ Launches without reach into much of the intended cohort

- Option 3: ✅ Real reach into the actual candidate base from day one
❌ Roughly doubles content operations; adds translation QA to every sprint

- Option 4: ✅ Widest reach; strongest government-partnership position
❌ Substantial recurring translation cost with no revenue

**Final decision:** Hindi and English at launch. Locale routing, externalised strings and
Devanagari-capable typography are day-one requirements in the client (ADR-029). Translated content
is modelled as first-class fields rather than bolted on later. First-pass translation of seeded job,
course and NSQF skill content uses the LLM adapter already required by ADR-031, with human review —
translation is not sourced as a separate workstream.

Two consequences are recorded explicitly. First, this makes the multilingual embedding model in
ADR-031 load-bearing rather than a hedge. Second, it partially undercuts ADR-021: PostgreSQL ships
no Hindi text-search configuration — no stemmer and no stopword list. Hindi will be indexed using
the `simple` configuration together with `pg_trgm` for fuzzy matching, leaning on pgvector semantic
search to carry Hindi relevance. This must be validated early, and may pull ADR-021's OpenSearch
migration forward.


---

## ADR-034: NSQF Source of Record

**Status:** Accepted (September 2026)

**Context:** The skill taxonomy has until now been 52 hand-curated rows, sufficient to prove
search and matching shape but not a national taxonomy and not defensible to an employer or a
regulator. Real NSQF data — Qualification Packs and National Occupational Standards with aligned
levels — now exists in MongoDB, covering all Sector Skill Councils and on the order of ten
thousand NOS.

That data is hierarchical, versioned and irregular: Qualification Packs are revised and re-issued,
a NOS may be shared across several QPs, and field coverage differs between Sector Skill Councils.
It is a poor fit for a relational schema in its raw form and a natural fit for document storage.

The question is not where the data can be stored but **which store is authoritative**, and
whether the application reads it directly.

**Decision:** MongoDB is the source of record for the raw NSQF feed. PostgreSQL remains the
operational store, into which the feed is projected by an importer. The relationship is
one-directional and the projection is re-runnable.

**Options considered:** 1. PostgreSQL only — import once, then retire MongoDB
2. MongoDB as the live operational store for the taxonomy
3. MongoDB as master of the raw feed, PostgreSQL as the operational projection

**Trade-offs:**

- Option 1: ✅ Single datastore, nothing new to operate
✅ Fully consistent with ADR-003
❌ The raw source is lost; re-deriving after a mapping error means sourcing the data again
❌ Discards the natural home for versioned, irregular QP/NOS documents

- Option 2: ✅ Matches the intuition that NSQF data "lives" in MongoDB
❌ Five foreign keys point at `skills.id` — `job_skills`, `course_skills`, `candidate_skills`,
`candidate_certifications`, `skill_aliases` — and foreign keys cannot span datastores; every one
becomes an application-enforced reference with no integrity
❌ Matching joins skills against jobs and candidates; a cross-store join executes in Python, and
measured load testing puts the ceiling at ~137 requests per second on Python CPU while PostgreSQL
answers the same query in 1.5 ms
❌ Embeddings must sit beside the skill rows for HNSW search (ADR-013, ADR-031)

- Option 3: ✅ Each store does what it is good at: documents for the versioned source, relational
for the operational graph
✅ Every existing foreign key and index survives untouched
✅ PostgreSQL can be rebuilt from MongoDB at any time, which is what makes MongoDB the master
rather than merely a staging area
❌ A second datastore to run, back up and secure
❌ Two representations that can drift if the importer is not re-run

**Final decision:** MongoDB is master of the raw NSQF feed; PostgreSQL is the operational
projection. Four constraints make this a bounded exception rather than a general licence to add
datastores:

1. **The application never reads MongoDB at request time.** Only the importer opens a connection.
   Any endpoint reading MongoDB directly is a defect, not an extension of this decision.
2. **The projection is re-runnable and idempotent**, keyed on `qp_code` and `nos_code` and aware
   of version. PostgreSQL holds no NSQF state that cannot be regenerated.
3. **Access sits behind an adapter** in `api/adapters/nsqf/` per ADR-017. No module imports a
   MongoDB driver, and a file-based source implementation keeps the test suite free of MongoDB.
4. **This applies to NSQF source data only.** It is not a precedent for candidate, job, course or
   identity data, all of which remain relational.

This qualifies ADR-003 rather than superseding it. ADR-003 rejected a second store for *vector
search* and that reasoning is untouched — pgvector remains the vector store, adjacent to the rows
it indexes. What is added here is a second store for *source data*, a different axis, and the
operational database is still one.

Two operational notes are recorded because they cost time to discover. MongoDB is pinned to
**7.0**: version 8.0 refuses to start on Linux kernel 6.19 and newer (SERVER-121912), which
includes the Linux VM that Docker Desktop runs on macOS. And the container is exposed on host port
**27018** rather than 27017, following the same convention as PostgreSQL on 5433 and Redis on
6380, so a pre-existing local installation is never disturbed.


---

## ADR-035: Selective Ingestion of the NSQF Master Data

**Status:** Accepted (September 2026)

**Context:** The NSQF master data arrived in MongoDB as seven collections. Six describe the
framework — qualifications, standards, curricula, sectors, states, districts. The seventh, `ssc`,
does not: it is a portal account registry holding **4,027 email addresses, 4,042 mobile numbers,
2,129 personal names, and 50 bank account numbers with IFSC codes and account-holder names**, of
which 3,547 of 4,053 rows are incomplete registrations at `status='init'`.

It was initially assumed to be the Sector Skill Council master, and the obvious reading of "import
the master data" is to import all of it. Two facts made that wrong. First, the `sectors` collection
supplies the same organisations with real names and no personal data, and covers far more of the
corpus: its `sectorCode` is the code prefix of everything a body owns, resolving **99% of
qualifications and standards** against the 40% reachable through `ssc`'s `qpPrefix`. Second, the
personal and financial data serves no product purpose whatsoever — nothing in the marketplace,
matching or career-path design consumes an awarding body's bank account.

**Decision:** Ingestion is selective and justified per collection, not wholesale. The `ssc`
collection is **not imported at all**, and no module under `api/` may read it.

More generally: **a field is imported because something needs it, not because it is present.**
Audit, workflow and shadow fields (`createdBy`, `updatedReason`, `Reviews`, `dockets`,
`deactivation*`, every `_bk` / `_Old` variant) are dropped by the document parsers rather than
carried on the chance they prove useful.

**Options considered:**
1. Import everything, encrypt the sensitive fields under ADR-023
2. Import the ~110 rows carrying a `qpPrefix`, dropping only the PII columns
3. **Exclude the collection entirely** *(chosen)*

**Why:** Option 1 takes on a permanent DPDP obligation — lawful basis, retention limits, erasure
and export rights, breach exposure — for data the product does not use. Encryption reduces the
consequence of a breach; it does not create a lawful basis for holding the data in the first place.
Option 2 still means holding contact details for real people, and buys almost nothing: the
`sectors` collection already resolves more than twice the corpus. Option 3 loses no capability.

**Consequences:**
- Sector Skill Councils and awarding bodies come from the `sectors` collection, which holds both
  populations under one key, and land in one `awarding_bodies` table because the source treats them
  as one thing.
- Ownership is derived from the code prefix rather than from any explicit field.
- Should awarding-body contact data ever be needed, it must be collected with consent through the
  product's own onboarding, not lifted from a portal export.
- The exclusion is asserted by test and by convention: `CLAUDE.md` states that nothing in `api/`
  may read `ssc`, and the schema carries no column sourced from it.

This complements ADR-023 (encryption of sensitive data) rather than qualifying it. ADR-023 governs
data the product needs and must protect; this governs data the product does not need and therefore
must not hold. The cheapest way to protect personal data is not to collect it.

---
