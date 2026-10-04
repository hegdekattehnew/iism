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
> - **ADR-005, ADR-007** — extended by ADR-036 (skill-based versus behavioural, and when a
>   model may be called).
> - **ADR-021** — qualified by ADR-033 for Hindi-language search.
> - **ADR-039** — extended by ADR-042. Role-derived permission stands for everything scoped to a
>   tenant; ADR-042 adds a second authority that no membership can grant.
> - **ADR-003** — qualified by ADR-034. Its rejection of a second store for *vector search* stands
>   and pgvector is unchanged; ADR-034 adds a document store for *source data* only.
> - **ADR-025** — its deferral clause is carried forward by ADR-043, cited honestly rather than
>   declared satisfied: two of its three gate metrics are still thin. ADR-025's mandatory
>   instrumentation is unchanged.
> - **ADR-042** — extended by ADR-044. "An operator is not a role" stands; ADR-044 adds a second
>   global flag (`staff_tier`) beside `is_staff`, the tiering ADR-042's own consequences section
>   already anticipated.
> - **ADR-045** — superseded in part by ADR-046. §1–4 (the sibling module, the new tables, the
>   second scorer) are withdrawn: the owner determined a gig is a temporary job assignment and
>   should be treated as one. §5 (no payment/payout) is untouched and still holds.
> - **ADR-025 / ADR-043** — extended by ADR-047. The structural half of the gate (no surface for a
>   provider to report an enrolment) is closed; the volume half (real traffic) is not, and is not
>   something a later ADR can close by writing more code.

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

**Status:** Accepted. First slice built in Sprint 42 as ADR-049, derived from qualification data rather than the graph below.

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

## ADR-036: Recommendation Approach and Where the LLM Sits

**Status:** Accepted (September 2026)

**Context:** ADR-005 splits AI into extraction/explanation versus deterministic decision-making,
and ADR-007 names the scoring components. Neither answers two questions the matching engine cannot
avoid: whether recommendations are driven by **skills or by behaviour**, and **when in the request
lifecycle** a model may be called. Both are cheap to decide now and expensive to reverse once a
scoring surface exists that people have seen.

The cold start is absolute — nine users, four declared skills, zero recorded events. Collaborative
filtering needs on the order of 10⁴–10⁵ interactions before it beats random, so it is not
available. But that is the weaker argument.

**Decision:**

1. **Recommendations are skill-based. Behaviour is a re-ranker, never a source of matches.**
2. **LLM calls happen at write time, never in the request path.**

**Why skill-based, beyond the cold start:**

- **Behaviour cannot produce the output.** Collaborative filtering answers "people like you applied
  here". It cannot answer "you are missing these three standards, and this course closes them" —
  and the gap *is* the product. A behavioural engine would be a worse job board.
- **We have an ontology, which most recommender domains never get.** 238,370 assessable criteria,
  levels, entry routes, and an importance weight the standards themselves publish. Discarding that
  for click data would be perverse.
- **Cold start does not bite us the way it bites consumer recommenders.** A candidate with no
  history still gets a good answer, because the input is their declared skills.

When behaviour exists it may reorder already-qualified matches. It must never introduce a match, or
suppress one, on its own — that would make the explanation untrue.

**Why write-time only for LLM calls:**

Extraction (a résumé or a job description into taxonomy concepts) runs once per document.
Explanation, if it is ever generated rather than templated, is cached by content hash. Scoring is
deterministic SQL and arithmetic. Five reasons, in order: a score must be **auditable** to an
employer or a regulator; a golden set needs **determinism** to measure against; latency; cost —
1,000 daily users at 20 matches each is 20,000 calls a day; and reproducibility of an explanation
the candidate may act on.

**Embeddings are the middle path**, and where ADR-007's "semantic similarity" comes from. A vector
computed once at write time and compared with arithmetic at read time is not an LLM call. ADR-013
and ADR-031 already fix the implementation and dimension.

**Consequences:**
- `api/modules/matching/` contains no model client, and must not acquire one.
- Every score returns a **reason structure** — matched concepts, missing ones, which are mandatory,
  the level shortfall — rather than a number and a sentence. The UI renders the structure, so the
  explanation cannot drift from the score.
- Matching scores at **concept** level, not skill-row level, or a candidate and a job that picked
  different rows for the same standard would never meet.
- `analytics_events` must exist from the first release of matching, or the behavioural signal that
  a later re-ranker needs will not have been collected.
- Semantic similarity is deliberately **not** in the first release: deterministic overlap ships
  first so there is a baseline to measure any addition against.

---

---

## ADR-037: The Employer Console as a Labelled Demonstration

**Status:** Accepted (September 2026)

**Context:** Everything the matching engine does is real, and none of it is visible to the side of
the market ADR-025 expects to eventually carry revenue. There is no employer surface at all, so the
B2B case cannot be shown — and it needs to be, to an audience deciding whether to fund the next
phase.

Building it properly would mean organisation authentication, which ADR-032 deliberately deferred:
organisations have nothing to publish, so a login for them would protect nothing and would be
authentication built to satisfy a demo rather than a user. But an employer surface with **no**
authentication reads the candidate pool, and that is a real exposure however the roadmap is worded.

**Decision:** ship the employer console as an unauthenticated demonstration, bounded by three
constraints that are enforced in code rather than promised in a document.

1. **It is the same scorer, run the other way round.** `score_match` takes what a job requires and
   what a person holds; it does not care which side the query started from. Ranking candidates is
   that function with its arguments swapped. **No second scoring implementation may exist** — two
   scorers drift, and once they disagree about the same pair neither number is defensible.
2. **No candidate is identified.** A card carries a reference derived from the profile id, a
   headline, a district, years of experience and the gap. Never a name, a phone number, an email or
   a user id. A demonstration that leaks the pool is not a demonstration worth having.
3. **It refuses to mount in production.** `mount_employer_console` checks the environment and
   returns `False`, mirroring `ConsoleNotificationProvider`, which refuses to run there for the same
   reason: a stand-in that survives into a live environment is indistinguishable from the real thing
   right up until it matters. A test boots the app in both environments and asserts the route is
   present in one and absent in the other.

The identity assumed — *which* employer you are acting as — is stated on the screen, above the data
rather than beneath it.

**Consequences:**
- `api/modules/matching/employer.py` holds retrieval and aggregation only; scoring stays in
  `scoring.py`.
- Real employer authentication remains deferred until self-serve publishing exists. When it lands,
  the mount guard is removed and the routes move behind `get_current_user` — the ranking logic is
  unchanged, because it never depended on being anonymous.
- Two analytics events (`employer_overview_viewed`, `employer_shortlist_viewed`) carry a tenant or
  job id and counts, never a candidate reference. ADR-025's payload rule applies here as everywhere.

---

## ADR-038: One Identity, Many Roles

**Status:** Accepted (September 2026). Supersedes the organisational half of ADR-032.

**Context:** ADR-032 decided **phone with one-time passcode for candidates, email and password for
organizational actors**, and said both should be linkable on one account. The schema half shipped in
Sprint 4 — `User.phone` and `User.email` are nullable, independently unique and independently
verified, and `issue_token_pair` takes only a UUID — but nothing behavioural was ever built.

Two things are now known that were not then.

**A person is not an actor type.** The same human is a candidate looking for work *and* the hiring
manager at the clinic that employs them, and may later run a training centre. ADR-032 framed the
decision as *which credential each cohort uses*, which quietly implies a cohort per account. Two
accounts would fork a person's history, split their memberships, and make "signed in with the wrong
one" a permanent support burden.

**The password half has not survived contact with the build.** The OTP store, verify-and-consume,
per-identifier request limiting and attempt capping all exist, are tested, and are credential-blind
in logic. Reusing them costs a rename. A password path costs a hashing dependency — ADR-030 forbids
hand-rolling, and `hash_secret` is HMAC-SHA256 with no work factor, so it must not be repurposed —
plus a reset flow, strength rules and an ADR-023 obligation, before any employer posts a vacancy.

**Decision:**

1. **Organisations sign in with email and a one-time passcode.** No passwords anywhere in the
   product. ADR-032's *principle* is kept intact and is what the code implements: which credential a
   flow requires is decided by actor type **in the service layer**, not scattered across handlers.
2. **One `User`, many `Membership` rows.** A signed-in person can create an organisation from their
   existing identity (`POST /me/organisations`) and link a second credential
   (`POST /me/credentials/{email,phone}`). Both organisation paths — cold registration and creation
   from an existing account — land in the same state.
3. **The active tenant is named by the request and granted by the membership.** It is never carried
   in the token. Switching workspaces must not require re-issuing tokens; one person may hold two
   tabs open as two organisations, which a token-borne context makes impossible; and a claim baked
   into a 15-minute access token outlives a membership revoked in the meantime.

**Consequences:**
- Registering an address that already has an account **sends a sign-in code and creates no second
  organisation**. An earlier implementation sent a "you already have an account" note instead, which
  made the two responses differ by one field the moment `expose_otp` was on — a prober could read
  the difference straight off the response. A test asserts the two responses are indistinguishable.
- `EmailProvider` is a **separate port** from `NotificationProvider`, not a second method on it. SMS
  and email are different vendors with different failure modes and compliance regimes; in India DLT
  registration applies to one and not the other. `ConsoleEmailProvider` refuses to run in production,
  exactly as its SMS sibling does.
- SSO, when it arrives, attaches to the email identity rather than replacing a password flow.
- ADR-032 stands for candidates and for the dual-credential schema. Only its organisational
  credential choice is superseded.

---

## ADR-039: Authorization — Permissions Resolved From Membership Role

**Status:** Accepted (September 2026). Implements ADR-012 and ADR-022.

**Context:** ADR-012 decided "RBAC now, design for ABAC" and ADR-022 decided "permission-based
authorization". Both were Accepted, and for eleven sprints **neither existed in code**.
`Membership.role` carried three legal values, was written exactly once at account provisioning, and
was read nowhere. `get_current_user` answering *is this person signed in* was the entire enforcement
surface in `api/`. That was defensible while every authenticated route acted on the caller's own
data; self-serve publishing ends it, because a job belongs to an organisation rather than a person.

**Decision:** a permission layer whose permissions are resolved from the membership role.

- Callers ask for a **permission**, never for a role — ADR-022 — so ADR-012's eventual move to ABAC
  changes how the set is computed without touching a single route.
- The set is a closed `StrEnum`, for the same reason `EVENT_NAMES` is closed: an open string becomes
  forty spellings of the same idea within a month, and no audit survives that.
- `require(permission)` returns a frozen `TenantContext(user, tenant, role, permissions)`. Every
  org-scoped query filters on `context.tenant.id`; **no route reads a tenant id from a request
  body.**
- Deletion is the owner's alone. An admin can unpublish, which reverses; nothing else does.

**A tenant the caller is not a member of returns 404, never 403.** A 403 confirms the organisation
exists, so an employer could enumerate competitors by guessing slugs. Within an organisation the
caller has already proved membership, so an insufficient *role* is a 403 — the existence of the
organisation is not news to them, and telling them their role is too narrow is the useful answer.

**Consequences:**
- The employer console gains authenticated routes and ships to production. The unauthenticated
  demonstration console stays, mounted in **local environments only** — an allowlist, replacing the
  earlier comparison against `"production"` alone, which mounted an unauthenticated reader of the
  candidate pool on `staging`, on CI, and anywhere `ENVIRONMENT` was unset or misspelled. ADR-037
  anticipated removing the guard entirely; keeping the demonstration behind it is a deliberate
  deviation, and `/health` now reports whether it is mounted.
- Teammate invitations need no restructuring: the model is many memberships from the start, and the
  only thing missing is a way to create the second one.

## ADR-040: Structured JSON logging, superseding ADR-019's tooling

**Status:** Accepted. **Supersedes the tooling half of ADR-019**, which remains the destination.

**Context:** ADR-019 was Accepted and named OpenTelemetry, Prometheus and Grafana, and `CLAUDE.md`
repeated that claim in the tech-stack table. **None of the three was installed** — not in
`pyproject.toml`, not in the lockfile — and the gap had gone unnoticed for nineteen sprints because
nothing forced the question.

What existed instead was thinner than the ADR implied and thinner than anyone assumed: **5 logging
call sites in 93 Python files** (three `.warning`, one `.exception`, zero `.info` and zero
`.error`), **no logging configuration of any kind**, and therefore **three uncorrelated sinks in one
process** — structlog's default `PrintLogger` to stdout in ANSI colour, an unconfigured stdlib
logger falling through to `lastResort` on stderr, and unhandled tracebacks raw to stderr. No line
carried a request id, a user id or a tenant id. There were no exception handlers. `/health/deep`
caught every dependency failure and discarded the reason.

**Decision:** structured JSON to stdout, one object per line, no vendor SDK.

- One `structlog.stdlib.ProcessorFormatter` on one root handler, so structlog-native records and
  stdlib records — uvicorn, ARQ, SQLAlchemy, the notification adapters — render through one shared
  tail and land in one stream.
- **The redaction filter ADR-023 has always specified lives in that shared tail**, which is what
  makes it unbypassable: reaching for `logging.getLogger()` instead of structlog does not route
  around it.
- The process writes to stdout and nothing else. Collection is the platform's job — `awslogs` on
  ECS, which is why the shape is flat, single-line, and carries `timestamp` rather than
  `@timestamp` (a CloudWatch reserved field) and `level_number` beside `level` (a string level
  cannot be range-filtered).

**Why not OpenTelemetry now.** It is the right destination and this ADR does not argue otherwise.
It is premature while there is no deployed instance to observe: traces without a collector are a
dependency and a decision, not a capability. When there is somewhere to send them, OTel replaces
the renderer and the middleware — not the redaction filter, which it would still need.

**Consequences:**
- `ADR-019` should be read as *deferred*, not *implemented*. Anyone finding no OTel in the tree has
  found the truth, not a bug.
- The worker's entry point is `api/worker.py`, not `api.core.tasks.WorkerSettings`: ARQ's CLI
  applies its own logging config after importing the settings module, so configuration has to
  happen in `on_startup` or be handed to ARQ with `--custom-log-dict`. Both are used.
- `DB_ECHO` is refused outside development. `echo=True` attaches SQLAlchemy's own raw handler,
  bypassing the filter, and logs bound parameters — and a `WHERE users.phone = $1` binds a phone
  number.

## ADR-041: Localisation — source text in the row, translations in one table

**Status:** Accepted (September 2026). Supersedes the two-language assumption in **ADR-033**, whose
India-first, Hindi-and-English-at-launch decision stands; what is withdrawn is the implementation
that made "two" structural.

**Context:** ADR-033 was implemented as a column pair per translatable field — `title_en` and
`title_hi`, `name_en` and `name_hi` — which reached **18 pairs across 12 tables**, 16 `_hi` fields
in the API schemas, and **37 two-language ternaries** in the web client (`isHi && x.name_hi ?
x.name_hi : x.name_en`). `web/src/i18n/routing.ts` carried a comment claiming "adding a locale is a
translation task, not a refactor". It was not: a third language meant a schema migration, new
response fields, and an edit at every one of those 37 sites. The language switcher — two tabs — was
the visible symptom of a shape that could not hold three.

The measured state made the timing obvious. Of ~600,000 translatable rows, about **95 carried any
Hindi at all**: 52 of 21,355 skills (the curated set Sprint 9 retired), 22 of 23 jobs and 21 of 21
courses (both seeded demo data), and **zero** of 238,370 performance criteria, 185,559 knowledge
parameters, 4,424 qualification packs, 1,808 occupations and 43 sectors. The column pairs were a
promise the data had never taken up.

**Decision:**

1. **The base column holds the text in the row's own language.** `title_en` becomes `title`;
   `name_en` becomes `name`. A `source_locale` column (default `en`) says which language that is,
   because a job posted by a Hindi-speaking employer is source-Hindi and the corpus is source-English.
2. **Every other language lives in `content_translations`** — `(entity_type, entity_id, field,
   locale, text, source)`, unique on the first four. Adding a language is **INSERTs, never DDL**.
3. **`locale` carries no CHECK constraint**, deliberately, while `entity_type`, `field` and `source`
   all do. A closed set on `locale` would put adding a language back into a migration, which is the
   thing this ADR exists to prevent.
4. **The API resolves language; the client never picks.** Negotiation is `Accept-Language`, then an
   explicit `?locale=`, then the signed-in user's `preferred_locale`, then the default. Responses
   carry `title`, `locale_served` and `available_locales` — not one field per language.

**Why a side table rather than JSONB per field.** JSONB (`title: {"en": …, "hi": …}`) reads well and
costs more than it looks: it rewrites all 600,000 rows for a feature 0.02% of them use, it bloats
every index that touches a translatable column, and `skills.search_vector` — a GENERATED column —
would have to parse a JSON document per row on every write. The side table stays empty until
somebody translates something, and the sparse case is the case.

**Consequences:**

- **Adding a language is: one entry in `web/src/i18n/locales.ts`, one messages file, and rows.** No
  migration, no schema change, no new response field.
- **Search has two halves.** The generated vector covers source text with the `english`
  configuration; translated text is matched through the translations table with `simple` plus
  trigram, because Postgres ships no stemmer for Hindi (the qualification ADR-033 already made to
  ADR-021 — and it now applies to every language the product gains).
- **Untranslated is the normal case, and must read as deliberate.** The fallback chain is
  requested → source → English, and the response says which locale it actually served, so a client
  can mark borrowed text rather than presenting it as translated.
- **This makes the *text* multilingual. It does not make the *taxonomy* portable.** NSQF is an
  Indian framework (ADR-004/024) and the matching engine scores against it. A market outside India
  needs its own qualification framework mapped in; a translated interface is not that, and must not
  be mistaken for it.

## ADR-042: Operator Authority — global, flag-granted, outside the tenant model

**Status:** Accepted (September 2026). **Extends ADR-039**, which stands unchanged for everything
scoped to a tenant.

**Context:** ADR-039 answers *where does authority come from* with one answer — membership role —
and every mechanism it describes is scoped to one organisation. `require()` reads an `{org_slug}`
from the path, `_context_for` resolves a `Membership`, and `TenantContext` carries a tenant that
every org-scoped query filters on. There is no expression in that model for authority that belongs
to nobody's organisation.

`tenants.is_verified` has existed since Sprint 12 carrying a comment that it is *"set by an
operator, never by the organisation"*, and **has had no writer for sixteen sprints**. Verified
against the tree before this was written: a column definition, a read on `TenantOut`, a read in the
interface, migration 0016's DDL, and a test asserting it cannot be written through `OrganisationIn`.
A marketplace whose verified badge nobody can grant has no verified organisations — and a
self-asserted badge would be worse than none, because a candidate reads it as ours.

There is no operator concept of any kind in the product. No `is_staff`, no admin router, and
"admin" in this codebase means a tenant membership role. That absence is what ends here, and how it
ends determines whether the product acquires a privilege-escalation path along with a back office.

**Decision:**

1. **A second authority, in the same vocabulary.** Callers ask for a `Permission`, never for a flag
   — ADR-022's rule kept verbatim, for the reason it gives: when operator authority stops being a
   boolean, the change is to how the set is computed and not to any route. Operator permissions are
   members of the same closed `StrEnum`, prefixed `OPS_`, granted by `users.is_staff` and by nothing
   else. **`ROLE_PERMISSIONS` never contains one** — an organisation's owner must never be able to
   verify their own organisation — and a test asserts the two sets are disjoint.

2. **Two dependencies, not one.** `require()` resolves a tenant from the path;
   `require_operator()` resolves only the caller and returns an `OperatorContext` with no tenant on
   it. Widening `TenantContext` with a nullable tenant would make "every org-scoped query filters on
   `context.tenant.id`" conditional at every existing call site, and a `None` there aims a footgun
   at exactly the queries that must never be unfiltered.

3. **The flag has no writer over HTTP, in this or any later revision.** It is set by
   `scripts/grant_staff.py`, which needs database credentials — a capability strictly greater than
   anything the API grants — and which refuses to create an account it cannot find. There is no
   "manage operators" endpoint and no operator-only route that grants operator status. **A back
   office whose first feature is its own escalation path is the failure this clause prevents.**

4. **404 to a non-operator, and the body is byte-identical to an unrouted path.** ADR-039's
   enumeration argument does not carry — there is one back office and its path is not guessable —
   but its second half generalises. The rule covering both: **403 only where the caller has already
   established standing in the thing they are being refused; 404 otherwise.** A non-member of an
   organisation has proved no standing, and neither has a non-operator. A different `detail` string
   is an oracle, and this product has shipped one of those already (ADR-038).

5. **The operator routes mount in every environment.** The demonstration console is guarded because
   it is *unauthenticated*, not because it is non-production. Verification is a production activity,
   and a badge grantable only on a laptop is the absent writer in a new costume.

6. **Provenance is not optional, and the badge is derived from it.** `tenants.is_verified` is
   dropped; `is_verified` becomes `verified_at IS NOT NULL`. A CHECK pairs `verified_at` with an
   actor and a non-blank note, so a badge without evidence is **not representable** rather than
   merely constrained. Every decision appends a row to `tenant_verification_events`, and
   **revocation is a new row, never a mutation**.

**Consequences:**

- **The audit trail is not in analytics, and cannot be.** `purge_expired` deletes events past a
  retention age and `record()` swallows its own failures — both correct for measurement, both
  disqualifying for a record that must survive and must fail loudly.
- **Dropping the boolean is free only in the sprint that adds the writer.** Nothing had ever written
  it, so no row could disagree with the timestamp and the migration could not lose information.
  Every later sprint would have made the same refactor a data audit.
- **Deleting an organisation deletes its verification history**, explicitly in
  `privacy/_delete_tenant` rather than by cascade alone — that module's own rule. The organisation is
  the *subject* of the record, so once it is gone the row identifies nobody and holding it is data
  kept without a purpose. The consequence is real and is not solved here: an organisation can be
  verified, misbehave, delete itself and re-register under the same name, because the duplicate-name
  guard is per account. Closing that needs a tombstone surviving erasure, which is a fresh
  data-protection decision.
- **An operator's own erasure nulls `verified_by`** and the history then reads "a former operator".
  Copying the address into the log to keep the name would recreate the one row in this product that
  stores somebody else's address.
- **`is_staff` appears on `/auth/me` and in the operator's own data-subject export. A verification
  decision appears in nobody's.** It is a record about an organisation; putting it in an operator's
  export would export the organisation's file, not theirs. The invitation precedent — your own act
  is yours to see — does not transfer, because an invitation's other party is a person you named.
- **Nothing tells an organisation its badge changed until a notification template lands.**
  Revocation is silent in the first slice. That is a gap, recorded as one, not a design.
- **The enum grows by need.** A second operator action is two members and a route, not a new model.
  When authority stops being a boolean — an operator who may verify but not suspend —
  `OPERATOR_PERMISSIONS` becomes a function of the user and no route changes. That is ADR-012's ABAC
  promise, kept on the operator side too.
- **A route that forgets the dependency is the residual risk**, exactly as three of eight publishing
  writes once shipped without their second guard (ADR-039). It is pinned by reading the app's own
  route table, not by remembering.

---

## ADR-043: Payment Adapter Port, Monetisation Still Deferred

**Status:** Accepted (September 2026). Carries ADR-025's deferral clause forward — it does not
declare that clause satisfied.

**Context:** ADR-025 deferred all billing and named three metrics that must exist before a successor
ADR authorises billing code: recommendation precision@5 against a hand-labelled golden set,
candidate-to-course click-through, and provider-reported enrolment conversion. As of Sprint 33:

- **Precision@5 is now citable.** Sprint 29 took the golden set from 5 pairs to 34 pairs, 7
  orderings and 16 course expectations — thin against a target of 50–100, but real and defensible
  for the first time.
- **Click-through is joinable, not populated.** Sprint 24 gave `course_recommended` and
  `course_opened` a shared subject, so the query exists — it returns near-zero rows, because the
  platform has no real user volume yet.
- **Enrolment conversion has no surface at all.** Sprint 24 deliberately modelled *interest*, not
  *enrolment*: whether somebody actually enrolled is a fact the provider's own system owns, and this
  platform cannot verify it without asking the provider to report it, which is unbuilt.

Two of three gates remain thin. Against that, the owner's stated direction — a marketplace that
sells courses and carries gig work — has been deferred once already (ADR-025) and again through
Sprint 33's actor-breadth push. Sprint 33 demonstrated the platform to management with no
monetisation story at all, which is the cost of continued deferral becoming visible rather than
theoretical.

**Decision:** Build the payment adapter *port* only — an interface plus a console implementation
that refuses to run, following ADR-017's own precedent for notifications and email. No gateway
integration, no `Order`, `Entitlement`, or `Payout` table, and no route calls it. This is not a
claim that ADR-025's gate is passed.

**Options considered:** 1. Full billing implementation now (gateway integration, orders, entitlements, checkout)
2. Continue deferring; build nothing
3. Payment adapter port only, no billing code
4. Payment adapter port plus a provider-facing enrolment/conversion reporting surface, to close
   ADR-025's remaining gap before writing anything payment-shaped

**Trade-offs:**

- Option 1: ✅ Fastest path to revenue if traction is real
❌ Builds against exactly the two metrics ADR-025 named as still unvalidated
❌ Sprint 24's "interest, not enrolment" reasoning **inverts** the moment money moves through the
platform: taking payment makes this platform the system of record for enrolment, a materially larger
claim than anything built so far

- Option 2: ✅ No engineering spent against an unvalidated model
❌ The owner's stated direction has no path forward of any kind
❌ Blocks every later sequencing step (course checkout, gig) indefinitely rather than merely delaying
it

- Option 3: ✅ Matches ADR-017's own adapter precedent exactly — an interface commits to no vendor
and costs one small file tree
✅ Lets course-checkout design start against a real protocol instead of a hypothetical one
❌ Produces no revenue and closes none of ADR-025's metric gaps by itself

- Option 4: ✅ Would make ADR-025's gate fully citable before any payment-shaped code exists
❌ A provider-facing enrolment-reporting surface is its own scoped product feature — asking a
training provider to report back into the platform — not a one-sprint addition to an adapter port,
and bundling it here would understate its size

**Final decision:** Option 3. `api/adapters/payments/` defines a `PaymentProvider` protocol
(ADR-017's shape: business logic depends on the protocol, never on a gateway SDK) and a
`ConsolePaymentProvider`. It differs from its `notifications/` and `email/` siblings in one respect:
those have a legitimate development-mode success path, because real features call them today. This
one has no caller anywhere in the tree — course checkout does not exist — so `ConsolePaymentProvider`
refuses unconditionally, in every environment, rather than only in production. Succeeding would
fabricate a transaction for a flow that is not built.

This ADR does **not** claim ADR-025's gate is satisfied. Recording that plainly is the point of
writing it now rather than waiting: click-through is joinable but near-zero in volume, and enrolment
conversion has no surface at all. Course checkout — the feature that would generate real signal on
both — is deliberately out of scope here.

**Consequences:**

- `api/adapters/payments/` exists with zero callers, the same state `notifications/` was in before
  Sprint 4 wired sign-in to it. An adapter is allowed to predate its first caller; ADR-017 does not
  require the reverse.
- The next ADR in this sequence is course checkout itself — `Order`/`Entitlement` schema, the
  gateway's real implementation, refund handling — not written here, and gated on the owner choosing
  to spend the sprint.
- ADR-025's instrumentation mandate is unchanged and still binds. Nothing here reduces the
  requirement to keep measuring precision@5, click-through and provider-reported conversion, and
  nothing here should be read by a future reader as having satisfied it.

---

## ADR-044: Operator Authority Tiers

**Status:** Accepted (September 2026). **Extends ADR-042**, which stands unchanged for the
question it already answers -- operator authority is global, flag-granted, and not a `Membership`
role. This ADR answers the question ADR-042 deliberately left open and named its own escape hatch
for.

**Context:** `users.is_staff` has been a single boolean since ADR-042 (Sprint 28): every operator
gets every `OPS_*` permission that exists. ADR-042's own consequences section anticipated this
would not stay true forever: *"When authority stops being a boolean — an operator who may verify
but not suspend — `OPERATOR_PERMISSIONS` becomes a function of the user and no route changes."*
`require_operator()`'s dependency body carried a `# pragma: no cover - seam for tiers` comment
against exactly this line since the sprint it was written.

The immediate trigger (Sprint 37, BL-7.3, reprioritised ahead of Epic B8 on the owner's
instruction): `OPS_ORG_VERIFY` is not like the other three `OPS_*` permissions. Granting or
revoking an organisation's "Verified" badge is a decision with **public** blast radius — every
visitor to that organisation's listings sees it — where `OPS_ORG_READ`, `OPS_PROGRAMME_READ` and
`OPS_CANDIDATE_VERIFY` are each either read-only or scoped to one candidate's own evidence. A
single flag cannot express "trusted enough to review a certificate" without also expressing
"trusted enough to publish a trust signal to the entire marketplace."

**Decision:**

1. **A second column, not a second model.** `users.staff_tier: str | None`, closed to
   `STAFF_TIERS = ("support", "admin")`. `NULL` iff `is_staff` is false —
   `ck_users_staff_tier_pairs_with_flag` makes "staff with no tier" and "tiered but not staff" both
   unrepresentable, the same shape ADR-042 used for `tenants.verified_at`/`verified_by`. **Still not
   a role**: this is a second global flag beside `is_staff`, on the same `users` row, never a
   `Membership` — ADR-042's "an operator is not a role" is unchanged by having two flags instead of
   one.
2. **`TIER_PERMISSIONS: dict[str, frozenset[Permission]]` in `core/authorization.py`, exactly the
   function ADR-042 predicted.** `support` holds `OPS_ORG_READ`, `OPS_PROGRAMME_READ`,
   `OPS_CANDIDATE_VERIFY`; `admin` holds all four, `TIER_PERMISSIONS["admin"] ==
   OPERATOR_PERMISSIONS`, asserted at import time. No route changed — `require_operator(permission)`
   still takes one `Permission` and the eleven call sites across `operations/routes.py` are
   untouched. Widening this to a third tier later is two dictionary entries, not a schema change.
3. **The refusal for an insufficient tier is 403, not 404 — a deliberate departure from ADR-042's
   own rule, narrowed to where it still applies.** ADR-042 made every operator refusal 404, on the
   reasoning that "a non-operator has proved no standing." That reasoning is intact for a
   non-operator. It does not extend to an operator whose tier lacks one specific permission: that
   caller has already proved operator standing — the same fact a 200 on any other `/ops` route
   would confirm — so a 403 discloses nothing a stranger could not already infer by trying. This is
   ADR-038's tenant-side rule (an established identity's insufficient permission is a 403) applied
   one level up, and it produces a genuine, testable oracle: the same URL answers 404 to a stranger
   and 403 to a `support` operator.
4. **No new HTTP writer, in this or any later revision — the one constraint BL-7.3's acceptance
   criteria named explicitly.** `scripts/grant_staff.py` gains a required `--tier` flag on grant;
   revoke clears both columns together. There is still no "manage operators" route, and there will
   not be one, for the reason ADR-042 gives: a back office whose first feature is its own escalation
   path is the failure this rule exists to prevent.
5. **Migration 0036 backfills every existing `is_staff = true` row to `admin`.** Not a default of
   convenience — a boolean's only honest equivalent tier is the one with no restrictions. Any
   narrower backfill would silently take access away from an account that already had it, at the
   moment this migration ran, which is a worse failure mode than a boot-time refusal would have
   been and would not even announce itself.

**Options considered:** 1. Leave `is_staff` a boolean; treat `OPS_ORG_VERIFY` as an accepted risk
2. A third `Membership`-style role scoped to a synthetic "platform" tenant
3. Two independent booleans (`is_staff`, `may_verify_orgs`)
4. A tier column resolving to a `Permission` subset via a dictionary in `core/authorization.py`

**Trade-offs:**

- Option 1: ✅ Zero engineering
❌ Does not address BL-7.3's own premise — the one action with public blast radius stays as
reachable as a read-only report, forever, by construction

- Option 2: ✅ Reuses `ROLE_PERMISSIONS`' existing machinery
❌ Directly contradicts ADR-042's founding rule: a synthetic tenant is still a tenant, and
`Membership`-shaped authority for something that belongs to nobody's organisation reintroduces the
exact confusion ADR-042 was written to end

- Option 3: ✅ Simplest possible schema change
❌ Does not generalise — a third distinction needs a third column, and `require_operator()` would
need a per-permission `if` rather than one table lookup; ADR-042 explicitly named this shape as the
one to avoid ("becomes a function of the user," not a second flag per permission)

- Option 4: ✅ Matches ADR-042's own anticipated shape exactly
✅ Adding a tier or moving a permission between tiers touches one dictionary, no migration, no
route
❌ A second dimension of authority is a second thing to reason about when auditing who can do what

**Final decision:** Option 4.

**Consequences:**

- **`require_operator()`'s docstring now states two rules where it stated one**, and a test proves
  both are reachable on the same URL (`test_a_stranger_gets_404_on_the_very_same_route_a_support_
  operator_gets_403_on`) — the same discipline ADR-042 itself used to prove its own 404-vs-403
  split non-vacuous.
- **`OperatorContext.permissions` is now the caller's granted subset, not the full
  `OPERATOR_PERMISSIONS` set.** Nothing outside `core/authorization.py` compared it against the
  full set before this change, so nothing else needed to move — but a future route written as
  `if OPS_X in OPERATOR_PERMISSIONS` instead of asking `require_operator(Permission.OPS_X)` for the
  permission it actually needs would silently bypass the tier check. There is no such call site
  today; this is the risk to watch for.
- **A `support` operator can still be handed every read in the back office and the one write scoped
  to a single candidate's evidence, with no path to the public-facing badge.** This is the actual
  audience-visible capability BL-7.3 unlocks: a second operator can be brought on for routine
  verification work without also being trusted with the marketplace's public trust signal.
- **The seam ADR-042 left is now closed.** `# pragma: no cover - seam for tiers` is gone from
  `require_operator()`; the line it marked is now the real tier check, not a vacuous one.

---

## ADR-045: Gig / Short-Term Work — Design Phase (BL-8.1)

**Status:** Superseded in part by ADR-046 (September 2026). §1–4 below (the sibling module, the
new tables, the second scorer) are withdrawn — the owner determined a gig is a temporary job
assignment and should be treated as one, reusing `Job`/`Application` instead. §5 (no
payment/payout) is untouched and still holds. Kept here in full, not deleted: its reasoning about
why a gig looked like a different market was not wrong on its own terms, and a future story
revisiting this boundary should read both ADRs. Nothing described below was ever built against
this design; BL-8.2 was built against ADR-046 instead.

**Context:** The Business Requirements Document names gig work as the third pillar and is explicit
about why it is last: *"a genuinely different market with its own physics — availability rather
than a permanent vacancy — rather than an extension of the first two."* The Product Requirements
Document (§8.3) and the High-Level Design (§9.3) agree on the shape of the answer without
specifying it: *"a genuinely different market with its own physics; warrants its own design phase
rather than an extension of this product"* and *"a new, sibling module... does not extend
`marketplace.Job`... reuses `geography/` and `skills/`."* Neither document goes further. This ADR
is where the physics actually get specified.

**What makes this a different market, concretely — not just a slogan:**

1. **A vacancy is a standing offer; a gig is a scheduled need.** `Job` has no start or end time —
   it is open until closed. A gig is inherently time-boxed: a specific shift, or a short run of
   them, with a real start and end. There is no equivalent of `JobSkill`/`CandidateSkill`'s
   always-on comparison — the question is not just "can this person do this work" but "can this
   person do this work *at this time*."
2. **Proximity is a hard filter, not a tie-break.** `matching._locality` is deliberately a
   tie-break, not a score component, because a strong permanent-job match is worth relocating for
   — ADR-037's own reasoning. Nobody relocates for a one-day gig. A gig listing outside a worker's
   reachable radius is not a worse match; it is not a match, the same way a missing mandatory
   standard is not "a slightly worse fit" for a vacancy that requires it.
3. **A vacancy does not end when someone is hired; a gig does.** Sprint 27 gave `Job` a lifecycle
   because *closing* was missing — but even closed, a job was never "completed" in the sense of a
   specific piece of work being finished and judged. A gig has a real completion event, and only a
   completion event can produce evidence of whether the work was actually done well — which neither
   `Job` nor `Application` has any way to represent.
4. **Reputation is bidirectional and gig-specific.** `CandidateSkill.source` (self-declared →
   inferred → assessed → certified) is evidence about a *skill*, gathered once and reused across
   every future match. Gig reputation is evidence about *reliability*, accumulated one completed
   engagement at a time, and it runs both directions — a poster who cancels on short notice or
   never pays is exactly as much a data point as a worker who does not show up.

**Decision:**

1. **A new sibling module, `api/modules/gig/`.** Depends on `identity` (who posted, who worked),
   `geography` (district-level proximity, reusing the existing `PlaceIndex` resolution — no new
   location-resolution logic), and `skills` (required standards, compared at concept level via the
   same `Skill.concept_id or Skill.id` key `scoring.py` and `courses_closing_gap` already use).
   **Does not import `marketplace`, and nothing in `marketplace` imports it.** No shared table with
   `Job`; a `GigListing` is a new, independent model, not a subtype or a new `Job.status` value —
   exactly Sprint 27's own lesson about `closed_at` restated for a bigger fork.
2. **A gig poster is an existing `employer` tenant, not a new actor type.** Epic B7 is about new
   *actors* (a government agency, an external system); Epic B8 is about a new *market* for an actor
   that already exists. Inventing a fifth tenant type here would blur that distinction for no
   benefit — a staffing agency or a hospital already registered as an `employer` should be able to
   post both a permanent vacancy and a weekend shift from the same account, the same
   ADR-038 reasoning that refused to fork an account by role. A new `Permission.GIG_PUBLISH`,
   scoped `require(Permission.GIG_PUBLISH, "employer")`, mirrors `JOB_PUBLISH` exactly.
3. **The domain model, sized to what matching, proximity and completion actually need — no more:**
   - **`GigListing`** — poster `tenant_id`, a district (`district_id`, **not nullable**: unlike a
     job, "somewhere in India" is not a postable gig), one or more shift windows
     (`starts_at`/`ends_at`, timezone-aware per the `tenants.created_at` lesson), `positions`
     (reusing `Job.positions`' own reasoning almost verbatim), and required skills through a
     `GigListingSkill` association table shaped like `JobSkill` (`skill_id`, `importance`,
     `is_mandatory`) — the *shape* is reused because it is a good shape, not the *table*.
   - **`GigWorkerAvailability`** — `profile_id`, a window (or a recurring pattern — a decision
     BL-8.2 still owes: a fixed date range is simplest to ship and cheapest to get right; a
     recurring weekly pattern is what a real gig worker actually wants and is explicitly the harder
     version deferred to BL-8.2's own build, not decided here). Lives in `gig/`, not as new columns
     on `CandidateProfile` — most candidates will never post one, the same reasoning that keeps
     `interests/` a sibling of `applications/` rather than columns bolted onto `Job`.
   - **`GigAssignment`** — one row per worker matched to one listing.
     `status ∈ {offered, accepted, in_progress, completed, no_show, cancelled_by_worker,
     cancelled_by_poster}`. This is the lifecycle Sprint 27 gave `Job` a smaller version of
     (`closed_at`/`close_reason`), sized up: a gig's status is a fact about *one worker's*
     engagement, not the listing as a whole, because a listing with three positions can have one
     worker complete, one no-show and one still in progress simultaneously.
   - **`GigReview`** — one row per direction per completed assignment (`assignment_id`,
     `rating_of` ∈ `{worker, poster}`, a 1-5 rating, an optional comment). Two rows, not one row
     with two rating columns: a poster rating a worker and a worker rating a poster are different
     acts by different people, and forcing them into one row means one party's review can only ever
     be written after the other's, or the row does not exist yet to update. **Only writable once
     `status = completed`** — a rating on a cancelled or no-show engagement is not evidence about
     the work, it is evidence about the cancellation, which the `status` value already carries.
4. **Matching is its own lightweight function, not `score_match`, and this is not the second
   scorer ADR-037 forbids.** ADR-037's rule is about *one comparison* — candidate against
   permanent vacancy — having exactly one implementation. Candidate-against-gig-shift is a
   different comparison, with a different hard filter (availability and proximity, not "missing
   mandatory caps at 45%") and a different concept of evidence (completion history, not
   `candidate_skills.source`). Reusing `score_match`'s specific weights and cap, tuned against the
   permanent-job golden set, would import numbers that have nothing to do with this question.
   What *is* reused: the concept-level comparison key (`Skill.concept_id or Skill.id`) and the
   general shape (retrieval narrows, then a bounded function scores the survivors) — patterns, not
   the tuned instance. **Retrieval for gig work filters on district and availability-window
   overlap before skill match is even considered** — the inverse order from `match_jobs`, where
   skill overlap drives retrieval and locality only breaks ties among the results.
5. **No payment, no payout, in this design or in BL-8.2.** ADR-025's gate on billing code applies
   here exactly as it applies to course checkout — a worker being paid through the platform is a
   materially larger claim (the platform becomes the payer of record) than anything this design
   proposes. A completed gig produces a review, not an invoice.

**Options considered:** 1. Extend `Job`/`Application` with gig-specific nullable columns
(`is_gig`, `shift_starts_at`, …)
2. A new sibling module, sharing no tables with `marketplace`, as described above
3. A fully separate service (its own database, its own deployment) given how different the domain is

**Trade-offs:**

- Option 1: ✅ No new module, reuses existing routes and the existing employer console
❌ `Job.status`'s CHECK, `open_job()`, every listing query and the golden set would all need to
learn a second meaning of "open" — exactly the "closing is not a third `status`" lesson from
Sprint 27, at a much larger scale, for a domain that does not actually share `Job`'s invariants
(a gig is not "closed" when filled, it is "in progress")

- Option 2: ✅ Matches the HLD's own placement table and Sprint 27's precedent for how this
codebase handles "looks similar, is not the same lifecycle"
✅ `marketplace/`, `matching/` and `scoring.py` are provably untouched — the golden set and every
existing test stay bit-identical by construction, not by discipline
❌ Real duplication of shape (a second `*Skill` association table, a second retrieval-then-score
pipeline) — accepted because the shapes are genuinely different once availability and proximity are
hard filters rather than a tie-break

- Option 3: ✅ Maximum isolation; nothing here can ever regress the job-matching path
❌ ADR-014's whole premise is that the modular monolith defers the microservices decision until
there is a reason for it, and "the domain feels different" is not yet a reason a monolith cannot
express — this reaches for Option 3's cost before Option 2's cost has actually been felt

**Final decision:** Option 2.

**Consequences:**

- **BL-8.2 inherits three explicit open decisions this ADR deliberately does not close**: a fixed
  availability window versus a recurring pattern; whether `GigListingSkill.importance`/
  `is_mandatory` feed a hard filter or a soft score the way they do for `Job`; and whether a
  worker's aggregate reputation (once `GigReview` rows exist to aggregate) should influence gig
  *ranking* or only be *shown* — the same "does behaviour rank or merely reorder" question ADR-036
  already answered once for the main platform, worth re-asking rather than assuming the same answer
  transfers.
- **No golden set exists for gig matching, and none can be built before real listings and real
  completions do.** The same honesty ADR-043 applied to the monetisation gate applies here: BL-8.2
  should not claim a tuned scorer before there is data to tune it against, and should say so in its
  own commit the way ADR-043 said so about semantic similarity's placeholder.
- **`api/modules/gig/` will need its own `tests/test_import_order.py` entry and its own migration
  sequence**, but neither exists yet — this ADR authorises the module's *shape*, not its schema.
  The first concrete artifact of BL-8.2 is the migration that creates `gig_listings`,
  `gig_worker_availability`, `gig_assignments` and `gig_reviews`, reviewed on its own terms.
- **Nothing in this design requires touching `marketplace/`, `matching/`, `scoring.py`, or the
  golden set.** That is the property Option 2 was chosen to guarantee, and BL-8.2's own tests
  should assert it the way `tests/test_payment_adapter.py` asserts nothing under `api/modules/`
  imports the payment port before checkout exists.

---

## ADR-046: Gig Work Reuses `Job` — Supersedes ADR-045 §1–4 (Sprint 37, Epic B8)

**Status:** Accepted (September 2026). Implemented and live-verified in the same sprint.

**Context:** ADR-045 was written, reviewed and never built — no migration, no module, no route
ever existed against it. Before BL-8.2 build work began, the owner gave a direct instruction that
overrides ADR-045's central premise: **"A gig work can also be considered as a temporary job
assignment and should be treated like a job in our system"** — for both the marketplace (postings)
and matching (a candidate's ranked results). ADR-045 had argued the opposite from first principles
(§"What makes this a different market, concretely"), reasoning forward from an assumption — a gig
*must* be architecturally distinct because its physics differ — that the owner's framing rejects
outright: the physics ADR-045 named (a real end, a real place, a completion event, bidirectional
reputation) are properties a `Job` row can simply be given, not proof that a `Job` row cannot hold
them.

Verified against the actual code before any of this was written, not assumed: `open_job()`
(`marketplace/models.py`), `match_jobs`'s retrieval SQL, `score_match` (`matching/scoring.py`), and
the existing hourly `close_expired_jobs` worker cron (`alerts/service.py`) contain **zero
references to `employment_type`**. A `Job` row with `employment_type="gig"`, a real `closes_at`,
and a real `positions` count already flows through the existing matching, ranking, and auto-close
pipeline with no code change to any of those three files. This is the fact ADR-045 did not have
occasion to check, because it never considered reuse as an option.

**Decision:**

1. **A gig is a `Job` with `employment_type="gig"`.** No new module, no `GigListing`, no
   `GigListingSkill`. `Job.district_id` (already `NOT NULL`-enforced in effect by
   `resolve_location`), `Job.closes_at`, `Job.positions` are exactly ADR-045's "a district, a
   window, a headcount" — they already existed on `Job`, unused by permanent vacancies for
   anything but the closing-date/auto-close feature Sprint 27 built. Two invariants close the one
   real gap: a gig with no resolvable district is refused at creation (422, service-layer, the same
   place `resolve_location` already runs — not a schema-level `NOT NULL`, because a permanent
   vacancy's district may still be null), and `JobIn` refuses `employment_type="gig"` with
   `closes_at=None` ("a shift with no end is not a gig") — both new checks, not the CHECK-widening
   migration, which only had to teach the enum a new value.
2. **`gig` joins the shared `EMPLOYMENT_TYPES` tuple** consumed by both `Job.employment_type` and
   `CandidateProfile.preferred_employment_type` — the owner's own second decision when asked
   directly. A candidate can state "gig" as a preferred employment type the same way they state
   "part_time" today; no separate preference model.
3. **Matching needs no second scorer, and this satisfies ADR-037 rather than testing it.**
   ADR-037's rule is "one comparison, one implementation." Gig-against-candidate is not a
   *different* comparison from permanent-vacancy-against-candidate once a gig is a `Job` — it is
   the *same* comparison, because `score_match` never asked what kind of `Job` it was scoring.
   ADR-045's argument for a second scorer rested entirely on gig work being a different kind of
   thing than a `Job`; once it is a `Job`, that argument has no premise left to stand on.
   `matching._locality`'s tie-break-not-hard-filter behaviour is **unchanged** for gigs too — the
   owner's instruction was to treat a gig as a job, not to give proximity a different role for one
   `employment_type` than another.
4. **Application outcomes, not a new `GigAssignment` model.** `Application` already carries one
   row per candidate per `Job`; `APPLICATION_STATUSES` gains `completed` and `no_show`, reachable
   only from `hired`, and only when the underlying job's `employment_type == "gig"` (enforced in
   `employer_service.set_status`, a service-layer refusal, the same shape as "no required standard
   blocks publish" — not a CHECK, because the rule spans two tables). A permanent vacancy's `hired`
   stays terminal exactly as before Sprint 37.
5. **Full two-sided rating, not status-only** — the owner's explicit choice when asked to scope
   it. New table `application_reviews`: `subject_role ∈ {poster, worker}` names **who the rating is
   about**, not who wrote it, so `UNIQUE (application_id, subject_role)` makes each direction
   write-once without one party's review having to wait on the other's row existing. Reviewable
   only once `Application.status == "completed"` — `no_show` is deliberately not reviewable, ADR-
   045's own reasoning carried forward unchanged: a no-show is evidence about the cancellation,
   which the status value already carries, not evidence about the work.
6. **§5 of ADR-045 is untouched.** No payment, no payout. A completed gig produces a review, not
   an invoice — the same gate ADR-025/ADR-043 apply to billing generally.

**Options considered:** 1. Keep ADR-045 as designed (sibling module, second scorer) and build
BL-8.2 against it, overriding the owner's later instruction
2. Reuse `Job`/`Application` as described above, formally superseding ADR-045 §1–4
3. A middle path — a new `GigListing` table that is not a `Job` subtype, but reads through the
   existing `match_jobs` pipeline via a view or union

**Trade-offs:**

- Option 1: ❌ Directly contradicts an explicit, direct instruction from the product owner, given
  after ADR-045 was written and before any of it was built — there is no design-quality argument
  strong enough to justify overriding that
- Option 2: ✅ Zero code changes to `matching/`, `scoring.py`, or the golden set — verified by
  grep before writing a line, not asserted after
✅ One `_PLAIN_FIELDS` fix (a genuine pre-existing bug: `positions`/`closes_at` were accepted by
`JobIn` and silently dropped by `create_job`/`update_job`, latent because nothing exercised them
through the HTTP API) is the only marketplace-side surprise, and it benefits every permanent
vacancy too, not only gigs
❌ `Job`/`Application` gain concepts (a completion event, a no-show, a review) that do not apply to
a permanent vacancy — accepted because the alternative (Option 1) is no longer the owner's decision
to make on this ADR's own reasoning alone
- Option 3: ❌ A view or union across `Job` and a new `GigListing` reintroduces exactly the
  "closing is not a third status" risk Sprint 27 already paid down once, and for less benefit than
  Option 2 — it still has to solve the placement question when the direct answer (make it a `Job`)
  is sitting right there

**Final decision:** Option 2.

**Consequences:**

- **One `Job` row per shift/date, not a recurring-gig model.** A staffing agency booking "every
  Saturday for a month" posts four `Job` rows, the same way a real staffing agency books each shift
  separately today. Accepted as the shape, not deferred as a gap — building a multi-shift
  sub-model would reintroduce exactly the complexity this ADR's reuse decision was meant to avoid.
- **No aggregate reputation surface yet.** `application_reviews` ships as a foundation-only table
  — a writer, no reader — the same shape `SkillRelation` shipped in (ADR-041's neighbour, Sprint
  36). There is no average-rating computation, no completion-count badge, and no query anywhere
  that reads more than one row at a time. Building one is a future story, not an oversight.
- **Reputation must never feed `score_match` without its own design pass.** If a later story wants
  a reputation-aware re-rank, it follows `weights_from_settings()`'s own precedent — a value
  computed outside `scoring.py` and passed in as an argument, never read from the database or
  settings inside the scorer itself (ADR-036's purity rule, ADR-037's one-scorer rule still bind
  it).
- **The frontend does not know about `"gig"` yet, and this ADR does not close that gap.** Three
  client-side arrays (`web/src/lib/profile.ts`, `JobBrowser.tsx`, `employer/JobEditor.tsx`) and two
  i18n namespaces across three locale files still need the new value; until they do, a gig `Job`
  on the public `/jobs` browse page renders the literal string `"employmentType.gig"` where a
  label belongs. Deliberately shipped backend-only, matching this project's established
  precedent for every prior backend-first sprint — not routed around by filtering gigs out of
  `/jobs` on the backend, which would be backend logic existing solely to compensate for a
  frontend gap. *Amended 2026-09-28:* shipping backend-only was not the neutral choice this
  bullet assumed. Widening `employment_type` broke the web type-check wherever the client held a
  narrower hand-written copy, so the branch as pushed did not build. The labels and the single
  shared list landed the same day; what stays API-only is the employer's completed/no-show
  controls and the rating form.
- **"Hired" became two questions, and a no-show answers them differently** (owner's decision,
  2026-09-28). Whether an application *fills a position* — which closes a vacancy at its
  head-count — counts `hired` and `completed`; a no-show left the seat empty and does not. Whether
  somebody *was hired* — the programme report's outcome figure — counts all three. Both sets are
  named once in `applications/models.py`; a bare `status == "hired"` is now the bug this
  sprint shipped twice.
- **ADR-045 remains in this document, marked superseded, rather than deleted.** Its reasoning
  about *why* a gig looked different was not wrong on its own terms — the owner's instruction
  changed the premise, not the analysis. A future story reconsidering this boundary should read
  both.

---

## ADR-047: Provider-Reported Enrolment Surface — Closing the Structural Half of ADR-025's Gate

**Status:** Accepted (September 2026). Extends ADR-025 and ADR-043. Does **not** authorise `BL-1.3`
(billing) on its own.

**Context:** ADR-025 named three metrics that must be citable before any billing code is written:
recommendation precision@5, candidate-to-course click-through, and provider-reported enrolment
conversion. ADR-043 (Sprint 34) built the payment adapter port but explicitly declined to close
that gate — precision@5 was citable, but click-through was "joinable, not populated" and enrolment
conversion "has no surface at all." Asked how to proceed toward `BL-1.3`, the owner chose to close
the gate first.

Checked against the code before writing anything: `api/modules/interests/models.py` already
separates the learner's moves (`registered`, `withdrawn`) from the provider's (`contacted`), with a
generic `provider_service.set_status`/`set_status_and_reload` pair that accepts any value in
`PROVIDER_STATUSES` through the existing `PATCH .../interests/{interest_id}` route with no route
change. `course_recommended` and `course_opened` (Sprint 24/33) already carry `user_id` and
`subject_id=course.id`, so click-through was already computable — nothing had ever queried it.

**Decision:** Add `"enrolled"` to `CourseInterest`'s status set, provider-settable at the same
unverified trust level `"contacted"` already carries. Add `scripts/report_conversion_metrics.py`
(`make monetisation-metrics`) to compute click-through and enrolment conversion from columns that
already exist — a sibling to `make evaluate`, which already answers precision@5 and touches no
`analytics_events` row. No new table, no new module, no new route, no new permission.

**Options considered:** 1. Full billing implementation now, treating ADR-043's port as sufficient license
2. Continue deferring; build nothing further
3. Close only the structural gap: a provider-reported enrolment surface plus the two missing reports
4. Also fabricate synthetic analytics/interest data so the metrics read as strong on a cold demo database

**Trade-offs:**

- Option 1: ✅ Fastest path to `BL-1.3`
❌ Ignores that ADR-043 explicitly declined to claim the gate was passed, and that nothing has
changed about real traffic since then

- Option 2: ✅ No engineering spent against an unvalidated model
❌ Leaves `BL-1.3` blocked indefinitely with no path forward, the same cost ADR-043 already weighed
against continued deferral

- Option 3: ✅ Matches ADR-043's own named "Option 4," reusing `CourseInterest` rather than adding
a table or module — the smallest change that makes the metric mechanically answerable
✅ Every number the resulting script prints is real, including an honest zero
❌ Does not, and cannot, make the *volume* underlying either metric large — that requires real
usage, not code

- Option 4: ✅ Would make both metrics look stronger immediately
❌ Directly contradicts this project's own instrumentation philosophy (ADR-025 exists precisely so
a revenue-shaped decision is not made on invented signal) and would misrepresent product traction to
whichever future ADR cites the number

**Final decision:** Option 3.

**Consequences:**

- `course_interests.status` gains `"enrolled"` (migration 0038); `INTEREST_STATUSES`,
  `PROVIDER_STATUSES` and `LIVE_STATUSES` in `interests/models.py` all include it, and the module's
  own docstring now distinguishes "provider-reported" from "platform-verified" explicitly, since the
  original text ("interest, not enrolment... a status this platform cannot verify") was correct
  about verification and would otherwise read as contradicted by this change.
- **This closes the structural gap only.** Verified live against the running dev server: a real
  seeded candidate's `/me/matches` call and a real `POST /me/events/course-opened` call produced a
  genuine `1/5 (20.0%)` click-through reading, and a real provider `PATCH` produced a genuine
  `3/15 (20.0%)` enrolment-conversion reading — both numbers are true and both are trivially small,
  because this is a dev/demo database with a handful of seeded actors, not a production platform
  with real candidates and providers using it. Nothing in this ADR changes that.
- **`BL-1.3` is still not authorised.** Whether to proceed to billing now requires either real
  traction numbers clearing a bar the owner sets, or the same kind of explicit override the owner
  already gave once this session for Epic B8 over ADR-045 §1–4. This ADR takes no position on which;
  it only makes the question answerable with a real number instead of "no surface exists."
  ADR-025's instrumentation mandate is otherwise unchanged and still binds. **Answered, 2026-09-29:**
  asked directly, the owner chose to wait for real traffic rather than override. `BL-1.3` is a
  standing not-started as of this date, not an open question — re-raise it only once usage moves
  either metric, or the owner redirects.
- **The frontend does not gain a control for this either, and that is named rather than silently
  shipped**, per this project's established precedent (see ADR-046's own frontend-gap consequence,
  amended after Sprint 37 shipped a build break). `web/src/components/employer/ProviderInbox.tsx`
  hardcodes `{ status: "contacted" }` as the only value its button ever sends; `tsc --noEmit` passes
  clean against the widened union (confirmed, unlike Sprint 37's first pass), so nothing is broken —
  but a provider using the web UI has no way to mark a learner enrolled today, only a direct API
  call can. Building that button, and the two i18n labels it needs, is a small follow-up story, not
  bundled here because it was not part of what ADR-025's gate required.
  **Closed in Sprint 41 (ADR-048's sprint):** `ProviderInbox` now sends the status it is given,
  offers "Mark as enrolled" forward-only, and the learner's `InterestList` names `enrolled` instead of
  rendering a raw message key. A provider's change to `contacted` or `enrolled` also queues a free
  in-app notice to the learner, reversing the "deliberately silent" decision recorded in
  `provider_service.set_status`'s old docstring.


## ADR-048: Hire and Train — An Employer May Prompt a Candidate, Never Learn Who They Are First

**Status:** Accepted (October 2026). Extends ADR-037 (de-identified employer payloads) and the alert
sweep's rules (Sprint 27). Introduces no revenue mechanism and no external integration.

**Context:** The employer console already shows, per vacancy, the candidates missing exactly one
mandatory standard ("nearly ready") and names the standard. What an employer could do about it was
nothing. The market research behind Sprint 41 found that no competitor connects a named missing
standard to a course an employer could sponsor. The risk is the one ADR-037 exists for: any feature
that lets an employer *act on* a specific candidate is one step from identifying them.

**Decision:** An employer looking at a one-standard-short card may open "Train and hire", see the
courses that teach that one standard, and **offer to sponsor** it. The offer is a row in
`sponsor_intents` (migration 0042), unique per (vacancy, candidate). The candidate receives **one
in-app notice** (`sponsor_offer`) naming the organisation, the standard and the course, linking to
the vacancy. **Applying is the act that discloses the candidate** (ADR-037, unchanged): the employer
learns who they are only if they choose to apply.

Six rules, each enforced in one place and each tested:

1. **A reference is a handle, not a key.** `C-XXXXXXXX` is eight hex characters of a profile id. It is
   resolved server-side, only inside *this vacancy's own near-miss pool* (`candidates_for_job`, the
   one scorer), never as a lookup of its own; every way of failing is the same 404.
2. **No second scorer.** "Who may be offered" is `missing_mandatory == 1` over the same ranking the
   console shows.
3. **Unsolicited, so it obeys the alerts' rules:** a candidate with `job_alerts_enabled = false` is
   not messaged, and an offer counts against the same `max_alerts_per_candidate_per_day` an alert does.
4. **The employer is never told which.** A notified candidate and an opted-out or capped one produce
   an identical response; `notified_at` records the difference and only the database holds it,
   because an opt-out is a fact about the candidate. The panel's wording never claims the candidate
   was told.
5. **In-app only, no email.** Unsolicited and employer-initiated; an inbox is not worth it. This is
   conservative and reversible.
6. **An offer needs a course.** If nothing on the platform teaches the standard the offer is refused
   (422): a promise to sponsor training that does not exist cannot be kept.

**Options considered:** 1. Do nothing; leave the near-miss pool informational
2. A direct employer-to-candidate message
3. An offer the candidate may respond to, with no identity disclosed until they apply
4. Reveal the candidate's identity once an offer is accepted

**Trade-offs:**

- Option 1: ✅ No new disclosure surface
❌ Wastes the console's most actionable number, and leaves the gap → course loop one-sided
- Option 2: ❌ A free-text channel from an employer to a de-identified person is exactly what ADR-037
forbids, and a new abuse surface
- Option 3: ✅ Reuses the consent act that already exists (applying); the employer's payload gains no
identity field
❌ The employer cannot tell whether an offer was seen; that is the cost of protecting the opt-out
- Option 4: ✅ A tighter loop
❌ Makes "accepting a training offer" a second disclosure act with its own consent record, and
re-opens the question ADR-037 settled

**Final decision:** Option 3.

**Consequences:**

- Migration 0042 creates `sponsor_intents`, widens `ck_notification_template` (`sponsor_offer`) and
  `ck_analytics_event_name` (`sponsor_intent_recorded`) by hand with frozen value lists. The event is
  nameless: subject is the vacancy, payload `{"notified": bool}`, never the candidate.
- Erasure removes the rows explicitly in both directions (`privacy.service._delete_tenant` and the
  candidate's own deletion), though the foreign keys would cascade -- "everything went" is a claim an
  erasure path must not make on assumption. The rows are **not** part of the DPDP export, matching
  `job_alerts`, which already holds the same kind of record; revisit if the export is widened.
- Lives in `api/modules/alerts/` beside `JobAlert`, which owns "may we write to this candidate
  unsolicited" -- the caps and the opt-out are read from one place. The module's old claim that
  nothing depends on it still holds; it now also has employer-facing routes.
- **No revenue hook.** Sponsorship records an intent, not a payment, an order or a placement fee.
  ADR-025's gate and the owner's 2026-09-29 decision to wait for real traffic are unchanged.


---

## ADR-049: Career Ladders Are Derived at Read Time From Qualification Data, Not From a Stored Graph

**Status:** Accepted (October 2026). Implements the first slice of ADR-008 (the career path engine)
without the inference graph ADR-008 and BL-6.3 assumed. Relaxes BL-6.3's dependency on BL-6.1/6.2 for
this slice only. Introduces no revenue mechanism and no external integration.

**Context:** ADR-008 reserved a `career_paths/` module and BL-6.3 described a graph-based role-transition
engine that rests on `SkillRelation` (BL-6.1, built in Sprint 36) and skill inference (BL-6.2, not
built). `SkillRelation` has **zero rows** and nobody has the labelling effort to fill 21,303 standards.
The national data names no prerequisite between two roles: entry routes carry a *minimum prior NSQF
level* in 1,882 qualification packs and name a specific pack in five. A worker's most natural question
-- "what is the next role up from mine, and what would it take" -- therefore had no answer, while the
market research found nobody else answering it for India's national framework.

**Decision:** A career ladder is **derived at read time** from the qualification data, **states the
evidence for every step**, and **stores nothing**. `GET /me/careers` (module `api/modules/careers/`, the
`career_paths/` ADR-008 reserved, named shorter) lists up to eight roles that build on the person's
own. Three modules each own one question: `skills.roles_above` (which roles build on one), the one
scorer through `matching.score_against_roles` (the person's fit; ADR-037), and
`matching.courses_closing_gap` (which courses teach what is missing).

**What counts as a step.** A current qualification pack `T` is a step from `F` when:

1. `T.nsqf_level > F.nsqf_level`, by at most **2.0 levels** (`LADDER_MAX_RISE`) -- a rung, not a leap;
2. `T` shares **at least one specific compulsory standard** with `F`, compared at concept level (the key
   `courses_closing_gap` uses). A standard in the compulsory list of **three or more sectors**
   (`GENERIC_STANDARD_SECTORS`; 81 of 13,618 standards -- "Employability Skills", "Communication
   Skills") is generic and is not evidence;
3. `T` has compulsory standards of its own, and is current;
4. Divyangjan-track packs are excluded unless the starting role is itself one.

Same occupation and a shared NCO code are **returned and shown as corroboration** and break ties; they
are not grounds. One row per role, collapsing `-SI` and reissued codes by the **same representative
rule role search uses** -- extracted to a single constant (`ROLE_REPRESENTATIVE_ORDER`) so the two cannot
name different packs for one job title; verified byte-identical on 699 real queries before and after.

**The starting role is an explicit choice, resolved by the existing role search, and nothing is stored.**
Without one the service guesses once, from the latest current job title then the preferred roles, and
**trusts only an exact or alias match of the person's own words**. A prefix, substring or typo is a
guess about a guess, and every step beneath a wrong starting role would look equally confident. A guess
is returned as `anchor_source: "guessed"` and the page says so; an unsure guess is `needs_choice` and
the page asks.

**What the real data showed (4,340 roles with compulsory standards, whole corpus):**

- **38% have at least one step** (1,661); 767 hit the eight-step cap; the query takes 57 ms median,
  72 ms p95.
- **Coverage is very uneven by sector.** BFSI 0% of 129, Information Technology Sector 1% of 178,
  Instrumentation 4%, Electronics 6% of 218, IT-ITeS 8% of 191, Management 12% of 319. In those sectors
  every pack carries its own standards, so nothing is shared across levels. This is a limit of the
  *data*, and the page says "we found none ... that can mean there is none, or that the data does not
  link them" rather than "there is none".
- **Without the generic-standard rule** a General Duty Assistant "led" to an Automotive technician and a
  Welder to a Green Hydrogen technician through one shared employability unit; coverage then read 54%
  and was mostly noise.

**Options considered:** 1. Fill `SkillRelation` by hand/inference, then traverse it (BL-6.2/6.3 as written)
2. Derive from qualification data at read time, with evidence (chosen)
3. Derive and also admit "same occupation, higher level" as grounds
4. Persist a ladder per candidate

**Trade-offs:**

- Option 1: ✅ Could express any transition ❌ No labelled edges exist and a hand-built graph is a claim
  nobody maintains; blocks the feature on the largest piece of work in Epic B6
- Option 2: ✅ Every step carries the evidence it came from; nothing to go stale; no new table; reuses
  the one scorer ❌ 38% overall and ~0% in several large sectors
- Option 3: ✅ Measured on a sample of 724 roles: 60% have a step (IT-ITeS 11% → 65%) ❌ 27% of the
  steps then share no standard at all, and narrowing it (occupations of at most 15/30 packs: 54%/57%,
  16-24% no-shared-standard steps; same sub-sector as well: 52%, 16%) did not remove them. "Same
  occupation, one level up" is a weaker claim than a shared standard and mixing the two would present
  them as equal. **Not adopted; revisit with a domain expert** -- if adopted, as a separately labelled
  weaker tier, never ranked with the first.
- Option 4: ✅ Faster ❌ A stored ladder is a claim about a person that goes stale; needs erasure,
  export and a consent story. The gap panel for a rejected application (Sprint 41) took the same view.

**Final decision:** Option 2.

**Consequences:**

- **Migration 0043 adds one event** (`career_ladder_viewed`), hand-written with a frozen value tuple. No
  table, so **erasure and the DPDP export have nothing to cover** -- verified, not assumed. The event is
  subject to the *role* the ladder started from; the payload is counts and whether the start was a guess,
  never a standard (a skill list describes a person) and never a name.
- `skills.roles_above` is a taxonomy fact and lives with the taxonomy. `matching.score_against_roles`
  builds `RequiredSkill` from a pack's **compulsory** standards (electives are "choose one of these",
  as `course_role_alignment` already says) with `importance` a flat 3 -- the source's `weightage` is an
  assessment mark, not how much a standard matters to the work -- and the lowest entry-route experience
  floor rounded up. `score_match`, the weights, the retrieval limit and the sort keys are untouched, so
  the golden set is unaffected. `EntryRouteFit` gained one shared helper so a job's qualification and a
  ladder's read `QpEntryRoute` the same way.
- Because every compulsory standard counts as mandatory, a role the person only partly holds is capped
  at 45 as a vacancy would be. That is the scorer's rule applied consistently, and the page shows
  "N mandatory standards missing" beside the bar rather than a bare low number.
- **The cost grows with the steps shown and nothing else:** scoring batches (six statements however many
  roles), the course lookup is six statements per step. Eight steps is the cap.
- **`SkillRelation` stays an unused foundation**, and BL-6.2 stays `[LATER]`. If a labelled graph ever
  exists, it can add steps; it does not replace the evidence rule.
- The page lives at `/career-paths`, not `/careers`, which is the company's own hiring page linked from
  the footer.

---

## ADR-050: Role Search Ranks Disability-Track Packs One Tier Lower, and They Are Never an Alias Target

**Status:** Accepted (October 2026). Refines the role-search rules in ADR-041's search path and the
alias rules written into `role_aliases.py` since Sprint 23. Introduces no migration and no external
integration; scoring, the golden set and `make evaluate` are untouched.

**Context:** Career ladders (ADR-049) and the profile's role picker both start from `search_roles`, so
a wrong result there now starts a wrong ladder and a wrong profile. Running the search against the real
corpus, which the small fixture corpus could not show, found four faults:

1. **A disability-track pack could lead a general one.** All 69 roles that have a disability-track pack
   carry a `PWD/` code, whether or not the title says "Divyangjan" (31 do not). 57 of the 69 exist **only**
   as a disability-track pack and 12 have both kinds. `data entry operator` led with three Divyangjan packs.
2. **Fourteen aliases pointed at a disability-track pack.** `cook`, `telecaller`, `salesman` and eleven more
   resolved to three roles whose representative pack is `PWD/`-coded. The rule "point at the general pack"
   had been written in `role_aliases.py` for twenty sprints, and the checker could not see a breach.
3. **A half-typed alias lost to a literal prefix.** Both score 3.0, and the tie was broken by similarity to
   the pack's name, which always favours the literal one: `war` listed Warper above General Duty Assistant.
4. **Multi-word queries found nothing.** `hotel waiter` matched neither as a substring nor by trigram
   (word similarity 0.54 against a 0.6 threshold).

**Decision:**

- **A disability-track pack is demoted by one match tier** unless the query asks for one (it contains
  `divyang`, `pwd` or `disab`) or is exactly the pack's title. Implemented as a 1.01 subtraction from the
  match score, so a disability-track *prefix* match (3.0) falls just below a general *contains* match (2.0)
  and stays above weaker guesses. `ROLE_REPRESENTATIVE_ORDER`, shared with career ladders, now puts a
  general pack before a disability-track one when a role has both.
- **No alias may resolve to a disability-track pack, and none may shadow a role's exact title.**
  `alias_problems()` replaces `unresolved_aliases()` and **fails** on both; it also **reports** every prefix
  of three or more characters that two or more targets claim, as information, never a failure.
- **A half-typed alias beats a literal prefix when they tie** (`via_alias > 0` ahead of `closeness`).
- **A multi-word query matches a title containing every word, in any order**, scored 1.5: above the fuzzy
  ceiling (0.9) and below a whole-string "contains" (2.0), so a guess never outranks something typed. A new
  `words` match kind carries it.
- **Withdraw-then-reapply is closed by the same logic** (BL-12.6): an application an employer has decided
  on can no longer be withdrawn, so a rejection cannot be wiped by withdrawing and reapplying.

**Options considered:** 1. Leave ranking alone and fix only the alias targets
2. Demote disability-track packs to **last place**, whatever the match
3. Demote by **one match tier** (chosen)
4. Hide disability-track packs unless asked for

**Trade-offs:**

- Option 1: ✅ Smallest ❌ Leaves `data entry operator` and `barista` leading with a pack the person did not
  ask for, and a ladder or profile anchored to it.
- Option 2: ✅ Simple to state ❌ Tried first and rejected on the real corpus: `hr executive` has one literal
  match, a disability-track pack, and last place ranked it below "Executive Housekeeper". A demotion that
  buries the only literal match is worse than none.
- Option 3: ✅ Loses to an equally good general pack, which is the case it exists for, and still reaches a
  disability-track pack when it is the best answer ❌ A person who wants the disability track and does not
  say so still sees it, one tier lower. The words `divyangjan`, `pwd` and `disab` lift it.
- Option 4: ❌ A disability-track-only role (57 of them) would become unfindable to the people it is for.

**Final decision:** Option 3.

**What the real data showed** (726 queries: every fifth role title, plus 35 known-bad queries, before and
after, 3,268 and 3,274 hits):

- **11 top results changed, all explained.** Seven are the alias tie-break on three-letter prefixes
  (`war`, `car`, `com`, `cou`, `dat`, `mob`, `sof`). `data entry operator` is the demotion.
  `telecaller` now reaches *Call Center Executive*; `cook` and `salesman` lost their aliases (below).
  No exact-title query changed.
- **The exact-title exemption exists because the first version had no exception**: `pressman`,
  `domestic it helpdesk attendant` and `solar pv installer - civil`, typed in full, were demoted below
  something else. They exist only as disability-track packs.
- **Aliases: 124 to 114.** Three targets had a general twin and were re-pointed (*Assistant Chef* to
  *Kitchen Trainee*, *Customer Care Executive(Call Center)* to *Call Center Executive*). *Retail Sales
  Associate* has no general pack, so its seven keys were removed rather than guessed, and `cook` was removed
  because the corpus has a role literally named *Cook (Multi-Cuisine)*. The new checker's first run found
  two more: `web developer` and `security analyst` are exact titles of roles that an alias was sending
  elsewhere.
- **Not fixed, and recorded:** the prefix collisions (`car`, `com`, `dat`, `mob`, `sof`, `war`) are
  ambiguous by nature. The tie-break now favours an alias-backed role, but which of several alias-backed
  roles leads is still arbitrary. Only a person who knows the labour market can curate that.

**Consequences:**

- **Coverage is unchanged and still thin**: 43 distinct roles of 3,417 have an alias (1.3%), in 17 of 43
  sectors. The curated batch was deliberately not part of this sprint. Lay terms are labour-market
  knowledge; nothing in the repository contains them, and logging what people type would conflict with
  ADR-023.
- **`make check-role-aliases` cannot run in CI** (it needs the 21,303-standard corpus). Its rule logic is
  covered by tests on a fixture corpus instead.
- **Role search reads the `role_aliases` table, not the dict.** An edit to `role_aliases.py` reaches search
  only after the table is re-projected (`make seed`, or `_seed_role_aliases` alone), and the snapshot
  comparison for this ADR first ran against a stale table.
- Career ladders inherit the representative-pack rule, so a ladder's starting role is the general pack
  where there is one.


## ADR-051: Changing Who Owns an Organisation Is Serialised per Organisation, and Handing It Over Is One Act

**Status:** Accepted (October 2026). Refines the "last owner" rule of Sprint 25 (ADR-038/039) and adds BL-9.1.
One migration (0045, two CHECK widenings). No external integration; scoring is untouched.

**Context:** Sprint 25 made it impossible to empty an organisation of owners: removing, demoting or leaving
as the only owner is a 409, asked in one function (`_refuse_if_last_owner`) for all three paths. Handing an
organisation to somebody else was then two requests — promote a colleague, then leave — and the second could
fail on its own. Closing that gap raised the question the backlog called "the locking decision", and answering
it exposed a fault older than the feature:

1. **The last-owner guard was a check followed by a write, with nothing between them.** Under READ COMMITTED,
   two owners acting at the same moment each count two owners and each pass. A demotes B while B demotes A,
   or both leave, and the organisation has **nobody in charge** — the outcome Sprint 25 exists to prevent.
   Reproduced before any fix: both requests returned success and the owner count was **0**.
2. **Account erasure asks the same question through its own grouped count** and had the same gap: an owner
   erasing their account while the other owner leaves.
3. **Authority was checked once, at the start of the request.** An owner demoted in between still completed
   an owner-only act.

**Decision:**

- **Every act that changes who owns an organisation first takes a lock on the tenant row**
  (`SELECT ... FOR NO KEY UPDATE`, `_lock_ownership`): role change, removal, leaving, the new handover, and
  account erasure. Taken **before** the count and held until the commit. Erasure locks every organisation the
  account belongs to in **ascending id order** (`lock_ownership_of`), the only place more than one is held.
- **After the lock, the caller's authority is re-read** (`_require_owner_now`, 403) with
  `populate_existing`, so an owner-only act cannot complete on authority another transaction has withdrawn.
  Leaving is anybody's act and skips it.
- **`POST /org/{slug}/transfer-ownership`** `{user_id, then: "admin" | "leave"}`, owner only. The promotion and
  the step-down commit together. The target must already be a **member** (an invitation cannot carry `owner`,
  so somebody outside is invited as an admin first), must not be the caller (422) and must not already be an
  owner (409: that is a role change, and this act means one thing). `then` defaults to `admin`; there is no
  "stay as owner".
- **One analytics event** (`ownership_transferred`, payload `{then}`), not also `member_role_changed`, which
  would count one decision twice.
- **The new owner is emailed** (`ownership_received`, `recipient_kind="user"`), queued **before** the commit so
  a notice that cannot be written leaves nobody made an owner in silence. The payload is the organisation's
  name and a link — no address. A phone-only account is `skipped`, as for every email here.

**Options considered:** 1. Fix only the handover, leave the guard as it was
2. Advisory lock keyed on the tenant id
3. `SERIALIZABLE` transactions for these functions
4. **Row lock on the tenant, `FOR NO KEY UPDATE`** (chosen)

**Trade-offs:**

- Option 1: ✅ Smallest ❌ Ships a new way to reach the old race, and leaves the old paths racing.
- Option 2: ✅ No row involved ❌ Invisible in the usual lock views, and nothing in the schema says what it
  protects.
- Option 3: ✅ Strongest guarantee ❌ Serialisation failures need a retry loop around the whole request layer
  for one rare act.
- Option 4: ✅ Visible, local to one organisation, needs no retry, and `FOR NO KEY UPDATE` does not conflict
  with the `FOR KEY SHARE` a membership insert takes through its foreign key, so an invitation being accepted
  is never held up ❌ It also serialises organisation-profile edits for the few milliseconds it is held, which
  nobody will notice.

**Measured:** four tests run two real sessions at once through the service (mutual demotion, mutual leaving, an
owner erasing against the other leaving, and a demoted owner's stale authority) — each **fails without the
lock** and passes with it. Removing the lock, the authority re-check, the already-owner refusal or the
self-transfer refusal each fails exactly its own test. Live, with throwaway organisations: 13 of 13 checks and
exactly two ownership emails for two handovers.

**Consequences:**

- **The race tests need committed rows.** The suite's `db` fixture is one rolled-back transaction, which cannot
  show two sessions interleaving, so `tests/test_ownership_race.py` builds its own organisation through the
  sessionmaker, deletes it afterwards, and widens the window on purpose (a sleep after the count) so the result
  does not depend on scheduler timing.
- **Any new writer of `Membership.role` must take `_lock_ownership` first.** `tests/test_module_boundaries.py`
  cannot see that; this ADR and the docstring on `_lock_ownership` are where it is written down.
- **The UI is an inline panel, not a dialog.** One choice and one button, and a modal would put Radix's dialog
  on the team page's first load. No typed-name gate, unlike organisation deletion: nothing here destroys anybody
  else's records and the new owner can reverse it.
- Not built: inviting somebody **as** owner, handing over to a non-member, undo, approval by two owners.


## ADR-052: A Check That Guards an Invariant Takes a Lock; a Cap That Deters Abuse May Stay Advisory

**Status:** Accepted (October 2026). Generalises ADR-051 from ownership to the candidate-facing write paths, and
refines the role-search tiers of ADR-050 (BL-12.14). No migration and no external integration.

**Context:** Sprint 44 found that the last-owner guard was a check followed by a write, and that nothing in the
suite could show it, because every test shares one connection inside one rolled-back transaction. Reading the other
check-then-write paths suggested the same blind spot; each suspicion was reproduced with two real requests before
anything was changed. Two of them were real, in different ways, and one was not what it first looked like:

1. **A double-submit raised an unhandled unique violation, a 500.** Two taps on Apply (or on registering interest, or
   on saving a vacancy) each find no row and each insert; the constraint refuses the second and nothing catches it.
   Data stayed right, the answer was wrong, and the target device is a phone on mobile data where a retry is normal.
   **A first attempt at the test passed** — because a brand-new candidate's first two requests race to create their
   *profile*, a different race that hid this one. The helper now creates the profile first.
2. **Withdrawing against a decision was a lost update.** `withdraw()` checked the status and then wrote; the employer's
   `set_status` checked "not withdrawn" and then wrote. Run together, both reported success. A candidate's withdrawal
   overwrote an employer's rejection (what BL-12.6 exists to prevent), and an employer's status change overwrote a
   withdrawal, leaving a learner's contact visible on a row they had revoked: a DPDP concern, not an annoyance.
3. **Re-applying after a withdrawal, twice at once, queued two emails to the employer** — no constraint is involved
   (both find the same row), so nothing failed, and a duplicate went out.

**Decision:**

- **A check whose result must still be true when the write lands takes `SELECT ... FOR UPDATE` on the row it read**
  (`of=` the entity, so a joined relationship cannot make PostgreSQL refuse it) and re-reads under the lock with
  `populate_existing`. Applied to `applications.service.apply` (the existing row) and `withdraw`, `employer_service.
  set_status`, `interests.service.register`, and `provider_service.set_status`.
- **Where there is no row to lock yet, the unique constraint is the arbiter**, inserted inside a savepoint
  (`begin_nested`) so losing the race undoes only the insert, and the loser gets the answer it would have got a
  moment later: **409 "already applied"** for apply and interest, **the winner's row** for saving a vacancy, which
  is idempotent.
- **A learner's withdrawal of a course interest takes no lock, deliberately.** It is unconditional and always the last
  word, so its check cannot go stale; the race is closed on the provider's side, which locks and refuses a withdrawn
  row. A lock there could not change the outcome, and a mutation check confirmed that no test can fail without it.
- **Caps stay advisory** (50 applications a day, 20 pending invitations, 60 skills). They deter abuse rather than
  guard an invariant, and locking every application per candidate would turn "about 50" into "exactly 50" at the cost
  of serialising a hot path for a precision nothing depends on. Under concurrency a cap can be exceeded by a few.

**Options considered:** 1. Catch `IntegrityError` everywhere and change nothing else
2. Compare-and-set (`UPDATE ... WHERE status = :seen`, check the row count)
3. **Row locks, plus the constraint as arbiter where there is no row** (chosen)
4. `SERIALIZABLE` for these requests

**Trade-offs:**

- Option 1: ✅ Smallest ❌ Fixes the 500 and leaves the lost update, which is the serious one.
- Option 2: ✅ No lock held across the request ❌ Needs a second code path per transition and an ORM bypass, and the
  re-check the lock gives us for free ("is it still withdrawable?") has to be written out by hand each time.
- Option 3: ✅ The same pattern as ADR-051, the code reads as it did with one extra clause, and the check and the write
  are provably about the same row ❌ A request holds a row lock for the length of its transaction — one candidate's
  application, for milliseconds.
- Option 4: ✅ Strongest guarantee ❌ A retry loop around the request layer for paths that are one row each.

**Role search (BL-12.14), in the same sprint.** Sprint 43 let a synonym admit a row into role search and then scored it
as a fuzzy guess; the synonym applied only to the whole query string. `mfg technician` led with Technician -
Mechatronics, and `mfg operator` with Loader Operator. Two tiers now sit **below every literal one** — 1.4 for the query
with its abbreviations spelled out found whole in the title, 1.3 for every word met by itself or a synonym, in any
order — because what a person typed must outrank what we expanded it to. A first design put the phrase at 1.9, above
"all the typed words in any order" (1.5); reviewing it against that principle, before it shipped, caught it. Measured on
764 real queries: 6 lists changed, 4 of them at the top, every one an improvement, no exact-title or single-word query
moved. **The backlog's premise was partly wrong:** `tech` leading with Technical and Technician is correct, not a defect.

**Consequences:**

- **Race tests need committed rows and two requests that each hold their own session.** `tests/concurrency.py` builds
  the world through the real routes and sessionmaker and erases it afterwards. Two techniques: **hold a row lock from a
  third session and release it once `pg_stat_activity` shows both requests waiting** (deterministic, no sleeps), and
  widen a window by wrapping the function after a check. The suite's `db` fixture cannot show a race and must not be
  used for one.
- **A test that passes before the fix proves nothing.** One of the first four double-submit tests passed on unfixed code
  for the wrong reason (the profile race above). Every guard here was mutation-checked; one lock failed no test, which
  is how it was found to be redundant and removed.
- **Still advisory and still racy:** the three caps, and `_close_if_filled` (two hires landing together against one
  position close the vacancy at the head-count, by design). Not audited this sprint: slug uniqueness on publish.

