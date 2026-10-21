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

**Status:** Accepted. **Superseded in part by ADR-040** (the tooling: structured JSON logs to stdout). OpenTelemetry, Prometheus and Grafana remain the destination and are deferred, not built.

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

**Status:** Accepted (September 2026). **Superseded in part by ADR-038** (the organisation half: email one-time code, no password). The rule that a candidate signs up by phone still governs.

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

**Status:** Accepted (September 2026). **Superseded in part by ADR-041** (the two-language assumption: a language is a messages file and rows). Hindi and English remain the launch pair.

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

**Status:** Accepted (September 2026). **Superseded in part by ADR-038** (the authenticated employer console ships to production, behind a sign-in). The rule that no employer-facing payload identifies a candidate stands and is tested; only the unauthenticated demonstration console is local-only.

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


## ADR-053: Dependency Majors Arrive Alone, and a Held Major Carries Its Reason

**Status:** Accepted (October 2026). Refines the "Dependabot opens grouped weekly updates" decision of Sprint 20.
No migration and no external integration.

**Context:** Five dependabot pull requests sat open, none mergeable: three GitHub Actions bumps and two overlapping
npm PRs, 13 and 2 days old. The cause was our own configuration. `dependabot.yml` grouped every npm update
(`patterns: ["*"]`), so a major version that could not work turned the whole weekly PR red, and the safe bumps inside
it waited with it. The newest PR, merged with current `main` and run through every gate:

| Attempt | Install | `tsc` | Tests | Lint | Build + budget |
|---|---|---|---|---|---|
| As dependabot sent it | **fails** | – | – | – | – |
| TypeScript held at 5 | ok | **fails** | pass | **crashes** | **fails** |
| Every major held back | ok | ok | 371 pass | ok | ok |

- **TypeScript 7 cannot install.** `openapi-typescript`, which generates the TypeScript client (`make gen-api`),
  declares a TypeScript `^5.x` peer, so `npm ci` fails with `ERESOLVE`.
- **ESLint 10 crashes** inside the React plugin that ships with `eslint-config-next`, so `npm run lint` throws
  rather than reporting.
- **vitest 5 works, with one change.** It runs on vite 8's oxc transform, and the `esbuild: { jsx: "automatic" }` option
  `vitest.config.mts` used is now a type error. The replacement was not added: with no JSX option at all all 371 tests
  pass, because the transform reads the tsconfig itself. A first draft kept an explicit `oxc.jsx` setting and a comment
  claiming it would make a future default change fail loudly; removing it showed nothing depended on it, so the claim
  was false and the setting was deleted.

**Decision:**

- **Minor and patch updates are grouped; a major arrives as its own pull request.** Applies to the npm and uv groups.
  GitHub Actions are not grouped, so each already arrives alone.
- **TypeScript and ESLint majors are ignored, with the reason written in `dependabot.yml`** and a condition for revisiting
  each: `openapi-typescript` accepting TypeScript 7, and `eslint-config-next`'s React plugin running under ESLint 10.
  They appear as a backlog item (BL-13.6) rather than as red pull requests that remind nobody of anything.
- **The safe subset was applied together** (react and react-dom 19.3.0, TanStack Query, next-intl, tailwind-merge,
  axe-core, testing-library), plus **vitest 5 and jsdom 30**, which pass every gate. `@types/node` moved from 20 to 24 to
  match the runtime CI uses (Node 24); types for a different major than the runtime describe an API that is not there.
- **The three Actions bumps (checkout 4→7, setup-node 4→7, setup-uv 5→7) are not applied here.** They cannot be exercised
  locally; each is a pull request whose own CI run is the test, merged one at a time.

**Options considered:** 1. Leave the group as it was and close the red PRs by hand each week
2. Ungroup everything (one PR per dependency)
3. **Group minor and patch, isolate majors, hold the two that cannot work** (chosen)
4. Pin everything and update by hand each quarter

**Trade-offs:**

- Option 1: ✅ No change ❌ The safe updates never land and the next advisory fix is buried in the same red PR.
- Option 2: ✅ Each PR is independently mergeable ❌ Dozens of PRs a week for a team of one.
- Option 3: ✅ The weekly PR should pass, a major is judged alone, and a held one costs a line of config and a backlog
  item ❌ An `ignore` entry is a promise to come back; the backlog item and the stated condition are what keep it.
- Option 4: ✅ Quiet ❌ This is how the lint toolchain ends up three majors behind with no idea what blocks it.

**Consequences:**

- **Revisit BL-13.6 when either condition changes.** Removing the `ignore` entry makes the PR reappear.
- **`npm audit --omit=dev` (what CI runs) reports 0 vulnerabilities; a full `npm audit` reports a high-severity
  `braces` advisory** reached only through `eslint-config-next`, in the lint toolchain and not shipped. Noted, not acted
  on: the suggested fix is a downgrade to `eslint-config-next@14`.
- **Newer npm prints `allow-scripts` warnings** for two packages with install scripts (`fsevents`, `unrs-resolver`).
  Nothing fails, and the build and tests pass without approving them.

- **Re-checked 2026-10-07 (Sprint 52); both holds stand.** `eslint-config-next` is at 16.4.0 and still depends on `eslint-plugin-react` `^7.37.0`, whose latest release is 7.37.5
  (the version already installed) with a peer range that stops at ESLint `^9.7`; ESLint itself is at 10.12.0. `openapi-typescript` is still 7.13.0 with a TypeScript `^5.x` peer. Read from the
  registry rather than by installing ESLint 10 in a worktree, because the blocker is an upstream peer range that has not moved, so an install would only re-prove the crash. Re-check when
  `eslint-plugin-react` publishes a release whose peers include ESLint 10, or `openapi-typescript` one that admits TypeScript 7.


## ADR-054: Role Aliases Are Edited by an Operator, the Table Is the Source of Truth, and the Seed Never Overwrites an Operator

**Status:** Accepted (October 2026). Supersedes the "the dict is the authored source of truth" arrangement of Sprint 23
and Sprint 40. One migration (0046). No external integration; scoring and the golden set are untouched.

**Context:** Role-alias coverage is the product's weakest point: **43 of 3,417 roles** have an alias. The owner decided that
a curated batch needs a labour-market reviewer, which is right, and exposed why none had been written: a reviewer cannot
work. Aliases lived in a Python dict (`role_aliases.py`), and `scripts/seed_skills.py` projected them into the
`role_aliases` table by **deleting every row and rewriting it**. So only an engineer could add one, every batch needed a
commit and a deploy, and an alias added any other way vanished at the next seed.

**Decision:**

- **The table is the source of truth.** `role_aliases` gains `source` (`seed` | `operator`), `retired_at` and `created_at`;
  every existing row is `seed`. The dict only seeds.
- **The seed never touches an operator's work** (`sync_seed_aliases`): it inserts what is missing, updates a `seed` row whose
  target changed, and removes a `seed` row the dict no longer names. A row with `source='operator'` — including a retired
  one — is left exactly as it is, whatever the dict says.
- **Nothing is deleted by hand.** An operator **retires** an alias: `retired_at` is set and the row is handed to the operator,
  so a dict that still names the key cannot bring it back. Role search ignores retired rows. Adding a retired term again
  revives the same row.
- **`role_alias_events`** is the audit record, because those edits are not in version control the way the dict was:
  append-only, **naming** the alias (a copy of key and target) rather than referencing it, since the seed may delete the row
  an event describes; `actor_user_id` is `SET NULL` so the record outlives its author. Not `analytics_events`, for
  `TenantVerificationEvent`'s reasons (purged past retention; `record()` swallows its failures).
- **An alias is valid if it passes the checks `make check-role-aliases` runs**, from the same function (`alias_problems`),
  not a copy: the target must be a current role with standards, never a disability-track pack, and the key must not be a
  role's exact title aliased elsewhere. Ambiguous prefixes are **warnings**, never refusals. The target is stored as the
  corpus spells it, and the screen offers it from role search so it is **picked, not typed**.
- **Admin tier only** (`OPS_ALIAS_EDIT`, not on the support tier): an alias changes every candidate's role search, the same
  public blast radius that kept `OPS_ORG_VERIFY` off it (ADR-044). A support operator gets 403 and the screen says so.
- **`make check-role-aliases` now checks the table**, operator rows included and retired ones excluded. Checking the dict
  would have been checking exactly what an operator's edits are not.

**Options considered:** 1. Keep the dict as the truth and have the screen export a patch for an engineer to commit
2. A second table for operator aliases, merged at read time
3. **One table, with ownership per row and a seed that respects it** (chosen)
4. Drop the dict and seed from a data file

**Trade-offs:**

- Option 1: ✅ Reviewable in a diff ❌ Keeps the engineer in the loop for every batch, which is the thing being removed.
- Option 2: ✅ The seed can stay "delete and rewrite" ❌ Role search joins two tables and the checker reads two; two
  places for one fact.
- Option 3: ✅ Search is unchanged but for one filter, and the seed's rule is one sentence ❌ Operator edits are no longer
  in a diff; the audit table is the only record, and it has to be trusted.
- Option 4: ✅ Data, not code ❌ Moves the problem without solving it.

**Consequences:**

- **Raises capability, not coverage.** Coverage is 43 of 3,417 until somebody uses it.
- **The seed change is the dangerous part**, and is tested as a property: an operator's row survives a re-seed, is not
  overwritten by a seed that names it, and a retired one is not revived. Replacing the sync with the old delete-and-rewrite
  fails five tests.
- **Two operators adding one term at once** is a 201 and a 409, never a 500 (the unique constraint inside a savepoint,
  ADR-052); proven on committed rows, and the test fails without the handling.
- **An operator cannot edit a target in place**: retire, then add. Two steps, deliberately, so the history says what
  happened.
- **Typed searches are not logged** (ADR-023), so nothing here says which lay terms people actually use. A worklist from
  candidates' preferred-role titles (counts only, hidden below three) was considered and left out; with 42 candidates it
  would show nothing.


## ADR-055: What Erasure Deletes, the Export Shows, and a Guard Keeps Them in Step

**Status:** Accepted (October 2026). Refines the DPDP export and erasure of Sprint 20 (ADR-023 adjacent). No migration and no
external integration.

**Context:** Export and erasure are the two halves of the rights of access and of erasure, and only one half had been kept in
step with the schema. A scan of every foreign key into `users`, `candidate_profiles` and `tenants` found the erasure side
sound: **all of them are `CASCADE` or `SET NULL`**, so no stray constraint can block an erasure or leave a row behind. The export
side was not. Four things held about a person were erased correctly and **never shown to them**: job alerts (Sprint 27), ratings
(Sprint 37), sponsorship offers (Sprint 41) and the notices addressed to them. "We delete it but cannot show it" is the awkward
half to be missing, and nothing would have caught the next table being the same.

**Decision:**

- **The export now carries all four** (`job_alerts`, `sponsorship_offers`, `ratings_received`, `ratings_given`, `notices`), built
  by small helpers beside `export_account`. An empty account exports empty lists, not missing keys.
- **Nobody else is named.** A received rating shows the rating, the comment, the vacancy and the **organisation** that gave it
  (who they dealt with, so naming it tells them nothing new) and never `author_user_id`. A sponsorship offer names the
  organisation, the vacancy and the standard, never the person who made it. A rating given by the person describes the other
  party **only by role** ("a worker", "the organisation"), so exporting an employer's account does not hand them a worker's name.
  A rating about an organisation is that organisation's reputation, not its member's, and goes only to the person who wrote it.
- **A review whose author later erases their account stays, with the author blanked** (the existing `SET NULL`). Deleting it would
  change another person's earned reputation, and the review is about *them*. This is stated here and was an owner decision.
- **A structural guard** (`tests/test_privacy_coverage.py`) walks the SQLAlchemy metadata for every table with a foreign key into
  a person, plus `notifications` by name (the row names a recipient and holds no address, so no schema walk finds it). Each must be
  in `EXPORTED`, mapped to a real key of the document, or in `EXEMPT` with a written reason. It asserts it **found** tables before
  asserting anything about them, fails on a stale entry, and a second test feeds it a table that does not exist, as the
  route-delegation guard does. The three exemptions are operators' audit trails, not data held about a data subject.
- **The two halves are held to each other**: a test exports a candidate who has one of everything, then erases the account and
  asserts every record the export showed is gone.

**Options considered:** 1. Add the four fields and nothing else
2. Add them and a written checklist for the next table
3. **Add them and a guard that fails on the next one** (chosen)
4. Generate the export from the schema automatically

**Trade-offs:**

- Option 1: ✅ Smallest ❌ The next table repeats the gap. The Sprint 27, 37 and 41 tables are the proof.
- Option 2: ✅ Cheap ❌ A checklist is what was already there, in the form of this project's own conventions, and was not followed.
- Option 3: ✅ A forgotten table fails a build, with the instruction for fixing it in the message ❌ A new table needs one line in
  one of two lists, which is the intended friction.
- Option 4: ✅ Never out of date ❌ A generic dump cannot decide what to withhold. Whom a rating is "by" is a privacy decision per
  table, and an automatic export would make it silently.

**Consequences:**

- **Any new table that references a person fails `test_every_such_table_is_exported_or_excused` until it is handled.**
- The guard sees foreign keys. A person's data stored **without** one, as `notifications` is, must be added to `NON_FK_PERSONAL`
  by whoever writes it; the guard cannot find what the schema does not link.
- Not done: a retention limit on sent notifications, which accumulate for as long as the account lives. They hold vacancy and
  organisation names, no address, and are erased with the account.



## ADR-056: Retrieval Ranks Before It Caps, and What It Ranks By Is a Bound, Not a Second Scorer

**Status:** Accepted (October 2026). Refines ADR-007's two-stage matching and leaves ADR-036 and ADR-037 standing. No migration and
no external integration.

**Context:** Matching retrieves a bounded set and scores only that, because scoring everyone against everything does not survive
growth (ADR-007). Until now the bound was a cap of 500 applied **before** ranking, by an arbitrary key: `Job.id` for a candidate's
vacancies and the UUID's text for a vacancy's candidates. The code said so, in a comment: ranking retrieval by fit was "out of scope
until the catalogue is large enough for the cap to bite". Nobody had looked at whether it bit, because every number this project
quotes comes from 42 candidates and 151 vacancies.

Sprint 49 built a harness (`make seed-scale`, `make benchmark`): a separate database `iism_scale`, deterministic synthetic rows
(50,042 candidates, 890,778 candidate skills, 5,148 open vacancies; the commonest standard held by 46,025 candidates), skewed
popularity, and mixed evidence, level floors and experience floors so that the number being measured is not flattered by a
uniform world. Recall is measured against **exhaustive truth**: every vacancy (or candidate) sharing a standard, scored through the
same `score_match`, with no cap and no proxy.

| At 50,042 candidates, 5,148 vacancies | Before | After (K = 500) |
|---|---|---|
| Candidate: true top 20 vacancies returned | **2.9 of 20** | **20 of 20** |
| Employer: true top 20 candidates returned | **1.2 of 20** | **20 of 20** |
| Employer: points the best returned is short of the best that existed (mean / max) | 3.0 / 11 | 0 / 0 |
| `match_jobs` latency, p50 / p95 | 92 / 185 ms | 108 / 186 ms |
| `candidates_for_job` latency, p50 / p95 | 921 / 1,148 ms | 462 / 569 ms |
| Scarce skills, one employer / whole market | 495 / 470 ms | 119 / 108 ms |

The page *looked* right throughout, because the scorer ordered correctly whatever it was handed. The best matches were never in
front of it. Two further defects sat in the employer path: it loaded every `(candidate, standard)` pair that touched any of the
vacancies into Python (16 seconds for a popular standard) and then filtered with `IN (every candidate)`, which **crashes past
asyncpg's 32,767 bind parameters** -- a pool of 47,109 sharers did exactly that when uncapped.

**Decision:**

- **Retrieval keeps the K highest *upper bounds* on the score** (`api/modules/matching/retrieval.py`). The score is coverage plus
  level, experience and evidence, capped when a mandatory standard is missing. Coverage and the mandatory count come from the
  database in one aggregation; the other three components are not known without loading the person, so they are taken as full
  marks (each is at most 1). The cap is applied to that exactly as `score_match` applies it. The result can only overstate:
  `score - 0.5 <= 100 * bound` for every pair, the half point being the scorer's own rounding. A pair outside the K therefore cannot
  have a higher unrounded score than the K-th pair's bound.
- **It is a retrieval ranking and never a score.** It is not returned, stored, logged or shown; every number a person sees still comes
  from `score_match` (ADR-036, ADR-037). The rule that stops the two drifting is a test, not a comment: `tests/test_retrieval.py`
  asserts the bound is never below the score, for two weightings, over a randomised marketplace with concepts spanning two rows,
  mixed evidence, level and experience floors and mandatory standards -- **and that it is tight** when nothing else varies, which a
  bare "never below" cannot see (an over-count passes it).
- **The employer side is one window query per vacancy**, not a load into Python: `row_number() over (partition by vacancy order by
  bound desc, profile id) <= K`. It walks *from the requirements* to the skill rows that satisfy them and on to the holders through
  `candidate_skills.skill_id`'s index; the first version let the planner build every candidate's held keys across the table, which
  it answered with a scan of all 890,778 rows (about 350 ms) -- caught by `EXPLAIN ANALYZE`, not by a test.
- **Held-skill and profile loads are chunked** at 5,000 ids per `IN`, so no pool, and no number of vacancies, can reach the ceiling.
- **Scarce skills count holders only for the contenders.** Holders are the *second* sort key, after how many vacancies ask for the
  standard, so they matter only for standards tied with the last one that can make the list.
- **K is a setting** (`MATCH_RETRIEVAL_LIMIT`, default 500, at least 20). It is chosen by measuring, which the harness now makes
  possible; the default is the number the owner approved, and the table below is the evidence for changing it.

| K | Candidate overlap | Employer overlap | `candidates_for_job` p95 |
|---|---|---|---|
| 20 | 18.2 / 20 | 12.5 / 20 | 137 ms |
| 50 | 20 / 20 | 17.0 / 20 | 218 ms |
| 150 | 20 / 20 | 20 / 20 | 273 ms |
| **500** | **20 / 20** | **20 / 20** | **569 ms** |

**Options considered:** 1. Raise or remove the cap
2. Rank by a plain count of shared standards
3. **Rank by an upper bound on the score** (chosen)
4. Precompute a candidate-by-vacancy score table, or use pgvector nearest-neighbour search

**Trade-offs:**

- Option 1: ✅ No new code ❌ Removing it is the 16-second, 32,767-parameter crash; raising it only moves where the page falls over.
- Option 2: ✅ Trivial ❌ Ignores importance and the mandatory cap, so a candidate missing one mandatory standard ranks level with one
  who holds everything. The cap test fails it.
- Option 3: ✅ Comes with a stated guarantee and a test that holds it; uses the scorer's own weights and cap, from configuration
  ❌ A second statement of the cap rule, which is why it is test-guarded; loosest when evidence, level and experience vary, which is
  what the K = 50 row shows.
- Option 4: ✅ Constant-time reads ❌ Stored scores go stale on every profile or vacancy edit, and an approximate nearest-neighbour search
  is the generated ranking ADR-036 forbids deciding a match.

**Consequences:**

- **The default K = 500 misses the employer latency target I set (p95 at or under 300 ms): 569 ms at this size.** K = 150 meets it
  (273 ms) with identical recall on this data. The data is synthetic and its skew steeper than the real corpus will be, so this
  is a measured trade-off for the owner to set, not a conclusion.
- **`JobPool.pool`, `ready` and `nearly` are still counts over what was retrieved** (at most K), as they always were: a vacancy with
  more than K sharers undercounts them. Counting the true pool needs a second aggregate and is not done.
- **The retrieval cost is bounded by K, not by the catalogue**; the cost of the *aggregation* still grows with the number of holders
  of a vacancy's standards (about 50-100 ms at 47,000).
- Turning `match_weight_semantic` up widens the bound's headroom automatically (it is read from the same weights), at some cost in
  recall for the same K. Re-run `make benchmark` with it.
- The harness is a measuring instrument, not a promise: the absolute numbers will differ on real data. The structural findings
  (a cut by `Job.id` or UUID order; a pair-load that cannot run past 32,767 ids) do not depend on the skew.

---

## ADR-057: A District's Skill Gap Is Ranked by Shortfall, and a Count of Fewer Than Five Residents Is Never Shown

**Status:** Accepted (October 2026). Completes BL-12.7. No migration; read-only, operator-only, beside the programme report
(`OPS_PROGRAMME_READ`, so support and admin tiers, ADR-044).

**Context:** A district official's question is "of what employers here want, where is the gap widest". The first version of this
story asked for the "scarce" standards, which needs a threshold nobody has a basis for. It also has a privacy problem the other
operator reports do not: supply is a count of **people in a place**. In a small district "two residents hold this standard" is
nearly a description of them.

**Decision:**

- **Every standard an open vacancy in the district requires is listed, ranked by shortfall.** No threshold decides what appears.
  Demand is the head-count (`Job.positions`) of the district's *open* vacancies (`open_job()`), a standard a vacancy lists twice
  through two rows of one concept counting once. Supply is the number of distinct *residents* (`CandidateProfile.district_id`, where
  they live, not where they said they would work) holding it, compared at concept level as the scorer does. Shortfall is
  `max(0, demand - supply)` and is **per standard**: one resident holds several, so the column does not sum to a number of people.
- **A supply of one to four is not shown** (`MIN_CELL_SIZE = 5`, a constant in `operations/skill_gap.py`, not a setting: a privacy
  floor that an environment variable can lower is not a floor). The row says "fewer than 5". Zero is shown: an absence describes
  nobody. The district's resident total is suppressed the same way.
- **Demand beside a hidden supply would let the reader subtract it back**, so the shortfall for such a row is computed against the
  largest hidden value (4) and flagged `shortfall_is_minimum`. **Rows are ranked on what is shown**, so the order leaks nothing the
  figures do not: a test asserts two standards with equal demand and hidden supplies of 1 and 4 come out in name order, which they
  would not if the true supply decided.
- The panel renders what the server says and computes nothing, so it cannot print a number the API withheld.

**Options considered:** 1. A "scarce" list with a cut-off
2. **Everything demanded, ranked by shortfall, small supplies suppressed** (chosen)
3. Show exact counts to operators, who are trusted
4. Round every count to the nearest five

**Trade-offs:**

- Option 1: ✅ Short list ❌ The threshold is invented, and what falls under it is invisible, which is the gap a district official most wants.
- Option 2: ✅ No invented line; the privacy rule is one function (`suppress`) with one constant ❌ A small district's page is mostly "fewer than 5"
  and minimum shortfalls, which is accurate about how little is known.
- Option 3: ✅ Simplest ❌ An operator's trust is not the data subject's consent, and a screenshot leaves the room.
- Option 4: ✅ Hides small cells too ❌ Rounds the large, useful counts to nothing finer than five.

**Consequences:**

- **`/ops/programmes/{name}/districts` still shows exact per-district enrolment, including cells under five.** That is the Sprint 40 view
  and was not changed here; it is the same class of disclosure and should adopt `suppress` -- recorded, not done.
- Measured on the scale harness (46 districts with demand): 43-52 ms per district. On the 42-candidate dev data the view is a
  demonstration; the harness spreads synthetic rows over 25 districts so it can be exercised at size.
- Residents are counted if they hold *any* declared standard, so the total is "residents with a declared standard", not residents.

---

## ADR-058: Notifications Are Kept for Ninety Days, an Unopened Notice for a Hundred and Eighty, and a Message Still Owed Never Goes

**Status:** Accepted (October 2026). Closes the item ADR-055 recorded as not done. No migration.

**Context:** The outbox is the one table that keeps what the product has *said* to a person, and nothing ever removed a row. An
email delivered in 2026 would sit with its payload (a vacancy title, an organisation's name) for as long as the database does.
Data kept "just in case" is data held without a purpose (DPDP Act 2023); analytics events already have a purge for the same reason.

**Decision:** a worker cron (`purge_expired_notifications`, 03:15 India time, fifteen minutes after the analytics purge) deletes, by
`created_at`, three classes counted separately in the log:

- **delivered** -- email that is `sent`, `skipped` or terminally `failed`, older than `NOTIFICATION_RETENTION_DAYS` (default 90, at least 7);
- **read** -- an in-app notice the person opened, older than the same period;
- **unread** -- an in-app notice nobody opened, after **twice** the period. The list shows the newest fifty regardless of age and an
  unopened notice may be an offer to sponsor a standard (ADR-048) that the person has not yet seen.

A `pending` message is **never** deleted however old: it is still owed, and the drain will send it or fail it.

**Options considered:** 1. Leave it
2. **Three classes, one setting** (chosen)
3. Delete everything past the period regardless of state
4. Archive to a second table

**Trade-offs:**

- Option 1: ✅ No work ❌ Unbounded growth of a table of personal communications.
- Option 2: ✅ Never deletes what is owed or unseen ❌ Two ages from one setting is a rule to remember; it is written beside the code.
- Option 3: ✅ Simplest ❌ Deletes an unseen offer, and could delete a message the drain has not yet sent.
- Option 4: ✅ Reversible ❌ Keeps the data, which is the thing being removed.

**Consequences:**

- The DPDP export (ADR-055) shows what exists, so it shows less after a purge. That is the correct reading of "what the product holds".
- No index serves the in-app delete (`created_at` alone), so it is a nightly sequential scan. Fine at today's size; add one when the table
  is large enough for it to matter.
- Nothing else reads old notifications: the alert and sponsorship daily caps count `job_alerts` and `sponsor_intents`, not this table.

---

## ADR-059: Every Route's Audience Is Stated, and a Test Reads It Back From the Route Table

**Status:** Accepted (October 2026). A test-only change plus one attribute on `require_operator`'s dependency.

**Context:** Every authorization guard here is a dependency a route must remember to declare, and the project's record is that it
sometimes did not: three of eight publishing writes without the tenant-type check, a candidate able to read the employer console.
Each was found by hand, sprints later.

**Decision:** `tests/test_authorization_matrix.py` builds the list of operations from the OpenAPI schema, so a route added tomorrow
is covered the day it exists, and asks four questions of every one:

- **Anonymous.** Every route not named in `PUBLIC_ROUTES` -- each with its reason -- answers 401. A route that forgot its guard answers
  200, 404 or 422 and the failure names it. The list is itself checked: an entry for a route that no longer exists fails, and so does one
  that answers 401.
- **A stranger to an organisation.** For every `/org/{slug}/...` route, a candidate with no organisation and the owner of a *different* one
  each get the same 404 -- status and body -- for an organisation that exists as for one that does not (ADR-038).
- **The back office.** A signed-in non-operator gets a 404 byte-identical to an unrouted path on every `/ops` route (ADR-042); a support
  operator gets 403 exactly where `TIER_PERMISSIONS["support"]` lacks the route's permission (ADR-044). **The permission is read off the
  route** -- `require_operator`'s dependency now carries a `permission` attribute -- rather than restated in a second list.
- **A partner key.** A user's bearer token opens no `/partners` route.

**Consequences:**

- Written against the current code it **found nothing wrong**: two entries in the first draft of `PUBLIC_ROUTES` were corrected by running it
  (`/auth/logout` is public by design, the refresh token being the credential; `/invitations/{token}/accept` requires sign-in), which is the
  intended use of the list. Each check was shown to fail when its guard is removed.
- **It guards the doors, not the rooms.** Whether a permitted caller can reach *another person's* row (one candidate withdrawing somebody
  else's application) needs a real resource per route and stays with each module's own tests. Saying otherwise would be the false claim this
  project has made before.
- **A new public route is a one-line addition with a reason**, which is the intended friction.


## ADR-060: A Count Is Computed Where the Rows Are, a Question About Many People Is Asked Once, and a Sweep Cannot Stall Behind What It Cannot Do

**Status:** Accepted (October 2026). Extends ADR-056's scale work to the rest of the product. Migration 0047 (two indexes, no data change).

**Context:** Sprint 49 measured matching retrieval at 50,042 candidates and 5,148 vacancies and found it returning 2.9 and 1.2 of a true top
twenty. Sprint 50 asked the same of everything else that loops per row, loads an unbounded set or scans -- a read-only audit of the code,
then a measurement of each finding with the same harness (`make seed-scale --skill-less 150 --enrolled 10000 --applicants 5000
--notifications 500000`, then `make benchmark`). Three were not slow but **broken**:

- `programme_report` called `match_jobs` once per enrolled candidate, in one HTTP request, and built `IN (every enrolled id)`.
  Measured: **133 ms a candidate**, so ten thousand enrolled is twenty-two minutes -- against a 15-second statement timeout, the report
  stopped working at about 140 candidates -- and past 32,767 it failed on asyncpg's bind-parameter limit before the time mattered.
- The embedding sweeps picked `LIMIT 100` with no `ORDER BY`. A row with nothing to embed (a profile with no declared standard, which
  `ensure_profile` creates routinely) keeps `embedding IS NULL`, so the same rows were returned first on every tick; once a batch's worth existed,
  **nothing behind them was ever embedded**. Invisible in the harness until it was seeded with skill-less profiles.
- The notification drain walked every accumulated in-app notice to find email rows: in-app rows are never moved off `pending`, and the index
  is `(status, created_at)` with no `channel`.

**Decision:**

- **A question about many people is asked once** (`matching/batch.py`, `profiles_with_serious_match`). "Does this candidate have any serious
  match" needs only the pairs that *can* reach 60, and the retrieval bound says which: `score - 0.5 <= 100 * bound` (ADR-056), so a pair
  scoring 60 has a bound of at least 0.595. The database finds each candidate's pairs at or above that, best first, and **only those** are
  scored, exactly, through `score_match` -- a *selection* of which pairs to score, never a second scorer. The same retrieval limit K applies,
  so the answer is the loop's, pair for pair; `tests/test_matching_batch.py` keeps the loop as the oracle on three random marketplaces.
  `applied` and `hired` are joins on the programme, so no list exists to hit a ceiling.
- **The pair query is pruned by an anchor** (`retrieval._bounded_pairs_anchored`). A pair above the mandatory cap holds *every* mandatory
  standard of its vacancy, so a vacancy need only be probed through its rarest mandatory standard among the candidates in the batch. That
  builds 285 thousand pairs where the full route builds 3.2 million (1,000 candidates against 5,148 vacancies: 0.8 s against 5.2 s), and
  the two routes are held to **identical output** by a test. The join order had to be forced with a `MATERIALIZED` CTE: left alone the planner
  joined first and filtered after, throwing the saving away -- found with `EXPLAIN ANALYZE`, not by reading.
- **A count is computed where the rows are.** `job_pools` scored every sharer of every vacancy and loaded each as a full profile to read three
  integers. `ready` and `nearly` are *defined* by the number of mandatory standards missing, which the retrieval SQL already has, so the
  scorer adds nothing: one aggregate over the same pair facts the bound is built from (`retrieval.pool_counts`). The counts are now **true
  totals** (the pool used to be counted over the K retrieved, a limit ADR-056 recorded). `candidates_total` is an `EXISTS` per profile rather
  than a `count(distinct)` over 890,000 rows.
- **A profile is loaded as columns when nothing reads its collections.** Every `CandidateProfile` load runs seven eager `selectin` queries
  (`marketplace/models.py`); nothing in `matching/`, `alerts/` or the inbox reads them. Those paths use `lazyload("*")`, and `candidate_facts`
  selects its four columns instead of `db.get`.
- **A status change returns the one row that changed.** It re-ran the whole inbox -- load and score every applicant -- so each shortlist click
  cost as much as opening the page (3.5 s at 5,000). A score is a function of one candidate and one vacancy; `score_profiles` is chunked
  as well, since a popular vacancy can draw more than 32,767.
- **A sweep orders by when it last looked** (`embedding_computed_at ASC NULLS FIRST`) and stamps a row it could not embed, so unembeddable rows
  go to the back after one look. The skill ids for a batch are one query, not one per row, and the batch is 250.
- **Two indexes (migration 0047):** `ix_notifications_pending_email`, partial on `(created_at) WHERE status = 'pending' AND channel = 'email'`
  (a drain tick walked 500,000 rows to find 200), and `ix_applications_job_status` on `(job_id, status)`.
- **JIT is off for every connection** (`DB_JIT`, default false). Postgres compiled the programme report's aggregates at about 600 ms a chunk
  and bought nothing; every cheap query is unaffected either way. 37 s became 18 s for ten thousand candidates.
- **The programme-by-district view adopts the small-count rule** (`skill_gap.suppress`, ADR-057): one to four is "fewer than 5", the
  "Unknown" bucket included, and districts are ranked on what is shown. The bars now sum to *at most* the enrolled total, by design, and the
  page says so.
- **The alert sweep takes 30 vacancies a tick, not 10.** Ten every five minutes is 120 an hour, so a catalogue taking more than about 2,900
  new vacancies a day never drained.

**Measured** (same dataset, checksum unchanged; **the machine was under load, load average 6-12, so absolute times are inflated and the
old and new runs were interleaved three times to compare**). Unloaded figures where I have them are marked *q*.

| Path | Before | After |
|---|---|---|
| Programme report, 50 enrolled | 8.5 / 13.6 / 15.9 s (*q* 6.7 s) | 0.24 / 0.31 / 0.24 s (*q* 0.15 s) |
| Programme report, 10,000 enrolled | ~22 min (extrapolated; fails past 32,767) | 17.6 s *q* (37 s with JIT on) |
| Employer overview, 54 vacancies | 36 / 60 / 50 s (*q* 20 s) | 5.9 / 7.9 / 5.6 s (*q* 2.5 s); counts now true totals |
| Employer inbox, 5,000 applicants | 8.0 / 15.8 / 11.0 s (*q* 3.5 s) | 2.7 / 3.3 / 3.1 s |
| `candidates_for_job` p50 | 660 / 990 / 1,340 ms | 364 / 827 / 412 ms |
| Notification drain tick, 500,000 in-app pending | *q* 267-311 ms | *q* 71-120 ms (a partial-index scan) |
| Embedding sweep | 100 a tick, stalls behind unembeddable rows | 250 a tick, cannot stall |

Recall against exhaustive truth is **unchanged at 20 of 20 on both sides** (K = 500), and `make evaluate` is bit-identical.

**Options considered for the programme report:** 1. Cache or precompute it nightly
2. Make `match_jobs` itself cheaper and keep the loop
3. **Ask the batch question once** (chosen)
4. Report an approximation (any pair with a bound over 0.595)

**Trade-offs:**

- Option 1: ✅ Constant-time reads ❌ A stale number on a page an operator reads to see whether a programme is working; and it hides that the loop does not scale.
- Option 2: ✅ No new module ❌ 133 ms is already mostly the SQL and the scoring of 500 vacancies; ten thousand of them is still minutes.
- Option 3: ✅ The same answer, proven by an oracle ❌ A second query shape to keep in step with `bounded_jobs`, which is why the two routes and the loop are tested against each other.
- Option 4: ✅ Fastest ❌ A bound is not a score; reporting it would be the second scorer ADR-036 forbids.

**Consequences:**

- **10,000 enrolled still takes 17.6 s as a request.** No single statement approaches the 15-second statement timeout (each chunk is a few seconds), but the
  operator waits that long. It is a report, not a page load; if programmes reach tens of thousands the next step is a nightly materialised figure, which
  should be a decision, not a default.
- **The employer overview still joins one row per (vacancy, sharer) pair**: 2.5 s unloaded for the heaviest harness employer (54 vacancies, 1.39 million
  sharing pairs). An employer with hundreds of vacancies would pay for it; the page should then show the first fifty.
- `set_status_and_reload` no longer returns a row from a freshly sorted list, so nothing about order is implied by it.
- Not done, and recorded: public `q` search (`_text_filter`) was **not measured** and has no trigram index; the erasure notice loop builds one ORM object per
  applicant; `closes_at` has no index; `corpus_stats` runs eleven counts per homepage hit and is deliberately not cached (a cached count is the "number did not
  move" bug in `CLAUDE.md`).


## ADR-061: A Public Figure About People Names What It Counts, Leads With the Defensible Number, and a Demonstration Says So

**Status:** Accepted (October 2026). Sprint 50.5. No migration; one new field on an existing public endpoint.

**Context:** The homepage band showed what the platform *holds* (standards, qualifications, sectors, vacancies, courses) and nothing about the people and activity on it.
For a sales conversation that is the wrong way round: how many job seekers, how many employers, how many hired is the first question a buyer asks. The owner asked for
those numbers, and chose to **always show the true count, however small**. That choice makes the definitions the whole of the work, because a real figure that is easy to
inflate is the one a buyer catches. Three internal figures already disagreed: `candidates_total` (profiles with a declared standard), `platform_dashboard.candidates` (every
profile row, including the empty ones lazy creation makes), and the homepage's own `states` and `districts` (the geography *master list*, not places with activity).

**Decision:**

- **Six figures, each with its definition written where it is computed** (`marketplace/stats.py`), and where a broad and a narrow figure differ **both are returned and the
  page names the narrow one underneath**, the `jobs_posted` / `jobs_open` pattern:
  - **Job seekers**: a profile with at least one declared standard (`marketplace.skilled_profile()`, now the one definition, shared with the employer console). It leads, because
    a profile row is created lazily on a visit and so is inflatable by browsing; "signed up" (every profile) is the line underneath.
  - **Employers** and **training providers**: `Tenant.tenant_type`, personal workspaces excluded (every candidate owns one); "hiring now" is an open vacancy, "with a published
    course" a published course.
  - **Applications**: every one made, withdrawn included (the candidate did apply).
  - **Hires**: `hired` or `completed`. A `no_show` was hired but left the seat empty, so it is not a hire to count. A person hired twice counts twice, which is why the label
    says "hires", never "people hired".
  - **Districts with an open vacancy**: `count(distinct district_id)` over `open_job()`; the master-list figure is relabelled "states and districts in our location data" so
    the two never read as one claim.
- **A true zero renders `0`, and a small number is shown.** No tile is hidden below a floor, because a tile that vanishes when small reads as a regression on the day it returns.
- **A demonstration says so** (`demo` on the response, a footnote on the band, en/hi/ms). It is true for anything but `ENVIRONMENT=production` **and for any database whose name ends
  `_scale`**, so the benchmark harness's 50,000 synthetic candidates can never read as traction, even under the environment name `production`.
- **One statement, still uncached.** Every count is a scalar subquery in one `SELECT`: nineteen figures in one round trip (17 ms on the dev database, 56 ms at 50,000 profiles).
  Not cached: a cached count is the "I added a job and the number did not move" bug, and a person who has just applied or signed up expects the same. `StatsBand` therefore has no
  `staleTime`, and applying, withdrawing and adding or removing a standard invalidate the public counts.
- **Places, never people in a place.** No figure is sliced by district, so ADR-057's small-cell rule is not engaged, and a national total is an aggregate ADR-037 allows. A
  "districts with a job seeker" figure was deliberately not built.

**Options considered:** 1. Lead with every profile
2. **Lead with the defensible figure and name the broad one underneath** (chosen)
3. Hide a tile until it passes a floor
4. Cache the figures for a minute

**Trade-offs:**

- Option 1: ✅ A bigger number ❌ Inflatable by browsing; the first buyer who asks "what is a job seeker?" ends the conversation.
- Option 2: ✅ Every figure survives the question; the number and its definition arrive together ❌ The headline is smaller than the broad count (22, not 42 on the dev database).
- Option 3: ✅ Looks better early ❌ Different tiles on different days, and a vanishing tile reads as a bug.
- Option 4: ✅ Fewer queries ❌ The exact bug the existing figures were rewritten to avoid.

**Consequences:**

- **The dev database reads as small and says it is a demonstration** (22 job seekers, 102 employers, 60 providers, 18 applications, 1 hire, 21 districts). That is the owner's choice and
  is true; a sales demo wants a database that has real use in it, not a larger synthetic one.
- Employers (102) and providers (60) on the dev database are mostly fixture organisations; "hiring now" (97) and "with a published course" (60) are what a seeded database makes look
  active. The `demo` footnote is what keeps that honest.
- `/marketplace/counts` still duplicates three of `/stats`'s figures and is read only by `LiveCount`; merging them was not worth the churn.
- Malay `stats` strings are still English (the locale is not in the switcher).


## ADR-062: Journeys Run in a Real Browser, Against the Production Build, and a Check That Cannot Fail Does Not Count

**Status:** Accepted (October 2026). Sprint 52. One new dev dependency (`@playwright/test`, pinned exactly); migration 0049 is separate.

**Context:** Nothing in this repository ran a real browser. The component tests mock three seams (`@/lib/auth`, `@/lib/org`, `@/i18n/navigation`), `a11y.test.tsx` runs axe with
`color-contrast` **off** because jsdom has no layout, and the Content-Security-Policy ships report-only, so a violation blocks nothing and is invisible. So a wrong actor branch, a
flush card, a routing defect or a failing contrast ratio compiled and shipped: Sprint 18's ten defects, the homepage panels sitting unpadded for four sprints, and a homepage grid
the owner found misaligned by eye. Sprint 51 then shipped its largest new screen with a hand-run as its only live proof.

**Decision:**

- **Playwright, Chromium only, on the production build.** `next build && next start`, not `next dev`: the CSP is looser in development, the service worker registers only in a
  production build, and `sw.js`'s DENY list is a security boundary nothing else exercises. The API is the real one on its own database, `iism_e2e`, with `ENVIRONMENT=test` (the sign-in code is
  returned and the form prints it). Ports are 8100 and 3100, so the tests never collide with `make api` and `make web`, and the build goes to `.next-e2e` so it never overwrites the
  `.next` a running `next dev` is serving from.
- **Six journeys, each one spec file:** candidate (sign-up, role search, matches with a named gap, apply, withdraw), employer (post, publish, de-identified pool, shortlist), provider
  (publish a course, a learner chooses to be contacted), operator (granted by `scripts/grant_staff.py`, verifies with a reason), Hindi at 360x640 (search above the fold, nothing clipped),
  and bulk upload (check, drafts, confirmed publish, re-upload creates nothing).
- **Every page a journey visits goes through one `checkPage`:** no `console.error`, no uncaught page error, no failed request, no 4xx/5xx from our own origins, **no
  `securitypolicyviolation` event** (an init script listens, because a report-only policy never blocks), and **axe with `color-contrast` ON in both colour schemes**. Transitions are frozen
  before measuring, because axe samples a colour mid-fade and reports a contrast failure that exists for 150 ms and in nobody's eyes.
- **Data: each test makes its own people through the product.** CI has no 21,303-standard corpus, so `scripts/seed_e2e.py` imports `tests/fixtures/nsqf_sample.json` through the real
  `JsonFileNsqfSource` (seven standards, three roles, Karnataka and Assam). It **refuses any database whose name does not end in `_e2e`**: the importer rewrites the standards it owns, and on
  the development database that would replace the real corpus with seven invented rows. A `globalSetup` deletes leftover vacancies and courses each run, because `/matches` shows a top
  twenty and identical vacancies from earlier runs, all tied on score, crowd a fresh one off the page.
- **axe is already a dependency**, so it is injected from `node_modules`; `@axe-core/playwright` is not added. `@playwright/test` is the only new package, it is dev-only, and it
  never reaches a phone.
- **A third CI job, `e2e`, on every pull request. Never nightly:** a build that is red every morning for a reason nobody can fix teaches people to ignore red builds. One retry; a test
  that needs more is rewritten around a web-first assertion or deleted. The report and traces are kept only on failure.
- **Findings are fixed, not allow-listed.** The first run of the contrast check found real defects (below), and the rule is that a finding changes the product.

**Options considered:** 1. More component tests
2. **Playwright against a production build** (chosen)
3. Cypress
4. Playwright against `next dev`
5. A nightly run

**Trade-offs:**

- Option 1: ✅ Fast, no browser ❌ jsdom has no layout, no contrast, no CSP, no service worker: the four things that kept shipping wrong.
- Option 2: ✅ Measures what a user gets ❌ A browser to download (about 575 MB cached) and roughly 17 seconds for six journeys locally.
- Option 3: ✅ Familiar ❌ Larger, slower to start, and its multi-origin handling is the harder fit for a web app on one origin calling an API on another.
- Option 4: ✅ No build step ❌ Tests a CSP and a service-worker story that production does not have.
- Option 5: ✅ Costs nothing per pull request ❌ A red build nobody is looking at, and the change that broke it is a day old.

**Consequences:**

- **It found five real defects in its first sessions**, none visible to any existing test: muted text at 4.33:1 on the hero (below WCAG AA 4.5:1); every signed-out page load asked `/auth/me`
  with no token, took a 401 and logged a console error; skill-code labels dimmed by `opacity-70` to 3.97:1 (light) and 4.17:1 (dark); the homepage figures' sub-lines were `<p>` inside a
  `<dl>`, invalid HTML that axe fails once a secondary figure exists; and Sprint 51's own upload screen did nothing when the same file was chosen twice, which is exactly the
  fix-and-upload-again loop it exists for. Each has a fix and, where jsdom can see it, a unit test.
- **Each check was proved able to fail** by breaking the product on purpose (a `console.error`, an image the CSP disallows, a 2:1 text colour): the console, failed-request, CSP and
  contrast checks each fired. A check that cannot fail is worse than none.
- **Not covered:** padding and spacing (a `Card` with no `CardBody` is the same to every one of these checks), visual regression, other browsers, and real devices. The first is the
  most likely to bite again; a screenshot comparison was considered and rejected as a larger, noisier dependency.
- Ten consecutive full runs (two repeats each) were clean after the two flakes found along the way were fixed: a test asserting before the server had acted, and a database that
  accumulated vacancies across runs.
- A local run needs Chromium (`npx playwright install chromium`) and Docker's Postgres and Redis; `make e2e` does the rest.

## ADR-063: A Spreadsheet Is Many Writes Through the One Writer, Checked Before It Is Applied, Applied as Drafts, and Published as a Separate Act

**Status:** Accepted (October 2026). Sprint 51. Migration 0048. (ADR-062 is held for Sprint 52's browser-test dependency.)

**Context:** A vacancy takes about 35-45 interactions to create: a twelve-field form, then each required standard is a search against 21,303 standards, a pick, an Add and
optional importance and mandatory settings, then a Save (always a draft) and a separate Publish. Thirty vacancies is roughly a thousand interactions. The people the product
is built for are the ones with many: a staffing agency, a multi-centre training partner (Sprint 26 refused to cap organisations per account for exactly them). Government
agencies already had a bulk path; employers and providers had none, and supply loaded by an engineer running a seed script is the thing that stops an owner onboarding a
partner. The owner chose: codes **and** a job-role column together, an upload that creates **drafts** with an explicit publish step, caps that are **higher once Verified**,
and vacancies and courses **in one sprint on one engine**.

**Decision:**

- **A CSV, UTF-8 (a BOM is tolerated), sent as the raw `text/csv` request body.** No multipart, no new dependency (the standard library's `csv`), and no CSV library shipped to
  the client: the browser reads the file with `file.text()` and posts it. XLSX is deferred; Excel exports "CSV UTF-8". The route declares the body in its OpenAPI
  (`openapi_extra`), so the generated client types it as a `string`.
- **Three acts, each its own request** (`marketplace/bulk.py`, `bulk_routes.py`): **check** (a dry run that writes nothing), **apply** (re-validates, never trusting a prior
  check, then creates each valid row as a **draft**) and **publish** (`set_published`'s own rules per slug, so a vacancy with no standard, or a gig with no place, is refused
  exactly as it is one at a time). A bad row never blocks a good one; the response carries a downloadable CSV of the original rows plus an `error` column, so the loop is
  fix and upload again.
- **Bulk goes through `create_job` and `create_course`, never beside them** (ADR-026: one writer). Those commit, so an upload is **per row**, not all-or-nothing, and a crash
  leaves a partial upload that re-uploading skips safely. Both writers validate before they write, so a refusal leaves nothing pending to roll back.
- **Idempotent, because fix-and-re-upload makes it essential.** An optional `external_ref` is unique per organisation (a partial unique index, `external_ref IS NOT NULL`). Without
  one, a row matching an existing listing of the same organisation on normalised title (vacancies: and district and employment type) is **skipped and names the slug it matched**.
  A repeat inside one file points at its first row. Never silently duplicated, never silently updated; update-by-reference is a later story.
- **Standards by code, or by job role, and a role is never guessed.** `Skill.nos_code` is unique across the corpus, so a code is safe in a spreadsheet; a name is not (1,778 names
  are shared by 4,838 standards). `standards` is `CODE[:importance[:M]]` for a vacancy and `CODE[:level]` for a course, `;`-separated. A `job_role` resolves by **exact title or
  active alias only, never fuzzy** (the careers rule: a guess is a claim about somebody else); a near miss is shown as a hint and never applied. It expands to the **compulsory**
  standards of the representative pack at importance 3, and **mandatory defaults to no** (`role_standards_mandatory=yes` opts in), because making every compulsory unit
  mandatory caps every candidate missing one at 45 (ADR-036) and a role's units are rarely all a real employer's must-haves. Explicitly listed standards win over the expansion.
  More than 50 resulting standards is an error (the largest real role has 65, the median is 6); a disability-track-only role is a warning (ADR-050). **The review lists every
  expanded standard by code and name**, so nobody applies a mapping they have not seen.
- **Caps.** 200 rows a file (413 past it, the file refused whole); a 2 MiB body for the two upload paths **and only those** (`body_limit_for`, every other route keeps 256 KB);
  and a rolling 24-hour creation cap per organisation, **100 unverified and 500 verified**, counted from `created_at` over every creation path so a hand-made listing counts, and
  applied identically by check and apply. Drafts are invisible, so the cap bounds clutter and abuse of the write path, not what a visitor can see. A phone number or email in a
  description is a **warning**, not a block (a description is public once published).
- **The route order is part of the design.** `/jobs/bulk/publish` would be captured by `/jobs/{slug}/publish` with `bulk` as the slug, so the bulk router is included **before**
  `publishing_router`; a test asserts it.
- **Two analytics events** (`jobs_bulk_uploaded`, `courses_bulk_uploaded`), counts only: rows, created, skipped, rejected. Recorded after the business commit, as `record()`
  requires.
- **The screen is a route of its own** (`/employer/[org]/jobs/upload`, `.../courses/upload`): `/employer/[org]` has 12 KB of first-load headroom against the budget and a CSV screen
  must not spend it. Download the template (served by the API, so there is one list of columns), choose a file, review (an `aria-live` summary, a per-row table, the standards each
  row resolved to), acknowledge the rows that will be skipped, create drafts, then publish with a confirmation that says the consequence in words. The server's own sentence is
  shown on any failure; a 401 is "signed out", never "your file is wrong".

**Options considered:** 1. A form-per-row grid in the browser
2. **A CSV through a check, apply and publish sequence on the existing writers** (chosen)
3. XLSX first
4. All-or-nothing apply in one transaction
5. Apply through the worker

**Trade-offs:**

- Option 1: ✅ No file format to explain ❌ The same thousand interactions, now in one page; no way to hand over a partner's existing inventory.
- Option 2: ✅ No dependency, one writer, a re-uploadable loop ❌ A person must save as CSV; a crash can leave a partial upload.
- Option 3: ✅ What a non-technical person has open ❌ A dependency that must justify itself (ADR-053) for a format every spreadsheet can already export.
- Option 4: ✅ No partial state ❌ One bad row blocks 199 good ones, and a 200-row transaction holds locks for the whole upload; `create_job` commits by design.
- Option 5: ✅ No request timeout to think about ❌ A 200-row apply takes about 2.5 s in a request, which is the bound; ADR-006 is about work that does not belong in a handler, and this
  does. Revisit above 200 rows.

**Consequences:**

- **Measured on the 50,000-candidate scale database:** a 200-row check is 0.06 s and a 200-row apply 2.4 s for vacancies and 2.6 s for courses.
- The standards step is the hardest for a person to get right. The role column removes it for the common case; the codes remain for those who know them, and a vacancy with no
  standard is a warning at check time and a refusal at publish time, not a silent success.
- **The role expansion decides what many vacancies require.** It is exact-or-alias, shows its working and defaults to non-mandatory; whether that default is right is the thing to
  watch with the first real partner.
- There is still **no verification gate on publishing**, for a hand-made vacancy or a bulk one. This widens nothing, and the unverified cap is what limits it.
- A partner or ATS pushing by API key (a `ServiceAccount`-to-tenant binding and a write scope) and an upload history are later stories, as is update-by-`external_ref`.


## ADR-064: A Published Listing Keeps Its Standards, an Upload Updates Only by Reference and Only the Columns It Carries, and the Browser Sees Every Page

**Status:** Accepted (October 2026). Sprint 53. No migration. Extends ADR-062 and ADR-063.

**Context:** Three loose ends from Sprints 51 and 52. (1) **A rule that was only a check.** "No standard, no publishing" (Sprint 12) was enforced at the instant of publishing, so
`update_job` and `update_course` would still replace a *published* listing's standards with none: it stayed published, stayed on `/jobs`, and could never be matched or recommended. Found while planning,
not reported. (2) **A re-upload could only skip.** ADR-063 made a matching `external_ref` a skip and never an update, which is the safe default and the wrong end state: a staffing agency fixes a salary
in its spreadsheet and has to edit the live vacancy by hand, thirty times. (3) **Sprint 52's six journeys saw about a third of the 42 routes**, and found five defects in them.

**Decision:**

- **Published implies at least one standard, enforced at every write that can break it.** `listings.refuse_emptying_a_published` is called first thing in `update_job` and `update_course`
  (before any field changes): a published listing saved with no standards is a 422 naming the rule and the way out ("add one, or unpublish it first"). A **draft** may still be saved with none
  (unfinished, not live), and unpublishing first remains the way to empty a listing. One shared helper in the shared-policy module, not two copies (ADR-026).
- **An upload may update, only when asked, only by reference.** `bulk/check` and `bulk/apply` take `existing=skip|update` (default `skip`, and a **required argument** inside the engine so there is no
  default to rely on). Only a row whose **`external_ref`** exists may update; a title match is a guess and stays a skip. The update goes through `update_job` / `update_course`, the one writer, so the
  invariant above guards a bulk update exactly as it guards a hand edit, and the check mirrors it so the preview says what the apply will do.
- **The file is the truth only for the columns it carries.** A column the header lacks is never in the row, so that field is left alone; a blank cell in a column the file *does* have clears it
  (the field takes its default, as it would on creation). The update is built by merging the file onto the existing listing, never by treating absent columns as blank, which would have wiped salaries
  and standards from any file that simply had fewer columns.
- **A row that would change nothing is a skip ("unchanged")**, so uploading the same file twice is still a no-op, and a changed row says which columns it changes.
- **Status, slug and the daily cap are untouched.** An update never publishes or unpublishes and never rewrites a published URL; it creates nothing, so it does not consume the daily creation cap
  (it still counts against the 200-row file limit).
- **A live listing changes the moment an update is applied, so the screen asks first.** When the update set includes published rows, the apply button stays disabled until the person acknowledges
  how many are live, in addition to the existing acknowledgement of rows that will be skipped. Toggling the choice re-checks the file already loaded, so an old review never sits beside a button that
  now does something else.
- **Every page is visited, not only the journeys** (`web/e2e/sweep.spec.ts`): ~45 routes in both languages, signed out and as a seeker, employer, provider and operator, with real rows on every list,
  each through the same `checkPage`. A new `checkPage` rule asks of every box with a border on all four sides whether its text starts at least 6px inside it, the gap ADR-062 named (a `Card` with no
  `CardBody` passed every other check).

**Options considered:** 1. Guard the invariant only at publish time (as before)
2. **Guard it at every write that can break it** (chosen)
3. Overwrite the whole listing from the file on update
4. **Merge the file onto the listing, column by column** (chosen)
5. Update on a title match
6. A separate "update" upload type with its own screen

**Trade-offs:**

- Option 1: ✅ No new refusal ❌ A live listing can silently become unmatchable; the rule was a check, not an invariant.
- Option 3: ✅ Simple to explain ❌ A file with fewer columns wipes everything it did not mention; the first partner to upload "just the salaries" would destroy their listings.
- Option 5: ✅ Works without references ❌ A title is not an identity: two "Ward attendant" vacancies in two districts, or a renamed one, would be edited or duplicated by a guess.
- Option 6: ✅ A cleaner mental model ❌ A second screen, a second template and a second review for what is the same file with a different intent.

**Consequences:**

- **The sweep found two defect classes in about 90 page visits**, both fixed at their cause: inline links told apart from their sentence by colour alone (1.54:1 against the text; WCAG 1.4.1 wants an
  underline or 3:1), on all three sign-up pages, sign-in and employer sign-in, in both languages; and two `<select>`s on `/admin` with no accessible name (a placeholder option is not a name). Each has
  a test that fails without the fix (the selects in the unit suite, the links in the sweep). The flush-border check found nothing on the real app and was **proved able to fail**: removing
  `CardBody`'s padding failed all six journeys, naming each box and its text.
- **Eleven rules of the update path were mutation-checked** (a title match updating, absent columns overwritten, blank cells not clearing, unchanged rows applied, updates consuming the cap, another
  organisation's references visible, the live guard not mirrored, the route default flipping, and the UI's live acknowledgement, query parameter and re-check on toggle), and one survivor, the
  engine's own default, was removed by making the argument required.
- **Measured on the 50,000-candidate scale database:** a 200-row update check takes 0.13 s, applying 200 updates 5.9 s, and re-uploading an unchanged file 0.06 s and writes nothing. Creation measured
  6.5 s the same session against 2.4 s in Sprint 51, because the machine was busy with the browser runs; treat both as upper bounds. ADR-063's "revisit above 200 rows" stands.
- **`update_job`'s other quiet behaviour is unchanged and now visible:** it replaces a listing's standards wholesale, so an update that carries a `standards` column replaces them; one that does not leaves
  them. The review lists the changed column names ("standards" among them) so nobody applies that unseen.
- **Dependency triage, recorded because it was done and not merged:** the newest `python` group (fastapi 0.142.2, pymongo 4.18.2, ruff 0.16.10, mypy 2.4.0) passes ruff, mypy and the full suite; the newest
  `web` group (`@radix-ui/react-dialog` 1.2.0, `axe-core` 4.14.0, `jsdom` 30.1.2, `react-progress` 1.1.17) passes `tsc`, lint, the unit suite, the build and every browser test, **but takes `/profile` to
  680 KB of the 684 KB budget**. The older duplicate groups and `@types/node` 26 (held by ADR-053) are the ones to close.
- **Not covered by the browser checks:** visual regression, other browsers, real devices, and padding that is present but wrong (the flush check catches none, not too little).


## ADR-065: The Footer Waits for the Page, a Page Must Not Jump While It Loads, and the Content Security Policy Is Enforced

**Status:** Accepted (October 2026). Sprint 54. No migration, no new dependency. Extends ADR-062; supersedes the "ships report-only" decision of Sprint 20.

**Context:** Two things the browser harness (ADR-062) made measurable and nothing had measured. (1) **Pages jump while they load.** Measured on a 360x640 phone profile (Slow 4G, 4x slower CPU) against a
production build, speed was fine (first and largest paint about 0.7 s on a vacancy, the jobs list and sign-in, 340 to 350 KB over the wire), but `/jobs` scored a layout shift of **0.205** and `/skills`
**0.167**, where Core Web Vitals call 0.1 good and 0.25 poor. The one element that moved was the footer: while a list is a placeholder the page is short, so the footer sits mid-screen, and when the list
lands it is pushed off the bottom. The signed-in screens were worse (up to **0.645**), because several returned `null` while loading, which leaves a blank page with a footer on it. (2) **The CSP blocked
nothing.** It shipped report-only in Sprint 20 "until a production build runs clean", and Sprints 52 and 53 then ran every page in both languages with a `securitypolicyviolation` listener and found none, so
the condition for enforcing it had been met for two sprints with no one assigned to notice.

**Decision:**

- **The footer is hidden, not removed, while anything on the page is still a placeholder.** `body:has([data-loading]) footer { visibility: hidden }` in `globals.css`. Every `Skeleton` carries
  `data-loading`; a placeholder that is not a `Skeleton` must carry the attribute itself. `visibility`, not `display`, so the footer keeps its box and appearing moves nothing, and a hidden element is
  not counted as having shifted. This is one rule for every page, present and future, rather than a height tuned per list. Where `:has()` is unsupported the footer is simply visible, as before.
- **Nothing renders `null` while it loads.** `SeekerOnly`, `ProfileEditor` and `DeleteOrganisation` returned nothing until their data arrived; they now return a `Skeleton`. A line of text that arrives
  late and is a different length (the consent line on `/account`) is reserved the same way, and a count is never shown as "No jobs" for the moment before the list arrives. A placeholder is as tall as
  what replaces it (`CandidateDashboard` was 64 px standing in for a ~400 px card, which dropped the whole match list below it; the homepage `StatsBand` holds the room for the line some of its tiles grow
  once the figures arrive, which the existing Hindi phone journey caught at 0.111; the employer and provider dashboards had the same 64 px placeholder, which **CI** caught at 0.158 on a slower runner when three local runs had passed).
- **The browser harness fails a page that jumps.** `checkPage` now reads the worst layout-shift *session window* (the way Chrome scores it, ignoring shifts within 500 ms of the person's own input) and
  fails above **0.1**, naming the elements that moved. To make that deterministic rather than a property of how fast the developer's laptop is, the harness holds every API **read** back 250 ms (writes are
  not delayed) and waits for the network to go idle before it looks. The sweep also runs the public pages and the signed-in pages **on a 360x640 phone**: on a 1280x720 desktop most pages are taller than
  the screen, the footer is never in view while a list loads, and nothing can jump, so the desktop pass could never have found this.
- **The Content Security Policy is enforced in a production build** (`Content-Security-Policy`), and stays report-only under `next dev`, where hot reload and React's overlay reach for eval and
  websockets that a production page never does. The policy itself is unchanged (including `'unsafe-inline'` for scripts, which is still the honest state: ADR-062 and Sprint 20 explain why). The guard is the
  sweep: a page that needs something the policy forbids now fails the suite. Two assertions, because a header can be present and a policy still wrong: the response carries the enforcing header and no
  report-only twin, and an injected `<script src="https://...">` is **blocked** (`script-src-elem ... (enforce)`).

**Options considered:**

1. Give each list a skeleton tuned to its expected height
2. **One rule that hides the footer until the page has settled** (chosen), plus real placeholders where a screen was blank
3. `min-height: 100vh` on `<main>` so the footer is always below the fold
4. Server-render every list so there is no loading state
5. Leave the CSP report-only until `'unsafe-inline'` can be removed
6. **Enforce it now with the policy as it stands** (chosen)

**Trade-offs:**

- Option 1: ✅ Each page is exact ❌ A height guessed per list is wrong the moment the content changes, and the next list shipped without one jumps again.
- Option 3: ✅ Trivial ❌ A short page (sign-in, a 404) would have a footer a full screen below its content.
- Option 4: ✅ No loading state, and faster ❌ Not possible for the signed-in screens, and a large change to how every list is fetched; it remains an option for the public lists.
- Option 5: ✅ Strictest end state ❌ Leaves a measured-clean policy doing nothing for an unbounded time; `frame-ancestors`, `object-src`, `base-uri`, `form-action` and the foreign-script restriction on
  `script-src-elem` all work today.

**Consequences:**

- **Before and after, on the same harness:** the first run of the check failed 18 of 88 pages (the signed-in workspaces, matches, account, admin, and the employer team and candidates pages). It
  passed `/jobs`, `/courses` and `/skills` that run, **which was wrong**: the check looked before the list had arrived. Once it waited for the network to go idle (and reads were delayed, and the phone
  viewport added) those six, in both languages, failed too, matching the hand measurement. After the rule and the placeholders, **all 119 browser tests pass**. Both ends were **proved able to fail**: removing the rule failed 21 tests (50 shift reports), restoring the report-only header failed the CSP test, and removing `data-loading` or changing the
  rule's `visibility` fails the unit tests.
- **The first two measurement runs tested stale code**: a production server left running on port 3100 from an earlier measurement was reused by Playwright (`reuseExistingServer`), and a rebuild under it
  served 500s for every changed chunk. CLAUDE.md already says to kill `next start -p 3100` after a rebuild; the process name is `next-server`, so `pkill -f "next start"` matches nothing. Kill by
  **port** (`lsof -nP -iTCP:3100 -sTCP:LISTEN -t`).
- **A running `next dev` can break `next build`'s type-check**: `tsconfig.json` includes both `.next/dev/types` and `.next-e2e/types`, and a dev server that has not yet compiled any page leaves a stub
  `routes.d.ts` that conflicts with the real one (`Route` collapses to `never`). Stop the dev server, or move `.next/dev/types` aside, before a browser build.
- **Not done, and why:** search-engine optimisation (per-page metadata, structured `JobPosting` data, a sitemap and `robots.txt`), a share control, deployment and monetisation were scoped out by the
  owner for later. The measured finding that motivates the first of them stands: every vacancy, course and standard page carries the same title and description.


## ADR-066: A Code May Be Asked For Again After a Wait, a Credential Is Changed by Proving the New One, and Changing It Ends the Other Sessions

**Status:** Accepted (October 2026). Sprint 56. No migration. Extends ADR-009, ADR-032 and ADR-038.

**Context:** A one-time code is the only way into an account (no password anywhere), so the phone number or email it goes to **is** the account, and a code that does not arrive is a lost user. Reading the code for the sprint's plan found more than the roadmap assumed. (1) **No cooldown.** `enforce_otp_rate_limit` was a budget (5 per identifier per 15 minutes); nothing separated two requests, and the sign-up form had no way to ask again at all (sign-in had a resend button with no countdown). (2) **A silent overwrite.** `POST /me/credentials/{phone,email}/verify` replaced a credential already held in that channel: no notice to the old address, no session ended, so a stolen session could swap the number or address and keep the account. (3) **No removal**, and a link screen that could only add the credential that was missing. (4) **A trap in the obvious resend:** for an organisation, asking again through `/auth/org/register` re-queues a pending organisation of the same name, and the duplicate-name refusal then fails the person at verification.

**Decision:**

- **One cooldown, in the one place every code request passes.** `enforce_otp_rate_limit` does `SET NX EX` first: a second request for the same identifier inside `otp_resend_cooldown_seconds` (default 30) is a 429 with `Retry-After` and a sentence saying how long. It is checked before, and does not spend, the 15-minute budget. It is per identifier whether or not an account exists, as the budget already was, so it is not an enumeration oracle. The response carries `resend_after_seconds` so the forms count down without guessing; the countdown is a deadline, not a tick counter, because a background tab throttles its timers.
- **An organisation asks again for a sign-in code, never registers again** (`/auth/email/otp/request`, the same key and the same verify).
- **Add is add-only.** `confirm_link` refuses (409, "replace it instead") when the channel already holds a different value, before the code is spent. The same value is an idempotent re-verify.
- **Replace proves the new identifier, not the old one.** The usual reason to replace is that the old one is lost. In its place: a live session, a code sent to the new identifier, the other credential being told, and **every other session ending**. `POST /me/credentials/{phone,email}/replace` and `DELETE /me/credentials/{phone,email}` revoke all refresh tokens and return a **fresh pair**, so the person who changed their number is not signed out of the screen they changed it on (the interface must store it: a component test fails if it does not).
- **Remove only while another verified way in remains.** "Verified" matters: an address typed in and never proved is not a way back. The user row is locked (`SELECT ... FOR UPDATE`) before the check, because the check is followed by a write and removing the phone and the email at the same moment would otherwise pass it twice and leave an account nobody can open; `ck_users_has_identifier` would turn the loser into a 500.
- **The notice is inline, best effort, and email only.** An outbox row names a recipient and resolves the address at send time (ADR-006, ADR-023), which after a replacement is the *new* address; this notice must reach the one taken away, so the address is captured before the change. A failure is logged and never undoes the change. No SMS: it needs a DLT-registered template and costs money. A phone-only person has nobody to tell, which is why the account and profile pages ask them to add an email.
- **The screen** (`CredentialsSection`, on the profile and on `/account` so an organisation-only account has it too): add, change (a code to the new one, then confirm), remove (asked twice), a countdown on every resend, and the new tokens stored after a change. It is loaded lazily on the profile, which sits a few kilobytes under the first-load ceiling.

**Options considered:**

1. A longer budget only (no cooldown)
2. **A cooldown shared by every code request** (chosen)
3. Send the notice through the notification outbox
4. **Send it inline to an address captured before the change** (chosen)
5. Require a code to the old identifier to replace it
6. **Require a code to the new one, end other sessions, tell the other credential** (chosen)
7. Return only the user from replace/remove and make the person sign in again
8. **Return a fresh token pair** (chosen)

**Trade-offs:**

- Option 3: ✅ Retries, locale, no inline latency ❌ Cannot address the credential that was removed, and would need a hand-written template CHECK.
- Option 5: ✅ Strongest ❌ Defeats the purpose: the person who lost the number cannot answer it.
- Option 7: ✅ Simplest ❌ A person who changes a number is signed out by doing so, on the page they did it on.

**Consequences:**

- **Recycled phone numbers are a risk this does not close.** A number reassigned by the carrier lets its new holder ask for a code and sign in to the old account, and "prove the new one" cannot see that. The mitigation is the backup email and, later, an operator-assisted identity policy for an account that has lost every credential (a policy question, not code; not built).
- **Phone codes reach a real phone only once SMS is registered (DLT).** Until then recovery works through email, and the console provider is the only phone path in development.
- **Access tokens of other sessions live until they expire (15 minutes)**; only refresh is revoked. Stated, not hidden: ending an access token early would need a revocation list on every request.
- **Measured by tests that fail without the rule:** no revocation (two session tests), add overwriting again, no "another way in" check (two tests), the notice going to the wrong address, the missing row lock (the committed-row race test fails with an `IntegrityError`), a component test for each interface branch including "forgets the new tokens", and the organisation resend asking to register again.
- **Not done:** an analytics event for credential changes (a hand-written CHECK migration; the lockout rate is not yet worth one), a notice by SMS, and proof of the old identifier.

## ADR-067: A Grievance Is a Row With a Deadline, We Never Write to an Address a Stranger Typed, and a Public Form Carries Its Own Limits

**Status:** Accepted (October 2026). Sprint 57 (BL-14.3). Migration 0050. Extends ADR-023, ADR-042 and ADR-044.

**Context:** `/grievance` told people "we acknowledge a grievance within 24 hours and aim to resolve it within 15 days" and to write to a grievance officer. There was no form, no table, no queue and no officer (`GRIEVANCE_OFFICER` still reads "to be appointed"); `/contact` was a placeholder. A promise with nothing behind it is worse than none, and the DPDP Act 2023 expects a working grievance route before real users. The forms are the engineering half; **appointing the officer is the owner's** and no code can do it.

**Decision:**

- **A new leaf module, `api/modules/grievances/`** (one table, `grievances`). `kind` is `contact`, `grievance` or `data_request`; `status` is `open`, `acknowledged`, `resolved` or `dismissed`; a reference (`GRV-` and six unambiguous characters, unique, drawn again inside a savepoint on a collision) is what the sender keeps. CHECKs hold the rules the service holds: a body of 10 to 4,000 characters, somebody to reach (`user_id` or `reply_to`), a data request belongs to an account, and a closed row has a `resolved_at`.
- **Who may send what.** A stranger may send a `contact` message or a `grievance`, and must leave an email address or a mobile number to be answered at. A **`data_request` (see, correct, erase, nominate) needs an account**, because the account is the proof of who is asking; a stranger asking to see or erase somebody's data is exactly the attack this stops. It is a 401 that says to sign in, not a 422.
- **No relay.** An anonymous form that emails whatever address it is handed is a way to harass a stranger. The address a stranger typed is shown to the operator and **never written to by us**; the operator replies out of band from the grievance officer's own mailbox. A signed-in sender is acknowledged at the verified email their account already holds (inline, best effort, as ADR-066), sees where the message stands on the grievance page, and gets an **in-app** notice on each change (`grievance_update`, a template added by hand to the notification CHECK; the payload is the reference and the status and **never the operator's note**, which is evidence and may name other people). A signed-in sender's own `reply_to` is not stored: they are answered through the account.
- **A public endpoint that writes a row carries its own limits.** `core.security.enforce_budget` (the OTP counters, generalised) gives 5 messages an hour **per client address** and **per account or reply address**, so one person is stopped without throttling their neighbours behind carrier-grade NAT, and one person changing address does not escape their own budget. `client_ip` (extracted from the request limiter) is the one rule for the address: `X-Forwarded-For` only when we trust a proxy, rightmost entry only. A hidden `website` field is a honeypot: a bot is answered with a success and a reference that exists nowhere, and nothing is stored. The global write limiter still applies; a CAPTCHA is out of scope (it needs a vendor).
- **The promise is measured.** The operator queue shows **overdue** against the page's own numbers, which are two settings (`grievance_acknowledge_hours`, `grievance_resolve_days`) read at the moment of the query, so the page and the code cannot drift. A contact message promises nothing and is never overdue; a closed one is no longer late.
- **Operators.** Two permissions, `OPS_GRIEVANCE_READ` and `OPS_GRIEVANCE_HANDLE`, in the **support and admin** tiers: a grievance is a single-subject decision with no public blast radius, like a certification check. `GET /ops/grievances` is ordered by what is owed (not yet acknowledged first, then acknowledged, then closed, the longest-waiting first), with true counts from SQL. A sender's **account is masked** (`mask_phone`, `mask_email`); the message and the reply address are not, because an operator cannot answer a person without them. A decision takes the row lock (`FOR UPDATE`), is final once closed, and closing an open message acknowledges it. Resolving or dismissing needs a note of at least 10 characters, like a verification decision. **The queue's default view is everything, not "waiting"**: found by the browser journey, an acknowledged message is still owed a resolution, and a default of "waiting" dropped it from sight the moment the first button was pressed.
- **Retention, export and erasure.** A closed grievance is deleted `grievance_retention_days` (365) after it was closed, by a daily worker cron; **an open one is never deleted, however old**. Erasing an account deletes its grievances explicitly; the DPDP export lists them (`grievances_raised`), **without the operator's note**. The log line carries the reference and the kind and never the body, a phone or an address.

**Options considered:**

1. Email the grievance to the officer's inbox (no table)
2. **A row, a queue and a deadline** (chosen)
3. Acknowledge every sender by email at the address they typed
4. **Acknowledge only the signed-in sender, at the address their account already holds** (chosen)
5. A CAPTCHA on the form
6. **A budget, a honeypot and a length cap** (chosen)
7. A separate table or tier for grievances
8. **Two permissions in the existing tiers** (chosen)

**Trade-offs:**

- Option 1: ✅ No new surface ❌ No deadline anyone can measure, no history, nothing to export or erase, and the page's promise stays unfalsifiable.
- Option 3: ✅ A stranger gets a receipt ❌ An open relay that writes to anyone: the form becomes a harassment tool. The reference on screen is the receipt.
- Option 5: ✅ Stops more bots ❌ A vendor, a script on the page and a CSP change, for a form behind a budget that already makes a flood harmless.

**Consequences:**

- **A signed-out sender cannot be answered through the product.** By design: the operator replies from a mailbox the owner must provide, and the sender is told on screen that nothing is sent automatically.
- **The officer is still to be appointed**, and a lawyer has not read the page. The queue makes the deadlines visible; people meet them.
- **The budget is per address and per sender, advisory by design** (a cap that deters abuse may stay advisory, ADR-051): Redis is the counter, and an outage fails open.
- **Measured by tests that fail without the rule:** a stranger's data request, a stranger with nowhere to reply, the honeypot storing, each of the two budgets (separately: the first version of the test could not tell them apart), the retention age, a contact message counted overdue, an acknowledged one counted late to acknowledge, the operator's note reaching the sender's notice, and the queue default hiding an acknowledged message. One mutant is equivalent and documented: the purge of an open row (the CHECK keeps `resolved_at` null there).
- **Not done:** the dashboard's open and overdue counts, an SMS notice (waits on DLT), threading a reply into the product, a per-sender view of an operator's reply, and a reply template. Appointing the officer and a reply mailbox are the owner's.

## ADR-068: A Recommendation Says Whether You Can Act on It: a Course Has a Place, an Intake and Seats, and Attendability Orders Suggestions Without Touching the Score

**Status:** Accepted (October 2026). Sprint 58 (BL-14.5, BL-14.6). Migration 0051. Extends ADR-036, ADR-037 and ADR-047.

**Context:** The product's pitch is "here is your gap, and the courses that close it". `courses_closing_gap` ranked by how much of the gap a course closes and then by title. A `Course` had a mode, language, fee and duration and **no place, no start date and no seat count**, so an offline course in another state was recommended exactly like one next door, a course that began last month like one that begins on Monday, and a full one like an empty one. Four screens each hand-rolled the same list item and none showed fee, place or start.

**Decision:**

- **Six nullable columns on `courses`**: `location_state`, `location_district` (free text), `state_id`, `district_id` (`SET NULL` foreign keys, resolved on write with the one `geography.resolve_location`, **before anything changes**, the Sprint 55 refuse-first rule), `starts_on` (a calendar date; null is a rolling or unstated intake) and `seats` (CHECK `>= 1`). Nothing is backfilled: a course published before this has no stated place, and a guess would be a factual claim the data does not support. A place is never required to save or publish, so an online course needs none; an offline course with none gets a hint in the editor and a warning in bulk upload.
- **Seats left is derived, never stored.** `seats - count(enrolled interests)`, floored at zero (`interests.enrolled_counts`, chunked by 5,000 for the bind-parameter limit). A counter would drift the first time somebody is un-enrolled, withdraws or erases their account; the derived figure cannot. It is only as true as the provider's own "enrolled" marks (ADR-047), so the screens say "seats left", never a guarantee. `started` is derived from `starts_on` and the date in India (`core/clock.today_ist`), never stored.
- **Attendability is its own pure module, `matching/attendance.py`**, like `scoring.py`: no I/O, no clock, no settings. It reads `candidate_facts` (the one reader of a person's locations), classifies a course as `online`, `district`, `state`, `unknown` or `elsewhere`, and says whether it has started, is full, or is within a budget. **It is not part of the score** (ADR-037): no match percentage changes; it orders and labels suggestions that were already chosen by what they teach.
- **The order**: a course that closes a mandatory standard first (never outranked by a nearer one that closes none), then one the person can attend, then the nearer, then by how much of the gap it closes. **Nothing is hidden**: a started, full, faraway or over-budget course stays in the list, labelled, because it may be the only one teaching the standard and intakes are often rolling. **An unknown place is neutral** (between "your state" and "elsewhere"), and a person with no location on file gets no reordering from place at all: no evidence must not read as "far away".
- **Only candidate-facing callers pass the context** (`match_detail`, `careers`, "why not me"). `courses_closing_gap(..., attend=None)` is the old order exactly, which the employer-facing sponsorship callers rely on: they know no candidate. Every suggestion carries its attendance either way, so every screen can say where, when and how many places. `CourseSuggestionOut.from_suggestion` stays the one construction site.
- **The budget is a per-request query parameter** (`budget_inr`, `0..10,000,000`), remembered in the browser only. A profile column would be personal data needing export and erasure treatment (ADR-055), and a number typed once to see another ordering is not a fact about the person.
- **One shared `SuggestedCourses` list** replaces the four hand-rolled ones. Interest in a full or started course is **not refused**: an interest is a request for contact, not an enrolment (ADR-047).
- **Bulk upload** gains `state`, `district`, `starts_on`, `seats` through the same planning and `update_course` path, so the refuse-first rule and the "published keeps a standard" invariant apply; a new state clears the old district for courses as for vacancies.

**Options considered:**

1. A stored `seats_left` counter
2. **Seats left derived from enrolled interests** (chosen)
3. Hide courses the person cannot attend
4. **Rank them last and label them** (chosen)
5. Fold distance and fee into the match score
6. **Keep the score untouched; order suggestions separately** (chosen)
7. Store the budget on the profile
8. **Pass it per request** (chosen)

**Trade-offs:**

- Option 1: ✅ One read ❌ Wrong after the first un-enrolment or erasure, with nothing to reconcile it against.
- Option 3: ✅ A shorter list ❌ A person with one faraway option is told there is none, and a rolling intake is hidden because its date has passed.
- Option 5: ✅ One number ❌ Breaks ADR-037's rule that a score is defensible to an employer and reproducible against the golden set, and ranks employers' candidate lists by proximity.

**Consequences:**

- **Start dates go stale.** `starts_on` is the provider's to update; the badge says "started", not "closed", and an online course with an old date still shows, labelled.
- **Seeded courses now carry places** (relative start dates, so the demo never ages; two are made full by a seeded enrolled learner), and the offline-without-place **warning in bulk upload changes five existing expectations from `ok` to `warning`**, which is the intended pressure on providers.
- **Measured by tests that fail without the rule:** each reach, started (today is not started), full, the budget edges and a null fee, the order including "a mandatory closer is never outranked", no-context equals the old order (a started course is not demoted), the derived seat count (only `enrolled`, never negative, a seat returns on withdrawal), the refuse-first update, and a golden set whose attendability labels are derived from the seed's own tables and checked independently in CI and by `make evaluate` (25 course expectations hold; breaking the attendable tier fails it).
- **Not done:** a place filter on course browse, travel time or a distance measure (district and state only), a waiting list, and language preference in the ranking.

## ADR-069: A Takedown Is a Draft With a Stamp, Not a Third Status; Reports Are Grouped by Listing and Decided by a Human, Never by a Count

**Status:** Accepted (October 2026). Sprint 59 (BL-14.4). Migration 0052. Extends ADR-042, ADR-044 and ADR-067.

**Context:** Fake vacancies are the main trust risk of a jobs marketplace, and the only moderation lever was the owner unpublishing their own listing. A candidate who met a vacancy asking for a deposit, or a course that did not exist, could not say so, and an operator could not act. The code showed three things that shape the answer. `status == "published"` is compared in about thirty-four places (browse, matching retrieval, counts, alerts), so a new status would have to be added to each and would stay visible wherever one was missed. Only two functions put a listing live (`publishing.set_published` and `course_publishing.set_published`; `bulk.publish_many` goes through them) and one brings a closed vacancy back (`reopen_job`). And closing a vacancy already tells the applicants still waiting.

**Decision:**

- **A takedown is `status="draft"` plus `taken_down_at` and `takedown_reason`** (set together, a CHECK on each table), not a third status. A draft is excluded by every public query for free. A vacancy is also **closed** with the new reason `taken_down` (the one close reason an owner cannot claim, as `expired` is the worker's), so it stops counting as open and its live applicants are told through the notice a closed vacancy already sends.
- **Every writer of "published" refuses while stamped** (409, with the reason and how to appeal): both `set_published` functions, which covers bulk publishing, and `reopen_job`. Editing stays allowed: the owner fixes what was wrong. **A restore clears the stamp and the takedown's own closure (a vacancy the employer had already filled stays filled) and leaves a draft**: nothing goes live by an operator's hand, the owner publishes again themselves. The write lives in `marketplace/takedown.py`, because whether a listing may go live is an invariant of the listing; `moderation/` only decides that one should come down.
- **A report is its own row** (`listing_reports`): once per person per listing (a unique constraint arbitrates), a reason from a fixed list plus up to 1,000 characters, `target_id` with **no foreign key** (a report about a deleted listing is still a fact; the retention purge removes the orphans with one `NOT EXISTS`, so no writer of a deleted listing had to learn about reports), and `reporter_id` with `CASCADE` (it is the reporter's own words, so erasing the account erases it, and the DPDP export lists it). A signed-in person only; a published listing only (a draft is a 404, so its existence is not confirmed); **not about their own organisation** (409); a per-person daily budget.
- **An operator decides about a listing, not a report.** The queue groups reports by listing, most distinct reporters first and then the oldest, with the reporter **masked** and the organisation named. Dismissing closes every open report on the listing; a takedown closes them as actioned **in the same transaction** as the removal, so a refusal leaves them open. **Nothing is taken down by a count, ever**: a rival organisation can file reports, and a human reads them.
- **Tiers (ADR-044).** Reading and dismissing are `support`'s; **taking down and restoring are `admin`'s alone** (`OPS_LISTING_TAKEDOWN`): removing somebody's business from the public has the blast radius `OPS_ORG_VERIFY` has for a badge. A support operator is not offered the control rather than offered and refused.
- **Who is told what.** The organisation is **emailed the operator's reason** (the form says so: it is the one free-text field in the back office that leaves the building) through the outbox, addressed to the tenant; the live applicants get the existing closed notice; **nobody is told who reported**, not the organisation, not an event, not the applicant. The reporter is told only that the report arrived.
- **Events** (`listing_reported`, `listing_reports_dismissed`, `listing_taken_down`, `listing_restored`) subject the listing and carry a reason code or a count, never the reporter or free text, recorded after the commit in the service. Three closed sets were widened by hand in migration 0052 with frozen lists (close reasons, event names, notification templates), since Alembic does not diff CHECK bodies.

**Options considered:**

1. A third `taken_down` status
2. **Draft plus a stamp** (chosen)
3. Take a listing down automatically at N reports
4. **A human decides, whatever the count** (chosen)
5. One queue row per report
6. **One row per listing with its reports nested** (chosen)
7. A foreign key from a report to its listing
8. **No foreign key and a purge that finds the orphans** (chosen)

**Trade-offs:**

- Option 1: ✅ Explicit ❌ Every one of ~34 `status == "published"` sites would need the new value, and a closed-by-operator listing would stay visible wherever one was missed.
- Option 3: ✅ Fast ❌ A brigade of N accounts removes a competitor's vacancies, and every count is a number somebody will aim for.
- Option 7: ✅ Referential integrity ❌ A cascade deletes the evidence when the owner deletes the listing, and `SET NULL` leaves rows that point at nothing; a purge is simpler and a deleted listing is the owner's right.

**Consequences:**

- **A taken-down vacancy 404s publicly**, like any draft. An applicant's bookmark would dead-end, so the application list shows "Removed by our team" and does not link to it.
- **A mistaken takedown harms a real business.** Admin-only, a mandatory reason, a restore, events and a banner telling the owner what happened; there is no appeals queue, only the contact page.
- **A reporter is not told the outcome**, and learners who registered interest in a removed course are not told (only a vacancy's applicants are). Both would need a notice design of their own.
- **Measured by tests that fail without the rule:** each of the three publish writers (job, course and `reopen_job`), the closure with its own reason, a restore that keeps a filled vacancy filled, a draft staying a draft after restore, self-report, a draft being reportable, support able to take down, dismissal needing the wrong tier, the retention age, an open report being purged, the queue order and an unmasked reporter; in the browser, a support operator is not offered the removal, the applicant's list says so, the owner cannot publish and an admin's restore lets them.
- **Not done:** an appeals queue, a reporter-facing outcome, notifying learners, language in a takedown notice beyond English and Hindi, and acting on a listing from its public page.

## ADR-070: A Message With a Status Is Read From the Application and Never Copied Into the Outbox; Notes Are the Employer's and in the Person's Export; One Serialiser Feeds the List and the Spreadsheet

**Status:** Accepted (October 2026). Sprint 60 (BL-14.7 to BL-14.9). Migration 0053. Extends ADR-006, ADR-023, ADR-037 and ADR-055.

**Context:** An employer could move an application to shortlisted, rejected or hired but could not say when or where an interview was; the candidate's notice said only the new status. There was nowhere to keep a note on an applicant and no way to take the list into a spreadsheet. A candidate's notices existed only inside the applications page, capped at the newest fifty with no unread count anywhere. Reading the code: `Application.message` is the *candidate's* covering note (withdrawing takes it back), so the employer's words need a different column; `employer_service.set_status` is the one writer of a status; the rule that contact and the covering note vanish on withdrawal lived in a pure function sitting inside a route module; the outbox holds a recipient and a payload and, by ADR-006/023, no address or phone; and `bulk.errors_csv` wrote cells exactly as uploaded.

**Decision:**

- **The message is stored on the application and never in the outbox.** `status_message` (500 characters, a CHECK as well as the schema) is **replaced when one is given, cleared when the status really changes and none is given, and left alone when the status is unchanged and none is given** (a second click on "Shortlist" must not erase an interview time). The notice carries `has_message: true` and the path; the words are read from the application page, where the candidate already is, and the email says only that there is one. An interview contact will often contain a phone number, and the outbox keeps free text for 90 days and mails it in clear; not copying the words keeps the rule without trying to detect phone numbers. A message uses its own template (`application_status_message`) rather than a conditional in the old one.
- **One latest message, not a thread.** A thread is a messaging product with moderation, notifications and abuse of its own; one message per application covers "when and where".
- **Employer notes are the employer's, private in the product, and in the person's data export.** `employer_notes` (2,000 characters) is never in any candidate-facing schema (a test walks every response model reachable from `/me/*` for the field), survives the candidate's withdrawal (withdrawing takes back what they shared, not what the employer wrote) and is deleted with the application on erasure. It **is** listed in the DPDP export: it is personal data about the person processed here, and a summary of what is held is the right of access (ADR-055's rule that what erasure deletes the export shows). The note field tells the employer so.
- **One serialiser.** `applicant_out` moved out of the route module into `applications/serialisers.py`; the CSV is built from the `ApplicantOut` objects it makes, never from the rows beside them, so a withdrawn applicant's name, phone, email and covering note are blank in the spreadsheet for the same reason they are blank on screen. The export is `CANDIDATE_SHORTLIST`-gated like the list, the employer's own vacancy only, as heavy as opening the list (it goes through `inbox()`), and recorded as `applicants_exported` with a count and no name.
- **Every cell is safe to open** (`core.text.csv_safe`): a cell that starts with `=` or `@`, a tab or a carriage return, or `+`/`-` followed by anything that is not a plain number, is prefixed with a single quote; a plain number keeps its sign (`+919876543210` is a constant, and prefixing it would break the phone column). It is applied to **`bulk.errors_csv` as well**, whose cells come from an uploaded file and had the same hole.
- **Notifications page.** `GET /me/notifications` takes `limit` (default 50, max 100) and a cursor of **`before` and `before_id` together**, because `created_at` is the transaction's time and an alert sweep or an erasure queues hundreds of notices in one transaction with the same timestamp: a cursor on time alone skips every one of them past the page boundary. `GET /me/notifications/unread-count` is one indexed count; `POST /me/notifications/{id}/read` is idempotent and a 404 for somebody else's notice. The one switch that words a notice is now `lib/notice-text.ts`, shared by the panel and the page. The header's "Updates" link shows the count for anyone signed in and asks nothing of a signed-out visitor.

**Options considered:**

1. Put the message text in the notice payload
2. **A flag in the payload and the words on the application** (chosen)
3. Detect phone numbers and redact them
4. **Do not copy free text at all** (chosen)
5. Exclude employer notes from the export
6. **Include them, and say so on the form** (chosen)
7. A second CSV writer beside the list
8. **One serialiser for both** (chosen)

**Trade-offs:**

- Option 1: ✅ The email carries the details ❌ A phone number sits in a table and a mailbox; the retention purge is the only thing between it and an incident.
- Option 3: ✅ Keeps the convenience ❌ A regular expression is a promise it cannot keep (a number written in words, a name and an address), and the failure is silent.
- Option 5: ✅ Employers write more freely ❌ It is a legal right of access over data this product holds; hiding it makes the product a place where notes about people cannot be asked about.

**Consequences:**

- **A candidate with only a phone is reached in-app**, as every notice is; the email path is the minority's.
- **Free text to a person is unmoderated.** A reported vacancy is moderated (ADR-069); a message inside an application is a private channel between two people who already share contact details by the candidate's own act. Capped, tied to a row the candidate can delete by withdrawing or erasing; not solved.
- **The header gained a request on every page for a signed-in person** (one count, on mount and on focus, not polled). Its hook is a separate module from the page's heavier ones: putting the infinite-query code in the header's import graph took `/profile` over its 684 KB budget by a kilobyte, and the split brought it to 683. **The budget headroom is now 1 KB.**
- **Found by the browser run, fixed at the cause:** an `aria-label` on the Updates link replaced the visible words and failed WCAG 2.5.3 (label in name), so the link has no label and says the count once, in words, beside a drawn number hidden from assistive technology; and an unread notice panel above the application list pushed the list down by its own height (a layout shift of 0.110 on a phone), so the panel now sits below it.
- **Measured by tests that fail without the rule:** a message not replaced, cleared on the wrong transition, or erased by a no-op click; the words reaching the outbox; the plain template used for a message; a withdrawn applicant leaking into the spreadsheet; each of the formula cases; a cursor on time alone; a notice readable by somebody else; the notes in a candidate's response or missing from their export. One mutant (adding a `notes=` argument to the candidate's constructor) is equivalent: Pydantic ignores it, and the structural test guards the schema instead.
- **Not done:** a message thread, notes visible to the candidate, a per-vacancy bulk status change, an email digest, and a count on the employer's side for unread applications.

## ADR-071: An Operator Enrols an Agency's File From the Back Office, and the Consent It Stamps Is an Attested Claim Recorded Against a Named Operator

**Status:** Accepted (October 2026). Sprint 61 (BL-14.10). Migration 0054. Extends ADR-042, ADR-044, ADR-055 and ADR-063.

**Context:** The government-agency actor has no login (Sprint 33), so an operator stands in for it. Enrolling an agency's file could only be done by `scripts/bulk_enrol_candidates.py`, run by an engineer with database credentials. The script creates accounts for people who have not touched the product and stamps the current privacy notice against each of them, on the footing of a self sign-up: it trusts that the notice was read out, and nothing recorded who vouched for that. Its validation was also thin (a "phone" needed eight digits, a spreadsheet's `nan` raised in `int()`, a name could exceed the length the profile editor allows, a number repeated inside one file was not noticed, and every row shared one transaction).

**Decision:**

- **One engine, in `operations/enrolment.py`, called by both the back office and the script.** It is a sibling of `marketplace/bulk.py` (ADR-026, ADR-063: `bulk.run` is hard-wired to a tenant and to vacancies and courses) and reuses its file reading. To make that possible without moving a 1,482-line module, `parse_file` was split into a kind-free `parse_records(text, columns=, required=, max_rows=)` that it now calls, and the whole-number cell rule is exported as `int_cell`; the existing 129 bulk tests are the guard that nothing about vacancies and courses changed. The script is a thin caller (dry run unless `--apply --attest --operator-email`).
- **The check and the apply run the same decision.** `_decide` is called by both, and the apply only adds the writes, so a check cannot promise what an apply would not do. Outcomes per row: `new` (an account is made through `identity.provision_candidate`, the one place a `User` is built from nothing), `tag` (an existing person gains the programme and nothing else; what they told us is never overwritten), `already` (already in a programme, left alone and named), `error`.
- **The attestation is a row.** `apply` is refused with a 422, before anything is read, unless the operator confirms the privacy notice was read out to everyone in the file. `enrolment_batches` records who, when, the notice version, the programme, the file name and four counts. It does **not** verify that the conversation happened and the screen says so; what it does is make the claim a named person's, on a row, instead of an assumption in a script. A person's own export says how they came to be in a programme (`agency_enrolment`: the programme, when, whether an account was made for them, the notice version attested) and never who the operator was.
- **Admin tier only** (`OPS_ENROL`, in `OPERATOR_PERMISSIONS` and `TIER_PERMISSIONS["admin"]`, not in support). Making accounts for other people and stamping their consent is at least as consequential as a takedown (ADR-069). A support operator is not shown the panel (the server's 403 is the guard; the page's absence is courtesy).
- **Nothing it reports can be dialled.** A phone appears masked (`+9198*****001`), a person by the first word of their name, in every report; the failed rows come back as the operator's own file plus an `error` column through `errors_csv` (formula-safe, ADR-070). No log line, event or payload carries a number or a name; the `enrolment_applied` event carries the programme and four counts.
- **A row that is wrong costs that row.** Each apply runs in its own savepoint; a number that appears twice in one file is an error on the second row naming the first; a number another request created in the meantime is the unique constraint refusing it and reads as `already`, never a 500; and a tag path takes `FOR UPDATE` on the profile so two programmes tagging one existing person cannot both win. `db.rollback()` is never called mid-loop (it expires the session; ADR-070's Sprint 55 lesson).
- **Phone and field validation is the profile's own.** An Indian mobile only (`+91` then a digit 6 to 9 then nine ASCII digits, so a Unicode digit or a superscript cannot pass), name at most 120, headline 160, years 0 to 60 through `bulk.int_cell` (`nan`, `inf` and a decimal are a problem on the row). An unrecognised state or district is a **warning**, not an error: the text is kept beside an empty id ("no id is better than a wrong one"), and the warning says it is invisible to location matching until fixed.
- **The record lives on the operations side.** `enrolment_batch_members(profile_id PK, batch_id, outcome)` points at `candidate_profiles` (CASCADE), rather than a column on the profile pointing at `operations`: `marketplace` cannot import `operations` (ADR-014), and a foreign key from a model to a module it may not import is a mapper-configuration failure for every script that loads one without the other. `enrolment_batches.actor_user_id` is SET NULL, so an operator's own erasure leaves the record. `tests/test_privacy_coverage.py` lists the batches table as excused (an operator's audit trail, like `tenant_verification_events`) and the members table as exported.
- **The row cap is a setting, `ENROLMENT_MAX_ROWS`, default 1,000**, with the upload body allowance of 2 MB (the path joins `_BULK_UPLOAD_PATH`). Measured on the test database: a 1,000-row **check takes 0.08 s and an apply 4.2 s** (about 4 ms a row, an account, a personal tenant, a membership and a profile each). That is acceptable for a one-off operator act and is why the cap was not raised; a larger file is split.

**Options considered:**

1. Keep the script and give an operator a way to call it
2. **A back-office upload on one shared engine, the script a thin caller** (chosen)
3. A programme/agency login and a self-service portal
4. **Operator-attested enrolment now; an agency login when a real agency exists** (chosen)
5. A column on `candidate_profiles` pointing at the batch
6. **A join table on the operations side** (chosen)
7. Skip people who already have an account
8. **Tag them, leaving everything they entered untouched** (chosen, Sprint 33's behaviour)

**Trade-offs:**

- Option 1: ✅ No new surface ❌ Anyone who can run it can create accounts with consent stamped and no named person behind it; it is the problem this sprint exists to remove.
- Option 3: ✅ The agency owns the claim ❌ A second login model, tenant type and consent receipt for an actor no real agency has asked to be; ADR-042 argues against speculative escalation paths.
- Option 5: ✅ One query away from a profile ❌ The cross-module key above.
- Option 7: ✅ Nobody is tagged without a choice ❌ Defeats the agency's own count for people who registered before the programme; one line to change if the owner prefers it.

**Consequences:**

- **Consent is still asserted, not verified.** An operator can tick the box without reading anything out. The stronger forms (a consent receipt the person gives, an agency login) are out of scope; the attestation makes the gap visible and names who is responsible.
- **An existing self-registered person in an agency's file is tagged** and so appears in that programme's counts. Nothing about them is shown to the agency (counts only, small cells hidden, ADR-057), and their export now says it happened.
- **An enrolled person has an account and no session.** They sign in by code like anyone, with consent already on file (a test and the browser journey do exactly that). Until SMS exists (DLT, deferred) the code does not reach a real phone, so the end-to-end proof is with the exposed development code.
- **Found while doing it:** the Dependabot bump moved Playwright to 1.64 and the browser suite could not start until its matching Chromium build was installed (`npx playwright install chromium`, 99 MB), a step CI performs itself.
- **Measured by tests that fail without the rule** (19 breakages each fail a test): no attestation, a check that writes, a non-mobile number, a repeated number, an overwritten profile, a re-tagged person, no savepoint, a wrong member outcome, an unmasked phone, a wrong notice version, no actor, years and name limits, a dropped place warning, no consent stamp, support allowed, the body limit, and an export that drops the enrolment. The component has seven (the attestation, the admin gate, forgetting a review when the programme changes, the attest flag sent, the file forgotten after use, problems sorted first, an oversize file never read). One is **not** guarded: clearing the file input after reading it (a browser fires no `change` for the same file twice), which jsdom cannot model, as in Sprint 52.
- **Not done:** an agency login, a consent receipt from the person, an SMS to say they were enrolled, a programme table (the name stays free text), undoing a batch, and an upload history beyond the 50 most recent batches.

## ADR-072: The Mobile App Is a Second Client of the Same API, in the Same Repository; Released Operations Are Additive-Only and an Old Build Is Told to Update

**Status:** Accepted (October 2026). Sprint 62 (BL-15.1, BL-15.7). Extends ADR-002, ADR-016 and ADR-029. No migration.

**Context:** The owner asked whether the product should be carved into a separate branch and rebaselined to ship as an Android and iOS app. The web app is a Next 16 application with 43 pages, 87 client components, 12 families of dynamic routes and 26 files that fetch on the server, so it cannot be packaged into an app shell without reworking every dynamic page. The owner chose a native client (Expo / React Native) for the job seeker, with deployment and the mobile launch run together. The question underneath is what stays shared and what must change when a client can no longer be updated by deploying.

**Decision:**

- **No separate branch and no rebaseline.** The backend is the contract and stays one. The app lives in a new top-level **`mobile/`** directory of this repository; `web/` and `api/` are not moved. Work is on short-lived `mobile-N` branches merged to `main`, one per sprint, like Sprints 56 to 61; a store release is tagged `mobile-vX.Y.Z` so a build can be reproduced and a hotfix cut from the tag.
- **v1 is candidate-only.** The PRD persona is a phone-only candidate on a low-end Android. Employers, providers and operators work on the website, which is already responsive; a phone signed in as one is told so rather than shown half an app. About 16 screens, not 43 pages.
- **One generator, one set of words, one set of colours.** `make gen-api-mobile` writes `mobile/src/api/schema.d.ts` from a fresh `app.openapi()` with the web's own `openapi-typescript` (a clean run is a zero-line diff against the web's schema, which it was). `make sync-mobile-messages` copies the web's catalogues, read by `use-intl` (next-intl's framework-free core, ICU plurals included); the phone-only strings are `app.en.json` and `app.hi.json` under a `mobile` namespace. `scripts/sync_mobile_tokens.py` generates `tokens.ts` from `globals.css` (colours only; shadows are CSS and the overlay is rewritten to `rgba()`), so a palette cannot be edited in one place and not the other. `tests/test_mobile_foundations.py` fails when any of the three is stale.
- **The portable core has no React Native import** (`mobile/src/core`): the API client, the token store, the sign-in flow, the locale rule. It is a port of `web/src/lib/api.ts` and keeps what that file cost a day each to learn (one refresh at a time; auth endpoints matched by exact pathname; the request is cloned before it is sent), with four differences: tokens are injected and async, the language is injected, every request names the build, and a **426** reaches the app.
- **Tokens live in the Keychain and the Keystore** (`expo-secure-store`, device-only), behind one file, with an in-memory copy because the client asks on every request. A locked keystore means "signed out", never a crash.
- **Released operations are additive-only.** A web page ships with the API; an installed app does not and cannot be updated on demand. `mobile/contract/surface.txt` names the operations the app calls and `mobile/contract/openapi.snapshot.json` records them as they were at the last store release (every `$ref` inlined). `api/core/contract.py` says what would break an installed app: a removed operation or success response; a response property removed, retyped, made nullable or no longer always present; a request that now needs something the app does not send (a new required property or parameter, a smaller maximum, a narrower enum). A widened *response* enum is reported and does not fail, because whether it breaks depends on whether the app is exhaustive over it. `tests/test_api_contract.py` holds the real API against the snapshot inside `make check`, and `make snapshot-contract` only **adds** operations (`--release` re-records everything at a store release, after the minimum version has been raised if a build must be retired). The surface file is held equal to the operations the app's code calls by a test, so the list cannot drift from the code.
- **An old build is told to update.** The app sends `X-App-Version` and `X-App-Platform`; `AppVersionMiddleware` answers **426 Upgrade Required**, with the minimum in `X-Min-App-Version`, when the version is below `MOBILE_MIN_VERSION_ANDROID` or `_IOS` (separate, because the two stores review at different speeds). The default `0.0.0` retires nothing. **It fails open on purpose**: a missing header (the web app), an unreadable version or an unknown platform is served, because locking out someone whose header was garbled is a worse failure than serving an old build. `/health` is never gated. The app replaces itself with an update screen on any 426.
- **A styling dependency was left out of M1.** The plan named NativeWind; M1 uses a plain token hook and `StyleSheet` instead, because NativeWind's build configuration is the part most likely to be wrong when it cannot be run, and the tokens are the same either way. It can be adopted later without touching the tokens.

**Options considered:**

1. A separate long-lived branch or fork for mobile
2. **A `mobile/` directory in the same repository on ordinary short branches** (chosen)
3. A Capacitor shell over the hosted web app
4. A bundled static export of the web app
5. **A native client (Expo / React Native) for the job seeker** (chosen by the owner)
6. Hand-maintaining the mobile types, strings and colours
7. **Generating all three from the web's** (chosen)

**Trade-offs:**

- Option 1: ✅ No risk to `main` ❌ Doubles the upkeep of an API and a web app that do not change, and the two drift.
- Option 3: ✅ Weeks, not months ❌ Apple's minimum-functionality review is a real risk for a wrapper, and it needs the web app deployed first.
- Option 4: ✅ Works offline ❌ Needs every dynamic route and server-rendered page reworked for static export.
- Option 5: ✅ The feel and store acceptance the owner wants ❌ The most expensive: every one of the 87 client components' behaviour is re-implemented, only the data layer carries over.

**Consequences:**

- **Two front ends will diverge.** Mitigation: the API is the one contract, a feature reaches the phone only after it is on the API, and `projectContextForMe.md` carries a parity list.
- **The API becomes additive-only for the operations on the surface.** This is the largest change in how the project is run: a rename the web would have taken in a sprint now needs the old and the new shape side by side until the minimum version is raised.
- **The React Native layer was written first and verified afterwards.** M1 was written without the toolchain (the owner declined a download of roughly 400 to 700 MB), with `mobile/src/core` checked under the web's TypeScript and Vitest. The owner then allowed the install, and the whole app was compiled for the first time: **one** type error across the layer (an `/auth/me` response that narrows to `never` on its failure branch), and then `tsc` (strict, TypeScript 6), `eslint` (Expo's config), a Metro bundle for Android and iOS, and **53 Jest tests** run through `jest-expo` (the 39 core tests unchanged, plus the sign-in and home screens rendered against the real catalogues). Surprises worth recording: Expo SDK 57 (React Native 0.86, React 19.2, TypeScript 6) ships optional peer ranges that npm's strict resolver rejects, so `mobile/.npmrc` sets `legacy-peer-deps=true`; `@react-native/jest-preset` must be exactly `react-native`'s version; the i18n packages are ESM-only and need `transformIgnorePatterns`; React Native Testing Library 14 is async and needs `test-renderer`; no `babel.config.js` is needed or wanted; and a test file under `app/` would be a route, so screen tests live in `src/test/`. `package.json` and `package-lock.json` are committed, the SDK-matched set coming from `create-expo-app` and `expo install`.
- **Still not verified, and nothing automated stands in for it:** a run on an emulator or a phone, whether **Hermes** formats Hindi plurals and dates like Node does (`use-intl` relies on `Intl`), TalkBack and VoiceOver, and performance on a low-end Android. The first job of M2 is a screen on a device.
- **The production audit is not clean and cannot be made clean from here.** `npm audit --omit=dev` reports 24 advisories (14 high, 10 moderate): every high one is Metro, the Expo CLI or a dependency of them (build tooling that does not ship), and the one that does ship is a moderate slow decode of a malformed deep link (`decode-uri-component` through `expo-router`'s `query-string`). `npm audit fix --force` would break the SDK. CI fails on `critical` only; the next SDK is the fix.
- **Real SMS and a reviewer login are still open.** A phone code cannot reach an App Store or Play reviewer, and without SMS delivery (DLT, deferred) nobody outside development can sign in. They are BL-15.8 and BL-12.9 and gate the launch more than any screen does.
- **The application id `in.iism.app`, the name and the store URLs are placeholders** until the store accounts exist.
- **Measured by tests that fail without the rule:** a version compared as text, `/health` gated, a missing header locking somebody out, the platform ignored, no minimum in the 426, and each of ten contract rules (15 breakages, each fails a test).
- **Not done in M1:** push notifications, deep links, any screen beyond sign-in and a front door, and the on-device checks above. The CI job for the app exists (`mobile`: audit at `critical`, `tsc`, `eslint`, `jest`, an Android Metro bundle).


## ADR-073: The Phone Persists Public Data Only, by an Allow-List of Query Keys, and Formats Numbers and Dates Without `Intl`

**Status:** Accepted (October 2026). Sprint 63 (BL-15.2, M2 of the mobile programme). Extends ADR-072. No migration, no API change beyond ten read operations added to the released surface.

**Context:** M2 gives a visitor who has not signed in the three catalogues (vacancies, courses, standards), a search and a remembered language. The target is a low-end Android on mobile data, so a list that blanks when the connection drops is a defect, and a cache of what was last seen is wanted. Two things made the obvious route wrong. First, the web's service worker keeps personal data out of its cache with a **deny list**, and a deny list fails open: a new personal endpoint is cached until someone remembers to add it. Second, the shared catalogues format with `Intl` (`use-intl`, `Intl.NumberFormat("en-IN")`, `format.dateTime`), and Hermes, the phone's JavaScript engine, does not give the same answer as Node for Hindi plurals or `en-IN` grouping on every device. Neither a simulator nor a phone exists on the machine this was written on, so the answer had to be one that does not depend on the engine.

**Decision:**

- **What is persisted is an allow-list, not a deny-list.** Every visitor query is keyed `["public", <locale>, kind, filter]` (`mobile/src/lib/queries.ts`). `persist.ts`'s `isPublicKey` accepts only a first key element of `"public"`; the persister keeps a query only if it is public **and has data** (`query.state.data !== undefined`). `shouldDehydrateMutation` is `() => false`. A personal query (`["me"]`, `["profile"]`, `["matches"]`, anything later) is therefore not persisted **by default**, and a test names each. The cache lasts 24 hours and is cleared when a person signs out.
- **A failed refetch must not discard what is on the screen.** The first version kept only `status === "success"`, so a request that failed while offline replaced the stored list with nothing; the browser run found it. The condition is `data !== undefined`, which is also what lets the app read offline.
- **The wipe is the transition, not the state.** The root layout wipes the stored cache when the signed-in state goes from true to false (`createSignOutWatch`), never on `false` alone: the token store reports `false` while it loads on every cold start of a signed-out visitor, which wiped the cache at every launch.
- **The language is a stored choice** (`iism.locale`), restored before the first screen, with the device language as the first-run default and **not written back** (so a changed phone language is followed until the person chooses one).
- **Numbers and dates are formatted by two small pure functions, not `Intl`.** `formatInr` groups in the Indian way (2,38,370), and `formatDate` reads `YYYY-MM-DD` with month names from the catalogue (`mobile.months.*`); India has no daylight saving, so a calendar date needs no time zone and cannot slip a day. Both are tested at the lakh and crore boundaries and across a leap year.
- **`Intl.PluralRules` is polyfilled only where it is missing**, with `@formatjs/intl-pluralrules` and `en` and `hi` data, installed synchronously at start-up (`installPluralRules`, before `use-intl` formats anything). It is the one thing the shared ICU messages need from the engine.
- **A screen is a function of the one scorer's fields, a list never says "no results" before its first answer, and an outage is not a 404** (the web's rules, Sprints 20 and 54): `ResultList` shows a skeleton until the first answer, a failure notice that keeps the server's own sentence and a retry when the first page fails, and keeps the rows already on screen when a later page fails.
- **The labels are ported, not shared.** `experienceLabel`, `salaryLabel`, `feeLabel`, `whereLabel`, `intakeLabel` and `seatsLabel` are pure functions over a translator in `mobile/src/core/labels.ts`, copying the web components' rules (zero and unstated fees both read "free"; an online course has no place to name). Two copies can drift; the catalogues are shared, and the rules are tested on the phone side.

**Options considered:**

1. Persist everything and filter personal queries out by a deny-list (the web's service worker)
2. **Persist only what is keyed public** (chosen)
3. Persist nothing
4. `Intl` for numbers and dates, with Hermes' behaviour checked on a device later
5. **Two pure functions** (chosen), and a polyfill for plural rules only

**Trade-offs:**

- Option 1: ✅ one rule for the whole app ❌ fails open; the first personal query added after it is cached.
- Option 3: ✅ nothing to leak ❌ a dropped connection blanks a list the person was reading.
- Option 4: ✅ no code to maintain ❌ cannot be proved from here, and a wrong plural or a wrong digit grouping reads as a fault.

**Consequences:**

- **Verified by running the real screens in a browser**, through `react-native-web` at 375x812 against a second API instance: Home, Jobs (148 vacancies, `₹2,45,000–3,25,000`), Courses in Hindi (the language survives a reload, "179 पाठ्यक्रम"), the three details, search (vacancies, then roles, then standards), the error and retry state, and **reading the cached courses with the API stopped**. This is not Hermes and not a native run; it is a real rendering of the same components. Both platforms compile to Hermes bytecode (`expo export`), which proves the syntax and imports and nothing about runtime behaviour.
- **Mutation-checked**: 28 behaviours in the portable core and the screens, each broken and each failing a test (a persisted personal key, mutations kept, a no-data query kept, a wipe at every launch, an off-by-one page, a page size, a fee of zero, the order of standards, a 404 for an outage, a query key without the language, a skeleton or failure shown out of order, the language not stored). **One real defect was found by it**: `feeLabel` did not treat a fee of zero as free, which the test already asserted; the file on disk disagreed with it, and it was fixed. Three Python guards also fail when broken (a require cycle, a second file touching async-storage, an undeclared package).
- **Still not verified**: a run on Android or iOS, Hermes' actual `Intl` behaviour, TalkBack and VoiceOver, scrolling on a low-end device, and a physical phone against a real network. The README says how to run the app on one in five minutes.
- **The released surface grows by ten operations** (`/jobs`, `/jobs/{slug}`, `/courses`, `/courses/{slug}`, `/skills`, `/skills/{slug}`, `/skills/search`, `/skills/{slug}/jobs`, `/skills/{slug}/courses`, `/roles/search`), which are now additive-only for as long as a build that calls them is installed.
- **Not in M2:** applying, matches, the profile, notices, reporting a listing (M3 and M4), push notifications and deep links.


## ADR-074: The Phone Holds a Person's Data in Memory Only and Drops It at Sign-Out; Applying and Registering Interest Are the Consent Moment and Say So; the Score Is Displayed, Never Derived

**Status:** Accepted (October 2026). Sprint 64 (BL-15.3, M3 of the mobile programme). Extends ADR-037, ADR-070 and ADR-073. No migration, no backend change; sixteen operations are added to the released surface (33 in all).

**Context:** M2 let a visitor read the catalogues. M3 is the first time the phone holds a person's data: their profile, their matches, their applications (with an employer's message) and the courses they asked about. It is also where the phone starts to *disclose* something on a person's behalf (a name, a mobile number and an email reach an employer or a provider). Three questions followed: where may personal data live on a phone that may be shared, what makes the disclosure the person's own act, and how much of the website's scoring display should the phone re-derive.

**Decision:**

- **Everything about a person is keyed `["me", ...]`** (`mobile/src/core/me-keys.ts`) and is **never persisted**: ADR-073's allow-list keeps only keys starting `"public"`, so a personal query cannot reach the disk by being added. A test names each key and refuses it; another fails if a personal query is built anywhere but `lib/me-queries.ts`.
- **Signing out drops all of it, whole.** `forgetEverything` clears the query client (not merely the `"me"` keys: a half-cleared cache is a bug waiting for the next key) and the stored public cache. The transition rule from ADR-073 stays: a signed-out cold start is not a sign-out. The plan for this sprint assumed the in-memory cache was *not* cleared on sign-out; reading the layout found that M2 already did it, untested, in an inline callback. It is now one tested function, wired to the real token store in a test, and the browser run signed one candidate out and another in with nothing of the first remaining.
- **A signed-out person, and an account with no job-seeker side, make no request that can only answer 401 or 403.** Every personal query waits for the account (`/auth/me`) to say there is a job-seeker membership; an organisation owner who signed in on a phone is told, in the web's words, that this is the job seeker's app.
- **Applying and registering interest are the consent moment.** The confirmation step is the web's, from the same catalogue: it names the organisation, says that applying sends the person's name, mobile number and email for this vacancy only, and says that withdrawing takes them back. Nothing is sent by the button that opens it, nothing is pre-filled, and cancelling sends nothing. A closed vacancy says so *before* asking anyone to sign in.
- **A failed write says what it was.** A table keyed by status (`applying.ts`) names a duplicate (409), the daily cap (429) and a non-seeker account (403); a withdrawal that meets a 409 says a decision was made; **401 is shown as an expired session, never as a failure**; the server's own sentence is shown when it kept one (a 60-standard cap, a salary range) and the generic line only when it did not. A Python guard fails when a screen calls a mutation hook and never reads its `.isError` or `.error`: the web's `mutation-errors.test.ts`, for the phone.
- **The phone displays the scorer's fields and computes nothing about them** (ADR-037). Score, coverage, cap, shortfalls and locality are fields; the words around them are the web's. The only arithmetic is the one identity the web also allows (the level the person attained is the required level minus the shortfall).
- **A card that holds a button is not a button.** The applications, saved and interests lists first made each card pressable *and* put Withdraw inside it. On the web that is a button inside a button (invalid HTML, found by running the screen in a browser); on a phone it hides the inner control from a screen reader. The card is plain and its own "View the job" button opens the page. A test per list asserts the card is not a button.
- **Dates a person sees are the day in India.** `formatInstantDate` reads a timestamp by hand (the API sends microseconds, which engines parse differently) and shifts it by the fixed +05:30; 20:00 UTC on the 14th is the 15th. No `Intl`, as in ADR-073.
- **The role picker is the web's, with its rules in a pure module** (`role-picker.ts`): nothing starts ticked, electives stay in their groups, a standard already held is shown ticked and cannot be ticked again or sent, and a batch is all or nothing at the server's cap of 60. Profile limits are mirrored on the inputs and the education levels are a record keyed by the schema's own union, so the compiler fails when the server adds one.

**Options considered:**

1. Persist the signed-in person's data so the app opens instantly offline
2. **Memory only, dropped at sign-out** (chosen)
3. Persist it encrypted in the Keychain
4. Re-derive the score display on the phone from the matched and missing lists
5. **Show the server's fields** (chosen)

**Trade-offs:**

- Option 1: ✅ a faster cold start ❌ on a shared phone the next person could see the last one's applications and an employer's message; and ADR-023 asks for an encryption path before this kind of data is kept.
- Option 3: ✅ safe at rest ❌ a second secret-handling path that nothing here can test on a device; deferred, not refused.
- Option 4: ✅ no round trip ❌ two derivations of one number, which is how a picture and a score come to disagree.

**Consequences:**

- **Verified by running the real screens in a browser** (`react-native-web`, 375x812, against the dev API as two seeded candidates, English and Hindi): matches with the gap and real courses, a match opened, applying through the confirmation, the application listed and withdrawn, the role picker through to a real skill added and removed, sign-out, and a second candidate who saw nothing of the first. It found the nested-button defect above. This is not Hermes and not native.
- **Mutation-checked: 43 breakages**, each failing a check. Four survived the first pass: a personal key the keys test did not list, a role-picker mutant that was equivalent (the reset on choosing a role made it unobservable; a better one was written), a guard mutant that removed only `.isError` while `.error` was still read (the check was right, the mutant too weak), and, most usefully, **no test that adding a skill refreshes the matches**. Each was closed and re-run.
- **A page reload signs the browser run out.** `expo-secure-store` has no web backend, so the session does not survive a reload under `react-native-web`; the phone's Keychain and Keystore are unaffected. It only constrains how the run is driven (navigate by tapping, never by URL).
- **Not on the phone yet**, each deliberate: the per-request course budget (ADR-068; held in `localStorage` on the web), reporting that a suggested course was opened (the click-through metric of ADR-025 is therefore web-only until M4), the work history, education, certificates, languages, preferred-location and salary sections of the profile, "why not me", and career paths. The basics and the skills are what move a match and what BL-15.3 asks for.
- **Still not verified**: a native run, Hermes, TalkBack and VoiceOver (the checkbox rows carry the `checkbox` role and a `checked` state, which is the part a test can assert), and scrolling on a low-end device. `expo-doctor` reports 20 of 21: five Expo packages are one patch version behind what the SDK now asks for; no package was changed in this sprint.


## ADR-075: A Push Is Something the Worker Does for an In-App Notice, Says Nothing From the Notice, and Reaches a Person Only Through a Phone They Registered

**Status:** Accepted (October 2026). Sprint 65 (BL-15.6, M4 of the mobile programme). Extends ADR-006, ADR-017, ADR-023 and ADR-070. Migration 0055.

**Context:** After M3 the app could not tell a candidate anything: an employer's reply, or a vacancy that closed, was visible only on opening the app. A push notification is the way a phone is told. It is also a new place to leak: it is drawn on a lock screen, kept by the operating system, and sent through a vendor. The outbox already had two channels (`email`, `in_app`) and the rule that a row names a recipient and holds no address.

**Decision:**

- **A phone is a row** (`device_tokens`): the token, the platform, the language, two times. A token is unique and **belongs to one person at a time**: registering one another account holds *moves* it, in one atomic upsert, because on a shared phone the last person to sign in is the one the next push is for. A person holds at most ten; unregistering is idempotent, deletes only the caller's own, and answers the same whether the token was theirs, someone else's or unknown. It is erased with the account and shown in the export (platform and dates, **never the token**: it is a credential for sending to that phone, and a downloaded export is a file that gets forwarded).
- **A push is not a channel. It is a stamp** (`notifications.pushed_at`) on an in-app notice to a person. The first design was a `push` channel with a companion row written when a notice was queued, only for a person with a phone; a statement-count test that already existed (the alert sweep must not query once per candidate) failed on it, because deciding "does this person have a phone" at queue time put a query on the request path for every notice. The worker decides instead (`notifications.service._sweep_push`, in the drain): it looks at in-app notices to people not yet stamped, sends to their phones, and stamps every row it looked at, phone or no phone, so the partial index it reads (`ix_notifications_unpushed`) holds only what is still owed. **Queuing a notice runs no query** and a test asserts it. A person with no phone costs a stamp; one who registers a phone later is not sent what they missed.
- **Switching it on replays nothing.** Migration 0055 stamps every existing notice, and the sweep stamps without sending anything older than 24 hours (a worker that was down must not turn into a lock-screen flood): the `alerted_at` lesson of Sprint 27, again.
- **A push says nothing from the notice.** Its words come from a fixed table keyed by template and language (`templates.PUSH_TEXT`, no format fields, English and Hindi); its data is the template name and an **in-app path** (anything that does not begin with a single `/` is dropped). No vacancy, organisation, person or employer message reaches it: a push is shown on a lock screen, and ADR-070 already says a regular expression cannot promise to keep a phone number out of free text, so none gets in. A template with no entry in the table is never pushed.
- **The token is resolved at send time and stored on no notice row**, as an address is. A token the provider reports dead is deleted, so a phone that left is not held about for no purpose. A failure retries up to `MAX_ATTEMPTS` and then gives up; the in-app notice is untouched either way, and a push failure never changes an email's outcome.
- **The provider is a port** (`api/adapters/push`, ADR-017). The console implementation logs a digest of the token and **refuses production**, like its siblings; a real provider (Expo Push, FCM, APNs) is a later one-file change with credentials the owner has not yet created.
- **The app asks in context, never at launch**: the first time somebody opens their updates, with a sentence saying what a notification will and will not show, and a "not now" that is remembered. The decisions (`shouldAsk`, `shouldRegister`, where a tap goes) are pure functions; `src/push.ts` is the one file that touches `expo-notifications`. Registration is a quiet no-op on the web and in a build with **no EAS project id**, which Expo needs to issue a token and which belongs to the owner's account. Sign-out removes this phone from the list **before** the session ends (bounded to three seconds so a slow network never holds sign-out up).

**Options considered:**

1. A `push` channel with a companion row queued with each in-app notice
2. **A stamp on the in-app notice, swept by the worker** (chosen)
3. Send from the request that creates the notice
4. A push that carries the vacancy's title and the organisation's name

**Trade-offs:**

- Option 1: ✅ one row per message, a status per push ❌ a query per notice at queue time (found by a statement-count test), and a second row for every in-app notice of a person with a phone.
- Option 3: ✅ immediate ❌ an outage of the push vendor would fail the very thing being described (ADR-006).
- Option 4: ✅ a more useful lock screen ❌ vacancy titles and an employer's words on a screen anyone can read, kept by the operating system.

**Consequences:**

- **Verified end to end against the real worker and the development database**: a phone registered over HTTP as a seeded candidate, three in-app notices queued, and one worker tick later the log shows three pushes with the fixed words and only a path as data, a digest instead of a token, and the notices stamped.
- **Not verified**: a real notification on a real phone. There is no device, no EAS project and no vendor account here; `expo-notifications` is compiled and bundled, nothing more.
- **A signed-out phone keeps its token until the next person registers it** when the session was ended by the server (a refused refresh) rather than by the person: the pushes it could carry say nothing, and the next registration moves the token.
- **Every notice in the sweep is looked at once**, up to 500 a minute; at larger volume the batch size is the first thing to measure (`make seed-scale --notifications`).

## ADR-076: Store Reviewers Sign In With a Fixed Code on Named Phones, Behind an Explicit Production Switch, and Only to a Demonstration Account

**Status:** Accepted (October 2026). Sprint 65 (BL-15.8, M4 of the mobile programme). Extends ADR-032, ADR-038 and ADR-066. No migration.

**Context:** Both app stores reject an app their reviewer cannot sign in to, and sign-in here is a code sent to a phone (there is no password anywhere, by decision). A code sent to a phone the reviewer does not hold cannot reach them, and SMS delivery (DLT) is not built. The setting that echoes codes in the API response, `otp_expose_in_response`, must never be on in production: it is refused at startup there, and `expose_otp` is `flag and is_local`.

**Decision:**

- **A named exception, off by default.** `REVIEWER_LOGIN_ENABLED` (false), `REVIEWER_PHONES` (at most five, each a phone), `REVIEWER_CODE` (exactly `otp_length` digits, from the environment, never the repository). For a listed phone `request_otp` stores the configured code and sends no SMS; every other number takes the normal path unchanged. **The request is otherwise identical**: same rate limit and cooldown, same answer, so it is no oracle for who is on the list; the attempt cap still burns the code after five wrong guesses.
- **It does not weaken the echo.** `OTP_EXPOSE_IN_RESPONSE` is still refused outside development, whatever else is set; the end-to-end check ran the reviewer sign-in with the echo **off** and it worked on the fixed code alone.
- **Startup validation refuses an unsafe configuration**, in every environment: no phones, an entry that is not a phone, more than five, a code that is not exactly `otp_length` digits, and (outside development) a guessable code (one digit repeated, or a straight run up or down).
- **It opens only a demonstration account.** At verification a listed phone whose account is an **operator** or **holds an organisation** is refused (403, "demonstration accounts only") and a warning is logged without the phone. A misconfigured list naming a real person's number would otherwise hand a store reviewer that person's account, or an organisation's applicants.
- **`scripts/create_reviewer.py` only ever creates.** It makes a candidate with the current notice recorded against `--attest` (ADR-071: consent on someone's behalf is an attested claim with a name on it), a place and four declared standards, so the reviewer sees matches. A phone that already has an account is an error and nothing is written. Dry run by default.

**Options considered:**

1. A reviewer password or a second credential type
2. A bypass for any number when the switch is on
3. **A fixed code for named phones** (chosen)
4. Real SMS to a number the stores can read (a mailbox or a virtual number), with no exception in the code

**Trade-offs:**

- Option 1: ✅ familiar to a reviewer ❌ the product has no passwords and no hashing dependency, deliberately (ADR-038); adding one for a single audience adds a login path every attacker would try.
- Option 2: ✅ nothing to configure ❌ every account becomes enterable.
- Option 4: ✅ no exception ❌ needs SMS delivery, which does not exist, and the reviewers' number is theirs to change between submissions.

**Consequences:**

- **Verified end to end** on a second API instance with the echo off: the reviewer account was created by the script, signed in on `482913`, saw eight matches; a stranger's number with the same code got a 401; a second run of the script wrote nothing. The test account was erased afterwards.
- **Mutation-checked**: the code accepted for any phone, with the switch off, for a staff account, for an organisation member, for an unnormalised phone, a guessable code, an empty list, and the script adopting an existing account or skipping the attestation each fail a test.
- **The code is a shared secret with the stores**: it should be rotated after a review and the switch turned off between submissions. That is a procedure for the release runbook (BL-15.5), not something this change can enforce.

## ADR-077: A Release Build Fails Closed, What Is Still the Owner's Is Counted Rather Than Hidden, and the Stores' Answers Are Checked Against the Data They Describe

**Status:** Accepted (October 2026). Sprint 66 (BL-15.5, M5 of the mobile programme). Extends ADR-072 and ADR-076. No migration, no API change (the contract is untouched).

**Context:** The app was complete on the code side and had never been released. Everything between it and the stores is either the owner's (accounts, the real name and bundle id, an EAS project, a deployed HTTPS API, a push vendor, SMS under DLT, the grievance officer, the app's own artwork) or can be made ready without them. Two failure modes mattered more than any missing file: **shipping a placeholder** (the first inspection found the icon, adaptive icon and splash are still the Expo template's, and the bundle id is `in.iism.app` by ADR-072's own admission), and **shipping a build that cannot reach anything**, because `config.ts` falls back to `http://localhost:8000` (or an emulator's `10.0.2.2`) and Android blocks cleartext traffic in release builds while Apple's App Transport Security refuses it.

**Decision:**

- **A release build refuses to start on a development origin.** `core/release.ts` (`configProblems`, pure) is fed the build's own `EXPO_PUBLIC_API_BASE_URL` and `EXPO_PUBLIC_WEB_BASE_URL` and `!__DEV__`; a missing origin, an `http://` one or a local one (`localhost`, `127.*`, `10.0.2.2`, `::1`, `*.localhost`) makes the root layout render `Misconfigured` instead of the router. The person is told in plain words to reinstall; the reason goes to the console. A development build is never judged.
- **One checker owns "is this configuration fit to ship"** (`scripts/check_release_config.py`, `make check-release`, stdlib only so CI's node job runs it). It separates **errors** (a defect in what is written: a cleartext or local origin in any profile, a missing icon or a wrong size, a permission the app does not use, encryption not declared, a missing build profile) from **open** items (a decision only the owner can make that is still a placeholder: the bundle id, a `REPLACE`/`.invalid` host, a store link, the EAS project id, the Expo template's artwork recognised by hash, the grievance officer). Errors fail every profile; open items are **reported for every profile and fail `production` only**. So the build stays green while the accounts do not exist, and a production build cannot be cut by accident. **Today `production` exits 1 and names thirteen items; that is the correct state.**
- **Release configuration is files, not memory**: `eas.json` (a `preview` and a `production` profile whose origins and store links come from per-profile `env`, never a default; remote app-version source with auto-increment; an app bundle for Play; a `submit` section of placeholders), `app.json` (an explicit one-permission Android list plus blocked dev-merged ones, `usesNonExemptEncryption: false`, the splash, the unused Face ID string removed from the secure-store plugin). Each was **checked by running `expo prebuild` into a scratch copy** and reading the generated manifest and Info.plist: the release Android manifest holds `INTERNET`, `POST_NOTIFICATIONS`, `VIBRATE`; cleartext appears only in the debug manifest; ATS is not relaxed.
- **The stores' answers are derived from the data they describe, and the data changes under them.** `docs/release/privacy-and-data-safety.md` has one row per section of the DPDP export, and `tests/test_release_docs.py` fails when the export (kept equal to the schema by `test_privacy_coverage`) gains a section the inventory does not name. The listing is held to each store's character limits in **both** languages and refuses claims the product cannot back (a guarantee, a placement, "best", a number the app does not compute); the reviewer notes may hold no code or phone number (they name the variable); the runbook must keep the steps that are forgotten (switching the reviewer login off and rotating the code, the contract re-record, the closed test, the restore drill, rollback).
- **A size ceiling, not a target** (`mobile/budget.json`, `make check-mobile-budget`, in the `mobile` CI job): the Android Hermes bundle (3.43 MB measured, ceiling 3.8 MB) and the assets. Launch time is not claimed: that needs a device.
- **Accessibility is held by the props that produce it, and says what it cannot see** (`mobile/ACCESSIBILITY.md`): every touch target at least 48 dp (a chip was 40), every `Pressable` a role, every control a name, text capped at 200% (`MAX_FONT_SCALE`) instead of unbounded, a decorative tick hidden from the reader, a notice one focusable item. TalkBack, VoiceOver, 200% on a real screen and Hermes are a checklist for a person with a phone.

**Options considered:**

1. A manual release checklist only
2. A checker that fails on every placeholder in every profile
3. **A checker that separates defects from open owner decisions and gates only `production` on the latter** (chosen)
4. Wait for the accounts and write all of this then

**Trade-offs:**

- Option 1: ✅ no code ❌ the placeholders are exactly what a checklist forgets (the template icons were found by looking, not by any check).
- Option 2: ✅ simple ❌ CI is red until the owner finishes, which teaches people to ignore red builds (CLAUDE.md, the golden-set decision).
- Option 4: ✅ nothing speculative ❌ the first real build is then also the first time the configuration is read, and the checks above would be written under submission pressure.

**Consequences:**

- **A defect found by the sprint's own browser run**: a local `expo export` reused Metro's transform cache and kept the old `EXPO_PUBLIC_*` values, so a build with the variables set still said `api-missing`. EAS builds start clean; a local release build needs `--clear` (the runbook says so).
- **Mutation-checked** (27 mutants; five survived the first run: two were real gaps, since nothing tested a placeholder origin or store link and the layout guard matched a log line instead of the render, and both were closed; three were badly written mutants; all killed after): cleartext or local origins accepted, placeholders ignored, template artwork ignored, an extra permission, the encryption flag, the production gate returning 0, a Hindi title over its limit, a listing that promises a guarantee, an inventory that forgets the push tokens, a code in the reviewer notes, a runbook without the switch-off step, a bundle over its ceiling, a `Pressable` with no role, text without the font cap, a 40 dp chip, a notice that is not one item, and the root layout or `config.ts` not consulting the check.
- **Not done and not claimed**: any EAS build, any submission, any device or emulator run (no TalkBack/VoiceOver, no Hermes `Intl` check for Hindi, no low-end timing, no real push). The privacy answers and the listing are drafts for the owner and a lawyer to confirm against each console's current form.
- **`expo-splash-screen`** was added (the template shipped a splash image and nothing to display it) and **`expo-dev-client` was not**: a development profile in `eas.json` would need it, and it is a download nobody asked for.
- Four patch-level Expo packages were brought level with SDK 57 (`expo-doctor` 21 of 21).

## ADR-078: The Phone Holds No Data the Website Does Not, Edits a History Section Through One Table Checked Against the Schema, and Keeps a Course Budget Only on the Device and Only Until Sign-Out

**Status:** Accepted (October 2026). Sprint 67 (BL-15.9 to BL-15.11, M6 of the mobile programme). Extends ADR-048, ADR-049, ADR-068, ADR-072 and ADR-074. No migration, no new endpoint: five operations that the website already calls join the released surface (46 to 51, additive only).

**Context:** After M5 the phone still lacked what the website's candidate has: the six history sections of the profile (work, education, certificates, languages, preferred roles and places), "Why not me" on a rejected application, career paths, and the course budget that reorders suggested courses. All of it was already on the API. The questions were what the phone should and should not take on, and how to keep a screen that edits six differently shaped things from drifting from the server.

**Decision:**

- **A phone adds no data type the website does not hold.** The Data Safety and App Privacy answers (`docs/release/privacy-and-data-safety.md`) are unchanged. **Date of birth and gender stay web-only**: they are optional and sensitive, nothing on the phone needs them, and a phone is the device most likely to be shared. A person's salary range, notice period, work type, willingness to move and alert opt-out are the same fields the website edits.
- **The six sections are one table** (`core/profile-sections.ts`: fields, limits, defaults, the rules that span fields) and one editor, as on the website. The server's routes take an **untyped body**, so no generated type carries a limit; instead `tests/test_mobile_section_limits.py` reads the table's literals and compares each with the schema the server validates against (lengths, required, ranges, enumerations, defaults, and that the routed collections are the edited ones). A changed server limit fails a build, not a person.
- **A date is a month and a year**, typed into two small fields and sent as the first of the month: no picker package (native code nothing here can run). **An edit that leaves the month and year alone sends back the exact date the entry already had**, and an edit sends the whole entry (the server reads an absent field as "clear it"), so a start date the website recorded as the 15th, or a certificate's NSQF level the phone never shows, survive an edit made on the phone. A skill link is never sent, so the server leaves it alone.
- **"Why not me" is offered on a rejection only**, computed at read time from the person's skills as they are, never stored, and says nothing about why an employer decided (the product does not know). **Career paths** say what they are derived from and flag a guessed starting role as a guess.
- **The course budget is a device-held preference, not profile data** (ADR-068 kept it off the profile for the same reason). It is remembered on the phone, sent only as `?budget_inr=`, **forgotten when the session ends** (a shared phone must not carry the last person's figure), and is the **last** element of a query key so every existing prefix invalidation still reaches every variant of a match.

**Options considered:**

1. Edit the history sections on the website only
2. **One table-driven editor, limits compared with the schema by a test** (chosen)
3. A hand-written screen per section
4. A date-picker package

**Trade-offs:**

- Option 1: ✅ nothing to build ❌ the sections feed the completeness meter, and a phone-first candidate is told to finish their profile on a laptop they may not have.
- Option 3: ✅ each screen reads plainly ❌ six places for a limit to drift; the website already learned this (`constraints.test.ts`).
- Option 4: ✅ a familiar control ❌ a native module that cannot be run or checked here, for a rule ("month and year") that two number fields meet.

**Consequences:**

- **Verified** by tests in Node and with the real screens rendered against the real catalogues, plus mutation checks and a browser run; **not** on a device. A date typed as a month and a year is a convention, not a picker, and the Hindi layout of the new screens is unchecked on a real phone.
- The released contract grows by five operations and nothing is removed or retyped; the old 46 are byte-identical in the snapshot.
- A new section, or a new field in one, is an entry in the table and a line in the schema guard, not a screen.

## ADR-079: A Listing Says What Decides Whether to Open It in the Units People Use, a Rule Both Clients Share Is Tested Against One File, a Count Comes From the Server, and Touch and Type Have Floors a Browser Test Holds

**Status:** Accepted (October 2026). Sprint 69 (BL-16.1, from the UI review of Sprint 68). Extends ADR-037, ADR-065, ADR-068, ADR-072 and ADR-074. No migration. One endpoint is new (`GET /jobs/states`, public, additive) and the two operator queues change shape (`/ops/organisations` and `/ops/candidates/certifications` return `{items, total, limit, offset}`); neither is in the released mobile surface, which stays at 51.

**Context:** The review (ADR-less, `docs/design/`) found the core loop correct and hard to scan: a vacancy card read as a database row (a generated sentence, an "NSQF level 4 and above" badge, no verified mark), pay was per year where the work is quoted per month, the apply button sat above the title, a skills list repeated one standard in capitals under two codes, targets under 44 px and text under 12 px were on every page, and three lists silently printed the length of a page as a total (`/jobs` and `/courses` at 200 rows, the operator's queue at 100 against 162).

**Decision:**

- **A card carries what decides whether to open it, in the order people ask: what, who, where, how much, by when.** The employer carries a verified mark when it has earned one; **a card never says "not verified"**, because in a list the absence of a mark would read as an accusation of every employer without one, and the vacancy's own page is where "not yet verified" and "never pay to apply" are stated. The NSQF level and the generated sentence leave the card (they stay on the page). "Closes in n days" is derived at render within 30 days and never stored. **There is no "posted n days ago"**: the public payload has no published date (`created_at` is the draft's), so it would be invented; a `published_at` column is a later migration.
- **Pay is said as a month where the posted annual figure is a salary** (`full_time`, `part_time`, `contract`, `apprenticeship`), rounded to the nearest ₹100 and prefixed "about"; one end alone is "from" and a maximum alone says nothing; a **gig keeps its posted figure** ("as posted"); a figure under about ₹600 a year stays annual rather than read "₹0 a month". The vacancy shows the monthly line first and the yearly beneath it.
- **A rule that two clients both need is written twice and tested against one file.** `payLine` and `presentRequirements` exist in `web/src/lib/` and `mobile/src/core/` (the clients share no package), and both are run over `tests/fixtures/pay_cases.json` and `requirements_cases.json`; a Python test fails when either side stops reading its file. **A gap found by mutation:** no case had the stronger duplicate first, so a "last one wins" version passed until one was added.
- **A list that pages counts from the server.** `/jobs` and `/courses` ask for 24 and say the total with "Show more (n left)"; the state filter is **the catalogue's own list** (`GET /jobs/states`, counted with the listing's `open_job()` predicate, so an option always has a result), because it used to be read off whichever 200 rows had loaded and the geography table's names ("MAHARASHTRA") are not the jobs' ("Maharashtra"). The operator queues return their true size and the screen says "Showing 100 of 162". A source test (`web/src/lib/paged-counts.test.ts`) fails on `count: rows.length` in any component that reads a paged query.
- **The action the page exists for stays under the thumb.** On a phone the apply bar is the last thing in the visual order (`order-last`, `sticky bottom-0`) and second in the document, so a screen reader meets it with the facts; it rests where the content ends, above the footer. On the app, `Screen` takes a `footer` outside the scrolling part, height-capped and scrolling on its own, and an account that cannot apply gets **no bar rather than an empty strip** (`useApplyVisible` is the one rule the panel and the screen both read).
- **Floors are held by tests that can fail.** Nothing is set below 12 px (`--text-2xs` is 12 px; 35 literal sizes went; `web/src/lib/type-floor.test.ts`), and a control in the header or the footer is at least 44 px (`buttonVariants` sm/md/icon, the header, the language select and the footer links; a `checkPage` addition fails the browser sweep on any page). **Only the header and the footer are asserted**, because they are the same markup on every page and one fix clears them; the rest of a page is a count in the review.
- **A standard's name is presented, never edited.** Identical names (case and spacing ignored) collapse to one carrying the strongest flag and the highest importance; a name with no lowercase letter is sentence-cased; generic entries ("Employability skills", "OJT", "On-the-job training", matched at the start of the name) go under "Also covered". "Importance 5 of 5" becomes a "Must have" chip or nothing.

**Options considered:**

1. Fix the cards and leave the lists, the floors and the totals for later
2. **One sprint across the web and the phone, with a shared fixture and floors in tests** (chosen)
3. Compute a monthly figure and the skills presentation on the server
4. Show "not verified" on every card

**Trade-offs:**

- Option 1: ✅ smaller ❌ the silent caps are defects, not polish, and a card that scans well over a list that drops row 201 is the wrong half to have fixed.
- Option 3: ✅ one implementation ❌ the released phone's contract is additive-only (ADR-072), a presentation rule would become an API promise, and a seeker's language and rounding are display concerns; two small pure functions and a shared fixture cost less than a contract.
- Option 4: ✅ blunt honesty ❌ at this scale most employers are unverified; a list full of "not verified" tells a seeker nothing and punishes every employer that has simply not been reached yet.

**Consequences:**

- **Measured** with the review's own script on a production build, same pages, phone width: `/jobs` 42.3 to 7.5 screens, `/courses` 53.4 to 8.8, text under 12 px from 296 on `/jobs` (1,000 or more across the sampled pages) to **0 on every page**, targets under 44 px on `/jobs` 15 to 0 and the header and footer clear on all 52 captures (what is left is inline links and a few in-page buttons, counted not asserted). The Sprint 68 numbers are kept as the baseline in `docs/design/screens/` beside the new file.
- **Mutation-checked**: 37 breakages (34 in code, 3 in the browser sweep); two survived (the "last duplicate wins" version and a type badge hidden behind a gate the test never opened), each exposed a real gap in a test, and both were closed. A browser test for the sticky bar first asserted the bar stayed visible *through the footer*; the bar correctly rests where its content ends, and the test was wrong, not the page.
- **Not done and not claimed**: this is expert judgement with measurements, not user research (whether monthly pay or the trust strip changes behaviour is for the five-person check, BL-16.4); no device, no TalkBack or VoiceOver; paging past 200 is tested with a constructed catalogue (the seed has 148); no posted date; the match screen keeps its apply buttons in the page on purpose (its gap and courses are the content); a course page has no trust strip (it lost the slug line only).
- The first-load budget on `/admin` is now 682 KB of 684: the operator's queue brought `useInfiniteQuery` with it.

## ADR-080: A Match Is Explained in a Sentence Built From the Fields the Scorer Returned, a Count of Matches Comes From Where the Rows Are, and the First Screen Is the Person's Own

**Status:** Accepted (October 2026). Sprint 70 (BL-16.2, from the UI review of Sprint 68). Extends ADR-036, ADR-037, ADR-074 and ADR-079. No migration, no new operation: one existing field (`total` on `GET /me/matches`) now says what it always claimed, and the released surface stays at 51.

**Context:** After Sprint 69 a vacancy could be judged at a glance; what a first-time job seeker met before it was still an expert's tool: a homepage of eight sections that opened on "NSQF-aligned skill intelligence", a matches page that opened on a dashboard of charts with the first match a screen down, a match card that was a report (a ten-chip level scale, lists of full standard names and codes) whose answer to "why 45%, and what do I do?" sat at the bottom, and a signed-in phone home that was the signed-out one plus "You are signed in".

**Decision:**

- **A match is said in a sentence, from the lists the scorer returned and nothing else.** `matchSummary(matched, missing)` (web `lib/match-summary.ts`, phone `core/match-summary.ts`, both run over `tests/fixtures/match_summary_cases.json`, ADR-079's pattern, a Python test holds that both read it) counts the two lists after the vacancy page's presentation rules (`presentRequirements`): one standard listed under two codes counts once, a standard held under any code is held, and the **generic entries every qualification carries ("Employability skills", "OJT") are left out**. The score still counts them, so the sentence says "skills this job asks for", never "the score is": it is an explanation a person can act on, not a restatement of the number. Missing names are required ones first, at most two, the rest counted ("and 2 more").
- **One primary action per match.** With a gap it is "See courses that close this"; with none it is the job itself. The level scale, coverage bar, capped note and the you-have / you-need chips with codes are behind a native `<details>` (web) or a toggle that announces expanded or collapsed (phone). The list shows five and "Show more (n left)".
- **A count of matches is counted where the rows are.** `GET /me/matches` answered `total=len(page.items)`, the page length (capped by `limit`), so no screen could say "14 matches" from it; the dashboard's `match_count` was the honest figure. `match_jobs_with_total` returns the number before the cut (scoring already happens for all of them, so it costs nothing); `match_jobs`' signature and its callers (the golden set, the alert sweep) are unchanged. When more matched than were sent (the best fifty), the page says "your best 8 of 137" instead of implying it is everything. A test holds the page total equal to the dashboard's figure.
- **The matches page opens on the matches.** One line from the dashboard's own figures ("14 matches · best 87 · profile 100% complete"), the charts mounted only while "Your numbers" is open.
- **The homepage says what the product does in the seeker's words, and leads with the one thing a visitor came to do.** Search, five one-tap example jobs (an **English query with a label in the visitor's language**: the corpus is English, and a Hindi alias exists for only some roles), the "I'm here to" chooser, and two small links for employers and providers. A test fails if the framework's vocabulary (NSQF, framework, taxonomy, "occupational standard", criteria) returns to what a seeker reads first, in English, Hindi and Malay. **By the owner's choice only the framework band moved** (to About, as `FrameworkBand`); the live people figures and the browse panels with live counts stay, and the "three sides" cards went, replaced by two links.
- **A signed-in phone home is the person's own** (`SignedInHome`): the best match with its sentence and a way into it, profile completeness and the next step, new updates, and the applications an employer acted on **in the last 14 days** (no "read" state exists, so without a window a rejection from last spring would be news for ever; the window is a constant and a tested rule). It makes **no request the app did not already make** and is mounted only for an account that holds a job-seeker profile. **Applying is not offered on it**: the match summary carries no employer name, and the consent step names the employer ("this sends your name, mobile number and email to Apollo Care").

**Options considered:**

1. A real language model writes the explanation
2. **A sentence assembled from the scorer's own fields, tested against shared cases** (chosen)
3. Leave the report, add a summary above it
4. Add an apply button to the phone home by widening the match list with the employer's name

**Trade-offs:**

- Option 1: ✅ fluent ❌ ADR-005/018 keep decisions and their explanations deterministic; an explanation that can differ from the score by being clever is the one thing this must not do.
- Option 3: ✅ smallest ❌ the report still leads, which is what the review measured as the problem (15 screens, the answer at the bottom).
- Option 4: ✅ one fewer tap ❌ a new field on a released operation for a button whose consent text is the point; the match screen is one tap away and already does it right.

**Consequences:**

- **Measured** with the review's own script on a production build, phone width: `/matches` 15 to **4 screens**, small targets 45 to 1, text under 12 px 215 to 0; the homepage 7.7 to **6.0** screens (7.9 just before the sprint; the plan said "about 5": the people figures and browse counts the owner kept are most of what is left) with the framework band moved to About (2.5 to 3.3); the phone's signed-in home is pictured against the signed-out one.
- **Mutation-checked** (30 breakages across the sentence rule on both clients, the strip, the card, the homepage composition, the jargon guard, the example queries, the backend total and the phone home; one survived: an organisation account handed the personal home would sit on a placeholder for ever and nothing noticed, now asserted and killed).
- **Not done and not claimed**: this is expert judgement with measurements, not user research (whether the sentence is understood is exactly what BL-16.4 would settle); the Hindi copy was written by the engineer and needs a native reader before launch; nothing was run on a device; the phone's apply is a tap away, not on the home; "posted n days ago" is still not built.

---

## ADR-081: Role-Search Vocabulary Is Measured Against Titles Written Before It, a Hold-Out Is Reported Separately, and an Unreviewed Draft Says So Where a Reviewer Will Find It

**Status:** Accepted (October 2026). Sprint 71 (BL-12.12). Extends ADR-050 and ADR-054. No migration, no new operation (the released surface stays at 51), and **no ranking change**.

**Context:** "Name your job" is the door to everything a job seeker gets: the role picker turns a title into the standards behind it, and the standards are what a match is scored on. The search is only as good as its vocabulary, and it had almost none: 114 alias rows leading to 41 of 3,417 roles. Sprints 43 and 45 fixed ranking defects, not coverage, and nobody had measured how often a person's own word reached a sensible role. The backlog's note on BL-12.12 says a batch needs someone who knows the labour market to review it; the owner chose to proceed on engineering's draft.

**Decision:**

- **Titles are written before the aliases and not from what search answers.** `tests/fixtures/role_titles.json` holds 146 titles people say (118 English, 12 romanised Hindi, 16 Devanagari) across the sectors. Each carries the corpus roles that honestly fit, chosen by meaning from a listing of the corpus (an exact name, or a case-insensitive pattern over role names), or `none_ok` for a job the corpus has no role for, with a list of roles that must not lead. Labels were widened once after the first baseline (the corpus names roles in ways an exact list missed: *Bijli Mistry*, *Yoga Instructor (B&W)*), before any alias was added, and that is written in the file.
- **A hold-out is kept and reported separately.** Forty-one of the 146 are `hold`: none is an alias key (a test fails if one is), the evaluator hides their per-title lines unless asked, and their rate is reported on its own line. It was **seen once during the sprint**, in a run that still printed those lines; it did not move, so nothing was fitted to it, and the evaluator was changed so it cannot be read title by title by accident.
- **The evaluator is `make evaluate-roles`** (`scripts/evaluate_role_search.py`), like `make evaluate`: it needs the national import, so CI holds the **shape** of the fixture (`tests/test_role_titles.py`) and the pure `judge` and `summarise` functions, and the number is a thing a person runs. A title with an answer passes when an accepted role is in the first three; a `none_ok` title passes unless the first result is a rejected role or a disability-track pack.
- **The batch** adds 193 surface forms (307 now) onto 88 roles (41 before): English, romanised Hindi and Devanagari (40 forms in all), grouped by sector in `role_aliases.py`. Each target is a general pack (never `PWD/`), verified by `make check-role-aliases` against the real corpus, which removed four forms on its first run (three equalled an exact role title that another alias pointed elsewhere, one made "cab" ambiguous). Terms that name no single role stay out (helper, mechanic, machine operator, nurse, loader, packer, bouncer) and so do jobs the corpus has no role for (housemaid, maid, accountant, turner, lathe operator). The module's old claim that "waiter" and "mason" had no general pack was wrong and is corrected; both are keys.
- **The batch is flagged as an unreviewed draft where a reviewer will look**: the `role_aliases.py` header, the summary sheet of `docs/IISM-Role-Aliases-for-Review.xlsx` (one row per form with empty keep / change / retire columns, built from the dict alone so a test can fail when it is stale), and this ADR. The rows are `source='seed'`, so an admin-tier operator can retire or change any of them on `/admin` today (ADR-054); a retired form is not revived by a reload.
- **No ranking change shipped.** The plan allowed one only if aliases left a gap an alias could not close. After the batch, the tuning set's remaining misses were two missing aliases (added) and one `none_ok` title, "accountant", which leads with a corporate-law diploma because the word is inside "Chartered Accountants". That is a corpus gap, not a ranking defect, and a rule to prefer whole words risks the Sprint 43 and 45 invariants for one word.

**Options considered:**

1. Ship the alias batch and report that it works
2. **Measure against titles written first, report a hold-out, ship the batch as a flagged draft** (chosen)
3. Fuzzy or embedding search for the unmapped words
4. Wait for a market reviewer before adding anything

**Trade-offs:**

- Option 1: ✅ fastest ❌ a number measured on the words that were fitted is a number about the fitting; it is what "the search is better" would mean to nobody.
- Option 3: ✅ generalises ❌ the Hindi and trade words share no letters with the corpus (ADR-050's finding), the semantic adapter is a placeholder (ADR-013), and a guess that leads confidently is worse than a missing answer.
- Option 4: ✅ every row defended ❌ the search stays at 41 roles of 3,417 while the person who types "mason" gets a bricklaying qualification pack's neighbours.

**Consequences:**

- **Measured** (`make evaluate-roles`, top-1 and top-3 over titles with an answer; the baseline was recorded before any alias was added): all titles **65.5% / 66.9% to 81.7% / 83.1%**; the tuning titles **76.5% / 77.5% to 99.0% / 100%**; English 70.2% / 71.9% to 83.3% / 85.1%; romanised Hindi 50.0% to 66.7%; Devanagari 43.8% to 81.2%. **The hold-out did not move: 37.5% / 40.0% before and after.** That is the honest result. An alias covers the word it names and the ranking does not generalise from it, so of forty titles no alias names, fewer than half reach a right role in the first three. The tuning number measures the fitting; the hold-out says what an unseen word gets, and closing it is a matter of more vocabulary from someone who knows the words, not of the ranker. The `none_ok` titles are 3 of 4 not led astray, as before ("accountant" still is).
- **Mutation-checked** (17 breakages: an alias to a disability-track pack, one shadowing an exact title, one to a role that does not exist, the evaluator counting a miss as a hit or ranking ten as a pass or ignoring the hold-out or its patterns, a `none_ok` title answered with a rejected or disability-track role, a duplicate query, an empty accept list, a hold-out title that is an alias key, the seed sync overwriting or removing an operator's row, a pre-filled, stale or unflagged workbook). The first run of the three alias mutations **survived** because the checker reads the table and not the dict; the checks sync the table first, and the lesson is in `CLAUDE.md`.
- **Not done and not claimed**: nobody who works in these labour markets has read the batch; the title set is the engineer's idea of how people speak, not usage (logging real searches would breach ADR-023), so the hold-out measures generalisation inside that idea; the corpus is English and incomplete; no device and no Hindi keyboard was tried.

---

## ADR-082: Withdrawing Consent Is a Pause the Account Survives, a Changed Notice Is Confirmed and Never Enforced, and the Notice Is Checked Against the Data

**Status:** Accepted (October 2026). Sprint 72 (the DPDP readiness slice). Extends ADR-023, ADR-055, ADR-069 and ADR-071. Migration 0056 (one column and a partial index). Three operations (`GET`/`POST /me/account/consent`, `POST /me/account/consent/withdraw`) and two derived fields on `UserOut` (`consent_current`, `consent_withdrawn`), all additive: the released surface goes from 51 to 54 operations, the old 51 untouched.

**Context:** India's DPDP Act substantive obligations are enforceable from 13 May 2027. A survey of the code found most self-serve mechanics built (a consent stamp with a notice version, export, erasure with a preview, retention crons, a grievance queue) and five gaps that need no outside account: the **privacy notice was wrong** (it said employers never see a name or contact, but applying shares both; it omitted date of birth, gender, salary, application messages, notices and device tokens); **withdrawing consent was only deleting the account**; **a signed-in person was never re-asked** when the notice changed; **the 18-and-over promise was checked nowhere**; and **no breach procedure existed**.

**Decision:**

- **Withdrawing consent pauses the account and keeps it** (`users.consent_withdrawn_at`). Its effects are each read at one choke point and each has a test that fails without it: the person is out of every employer pool, alert sweep and public people figure (`marketplace.paused_profile()`, used by `matching.retrieval.candidate_pair_facts` and `skilled_profile()`); **applying and registering interest refuse with 409** (`identity.require_not_paused`, inside the two service functions, not the handlers); the applications and interests that still show their details are **taken back through the modules' own `withdraw`** (so an employer's decision is kept, ADR-052) and the person is told how many before confirming; **nothing is recorded against their account** (`analytics.record` and `record_many`); and **no push is sent** (the worker's sweep stamps and skips). They can still sign in, read, export, correct, delete and restore. **This is a pause, not an erasure.** Whether that satisfies DPDP s.6(4) is a legal question the notice and this ADR hand to counsel; deletion sits beside it on the same page.
- **A withdrawal and an apply at the same instant cannot leave contact shown.** An apply reads the stamp under `FOR SHARE` and keeps the lock until it commits; the withdrawal's `UPDATE` of the stamp conflicts with it, and the stamp is committed **before** the sweep takes anything back, so nothing new can be shared while it runs. Two race tests hold the row from a third session until the request is provably waiting (`tests/test_consent_race.py`). A first version also took `FOR UPDATE` on the withdrawal's read; a mutation check showed it changed nothing (the `UPDATE` conflicts all the same), so it was removed rather than kept as a guard no test can fail.
- **One act re-consents and restores.** `POST /me/account/consent` records the version in force and clears a withdrawal; a stale version is refused (422), because consent to a text nobody can identify proves nothing. **A changed notice asks and never blocks**: `UserOut.consent_current` drives a banner, and nothing is switched off while the person decides. The banner is **fixed to the bottom of the window**, which was the third placement tried: above the content it pushed the page down; below it, the dashboard arriving after `/auth/me` pushed *it* down (0.108 on the browser sweep, over the 0.1 budget of ADR-065); a fixed element moves nothing. "Not now" hides it for the session only.
- **The age gate rides on the consent sentence, not on a new field** (a required request property would break ADR-072): the sentence says "I am 18 or over", `PRIVACY_NOTICE_VERSION` moved to `2026-10-17` (which also made every existing consent stale, so the banner is exercised for real), and a **date of birth that would make the person younger than 18 is refused on write** with a sentence a form can show. Stored dates are not rewritten. Whether and how a minor may ever use the product is the owner's call.
- **The notice is rewritten from what is stored and is checked against it.** It now says what an employer sees in a candidate list (a reference, never a name) **and** what is shared when you apply or register interest (name, phone, email, any message, withdrawn when you withdraw), lists date of birth, gender, salary, notice period, application messages, notices, the phone's push code and the numeric skill summary, separates withdrawing from deleting, and says who is told of a breach. `tests/test_notice_covers_inventory.py` walks the person-bearing models and fails on any column that is neither covered by a phrase the English notice must contain nor excused with a reason, so the next stored field cannot slip past it. The Hindi and Malay catalogues carry the same structure; **the Hindi was written by the engineer and needs a native reader, and the whole notice still needs a lawyer** (it keeps its "draft pending legal review" badge).
- **A breach procedure exists** (`docs/release/incident-response.md`): detect, triage, contain, preserve, notify, recover, review, naming only controls the code already has (`revoke_all_for_user`, rotating `JWT_SECRET_KEY`, the reviewer switch, `redacted=True` in the logs, `make restore-drill`). **The law's timings and who must be told are left to counsel** and the file says so; a test keeps the stages, the controls and the absence of any secret, phone or code.
- **Not added: analytics events for withdraw and restore.** A closed set with a hand-written CHECK migration for two counts nobody reads yet; the structured log carries `consent.withdrawn` and `consent.confirmed` with no personal data, and the stamp is the record.

**A found defect, fixed at its cause.** The browser journey used a brand-new candidate and saw "Could not load your matches": the first page asks for matches and a dashboard at once, both found no profile and both inserted, and the unique constraint refused the second as an unhandled 500 (which carries no CORS header, so the browser hid it). Every other test creates the profile first, on purpose. `ensure_profile` now inserts in a savepoint and the loser takes the winner's row (ADR-052's move); a race test widens the gap.

**Options considered:**

1. Leave withdrawal as deletion
2. **Pause, and say so** (chosen)
3. Pause, then erase automatically after a period
4. Block everything until the changed notice is confirmed

**Trade-offs:**

- Option 1: ✅ nothing to build ❌ not "as easy as giving it", and the notice said it.
- Option 3: ✅ closer to erasure-on-withdrawal ❌ a retention number and a legal position nobody has taken; deleting the account stays one tap away for anyone who wants it now.
- Option 4: ✅ certain re-consent ❌ a person locked out of their own export and deletion by a notice they have not read; the grievance of the product elsewhere (ADR-066) is exactly that.

**Consequences:**

- **Measured on the scale harness** (50,042 profiles, 5,151 vacancies, interleaved with a clean worktree of `main`): the first, correlated `EXISTS` cost the employer shortlist about 100 ms at p95 (370 to 384 ms against 233 to 264); the uncorrelated `IN` over a partial index (`ix_users_consent_withdrawn`) is **275 to 280 ms against 260 to 264**, about 6% at p95, p50 164 to 196 against 146 to 150 (within the noise of a loaded machine). **Recall is unchanged**: 20 of 20 on the candidate side, 18 of 20 on the employer side with tie-aware 1.00, identical to `main`.
- **Verified:** 1,891 backend, 677 web, 697 mobile and 131 browser tests; **35 mutation checks** over the choke points, the guards, the lock, the version, the contract, the notice, the runbook, the banner and the phone (all killed; one survivor was the redundant lock above, another a weak heading test, both fixed). The real Account page was walked in the browser: the preview, the withdrawal, the paused banner in Hindi, dark, at 375 px.
- **Not done and not claimed:** compliance certification; encryption at rest for date of birth, salary and notes (its own sprint and a key-management decision); a nominee record; dormant-account erasure; a lawyer's review of the notice and the runbook; a native reader for the Hindi; anything on a device. A person who withdrew is paused for ever until they confirm or delete: there is no automatic erasure.

---

## ADR-083: The Hiring Side Gets One Primary Action Per Row and a Back Office You Can Jump Around, a Reference Panel Is Folded and Loaded When Opened, and a Finding Is Read Against the Code Before It Is Fixed

**Status:** Accepted (October 2026). Sprint 73 (UI-14, UI-15, UI-16 and UI-26 of the Sprint 68 review). Extends ADR-065 (no layout shift), ADR-079 (a 44 px floor) and ADR-082. No migration, no new operation; the released surface stays at 54.

**Context:** The job seeker has had four design passes; the employer console, the provider workspace and the operator back office none. The review's own numbers on a production build: `/admin` was one scroll of 40 screens on a phone with no way to jump; each vacancy and course row ended in four or five loose links about 20 px tall (181 targets under 44 px on `/admin`, 52 on `employer-home`, 69 on `provider-home`); the funnel and pool bars had no legend. `/admin` was also the route nearest the first-load budget (698,039 of 700,000 bytes). Reading the code before fixing found three things the review had wrong or missed: **UI-26 was mis-stated** (nothing in the API generates a description and bulk upload does not inherit one; the generic text was 129 job and 129 course literals in the demonstration seed), the funnel **already scaled to its first step**, and `OrganisationReview` showed **verify and revoke to a support-tier operator, who gets a 403**.

**Decision:**

- **`/admin`: the daily work first and open, the reference panels folded, one nav.** Overview, Verification, Grievances and Reports stay on the page; Programme outcomes, the district skill gap, Role aliases and Enrolment are closed `<details>` rows of fixed height (`CollapsiblePanel`), and `AdminNav` is a sticky row of eight native anchors (44 px, scrolling sideways on a phone, wrapping from `sm` up, Enrolment shown to the admin tier only). The section ids come from one list (`admin-sections.ts`) that the nav and the page both read, and a source test holds the page to it. No tabs: the component library removed them on purpose, and an anchor needs no script.
- **A folded panel is loaded when opened, not before.** `AdminPanels` loads the four panels with `next/dynamic` at module level and `CollapsiblePanel` mounts one the first time its row opens, so their code leaves the route's first load **and** their queries stop firing on a visit that does not open them. An anchor to a folded panel (`#admin-aliases`) opens it. **`/admin` first-load JS went from 698,039 to 686,248 bytes** (headroom 1,961 to 13,752); `/profile` is now the closest route (3,237 bytes). The earlier notes of "1 KB" and "16 KB" headroom in `CLAUDE.md` were stale and are replaced by measured figures.
- **One primary action per row** (`RowActions`): a live vacancy's primary is **See candidates**, a draft's is **Publish**; a live course's is its **interested learners**; **Edit** is beside it; Unpublish, Close/Reopen and View public are behind a native **More** (`<details>`, in the flow, never floated over the card). Every control is a `Button`/`ButtonLink` at the 44 px floor. A vacancy an operator took down offers only Edit.
- **The charts say what they mean.** One line above the by-vacancy list explains amber (new applications waiting) and blue (none waiting), and the funnel's count outweighs its bar. Its widths are unchanged: they were right.
- **A block that is above something people look at must be the same shape before and after it loads.** The browser sweep, with `/admin` newly on a phone, failed the back office at 0.2 to 0.3 of layout shift: the verification queue now sits directly under the overview (it used to be two panels below, off screen), and the overview's placeholder was a different height. The overview now renders its heading and its six tiles with dashes while loading (`StatTile` draws a dash for no value, never a zero) and puts its one variable-length part, the scarce-skills list, behind a closed row of fixed height that exists before and after.
- **Support tier.** `OrganisationReview` offers verify and revoke only to the admin tier, and says why to anyone else; the server's `OPS_ORG_VERIFY` was already the rule.
- **Descriptions, honestly.** The seed writes **no description** for the 258 generated rows (six patterns, one filter, held against every tuple by a test that also checks both loops use it; a stale Hindi twin from an earlier run is dropped). The **bulk check says once, for the file**, how many rows have no description or one under 30 characters, and when an update would clear one; it changes no row's status. A first version warned **per row**, which changed 17 existing expectations on purpose and would have printed 200 identical warnings for a spreadsheet with the column left blank. The editors say what to write. **Not built: refusing to publish with no description**, the only fix that blocks anyone, which is a new 422 on a released operation and the owner's to choose.

**Two things the browser taught that a unit test could not:** Playwright's `getByText("Published")` is a case-insensitive **substring** match over an element's concatenated text, so it matched the new actions container (`Publish` and `Edit` side by side read `PublishEdit`) the instant it rendered, and two journeys passed their wait before the publish had happened; a status badge is now matched with `exact: true`. And a `<summary>` whose text carries a decorative chevron does not match an exact text lookup; a journey clicks it with `locator("summary", { hasText })`.

**Options considered:**

1. A tabbed back office with a tab per section
2. **A jump nav, daily queues open, reference panels folded and lazy** (chosen)
3. Move each panel to its own route
4. Leave the row's links and make them bigger

**Trade-offs:**

- Option 1: ✅ one section visible at a time ❌ Radix tabs cost bytes on the route with the least headroom, and every journey would click a tab before it could see a queue.
- Option 3: ✅ smallest pages ❌ ten new routes, each in the sweep in two languages, and an operator loses the single page that shows what is waiting.
- Option 4: ✅ no new component ❌ five equal controls at 44 px is a taller, no clearer row; the finding was that no action was primary.

**Consequences:**

- **Measured** with the review's own capture script on a production build against the demonstration database (the baseline is `measurements.json`; the figures are `measurements.sprint73.json`): `/admin` **40.2 to 27.9 screens** on a phone and **31.2 to 24.8** on desktop, targets under 44 px **181 to 0** and **236 to 0**; `employer-home` targets **52 to 0**, `provider-home` **69 to 0** (its page is about half a screen longer, because the buttons are 44 px); nothing under 12 px anywhere. The two long queues are still long: the verification queue shows 100 of 162.
- **Verified:** 1,913 backend, 714 web, 697 mobile and 134 browser tests; **26 mutation checks** over the nav, the folded panel, the anchor, the static-import guard, the support-tier gate, the row structure, the 44 px floors, the legend, the overview's shape, the seed filter and the bulk notes (all killed; two first passed for the wrong reason, a guard test that failed before the mutation and a count of the function's own definition, and were fixed). The back office, the employer home and the provider home were captured and read in Chromium at 375 px and 1280 px.
- **Not done and not claimed:** expert judgement with measurements, **not user research** (the five-person check, BL-16.4, is still the owner's); UI-25's type scale (it moves the phone's tokens); the demonstration database keeps the old descriptions until `make seed` is run; the Hindi labels (the nav, "More", the legend and the hints) were written by the engineer and need a native reader; nothing ran on a device.

## ADR-084: A Vacancy's Posted Date Is Stamped at Every Writer of "Published" and Never Invented, a Role You Confirm Is Saved Only by Your Own Act, and a Story Whose Data Does Not Exist Is Deferred With the Finding

**Status:** Accepted (October 2026). Sprint 74 (the first story of "candidate depth": the posted date Sprint 69 could not show, and BL-6.5). Extends ADR-049 (career ladders store nothing; this stores one fact, by the person's act), ADR-069 (list every writer of "published"), ADR-079 (a rule two clients need is written twice and run over one file) and ADR-082 (a new column on a person is in the notice, the export and the erasure). Migration 0057, additive response and request fields only; the released surface stays at 54 operations.

**Context:** Sprint 69 recorded that "posted n days ago" could not be shown because the public payload has no published date: `created_at` is the draft's, `updated_at` moves on every edit, and an invented date is worse than none. It is the one fact every job board shows and ours did not. Separately, the career ladder (ADR-049) forgot whose ladder it was: the role was held in React state (gone on reload) or guessed from the latest job title, so every visit asked again. A third backlog story, BL-12.8 (credit chips), was checked against the data before any code and **cannot be built**: `qualification_packs.credits` is well populated (4,301 of 4,424) but **no course links to a pack** (0 of 179; `Course.qualification_pack_code` is a free string that `CourseIn` cannot set and no seed sets), a credit is pack-level jargon the seeker's first screens may not use (ADR-080), and credits x 30 hours matches `total_hours` in only 83 packs, so deriving one would invent a number.

**Decision:**

- **`jobs.published_at`, nullable, not backfilled.** Every vacancy published before the column existed keeps NULL and the clients say nothing for NULL. A backfill from `created_at` would show a draft's date as a posting date.
- **One function keeps it true to `status`, and every writer of "published" calls it** (`takedown.stamp_publication`, beside `refuse_while_taken_down`, the ADR-069 convention). Going live from not-live stamps now; going not-live clears it; saving a live vacancy again leaves it alone. The callers are `publishing.set_published` (so `bulk.publish_many`, which only delegates) and `takedown.take_down`; `reopen_job` **deliberately does not call it**, because a closed vacancy was published all along and reopening is not a repost. The seeds are writers too (the model's default `status` is `published`, so a `Job(...)` built without one is live): the two demonstration seeds stamp a deterministic 0 to 21 days before the run (stable per slug, so a re-run does not move it; the database says it is `demo`), and the scale seed's raw INSERT does the same. A source test counts publications against stamps in each seed.
- **Decided, and said here: unpublishing clears the date and publishing again stamps a new one.** An employer can refresh a listing by unpublishing and republishing, at the price of the listing being invisible meanwhile; it is also what "posted" honestly means for a listing that was taken down and restored. This is stated, not prevented.
- **`postedAgo`: one rule, two clients, one file** (`tests/fixtures/posted_cases.json`, read by `web/src/lib/posted.test.ts` and `mobile/src/test/posted.test.ts`, with a Python test that fails when either stops, and one that holds the file to every answer and both boundaries). Whole **elapsed** days (floor of the hours, so it does not depend on a time zone): under a day, or a stamp in the future (clock skew), is "today"; 1 is "yesterday"; 2 to 29 is a number; **30 or more is "over a month ago" and never a precise old figure** (a vacancy that old is better read by its closing date). Nothing, or something unreadable, is nothing. Shown as a muted line on the card and the vacancy page (web and phone), never as a badge.
- **Courses get no date and there is no "newest first".** Neither was the story, a date invites the sort, and the default order is by title.
- **`candidate_profiles.current_role_slug`: the role you say you do now, saved only by your own act.** `PUT /me/profile` accepts it (an explicit `null` clears it; a section save that does not mention it leaves it, `exclude_unset`). It is checked on write against the taxonomy through `skills.roles_above` (a current role the ladder can start from; otherwise a 422 in words a form can show, before anything is written). **A slug and not a foreign key**, because the importer rewrites the taxonomy and a role that disappears falls back to the guess instead of breaking a profile. **The guess is never saved**; looking at the page stores nothing, however often. The ladder starts from an explicit `?role=` first, then the saved role, then the guess.
- **The new fact is a flag, not a fourth source.** `CareerLadderOut.anchor_confirmed` is added and **`anchor_source` stays `chosen | guessed | none`**, a saved role being `chosen`. The contract check only *reports* a widened response enum (it cannot know whether an installed app is exhaustive over it), so a test holds the set closed; the first mutation run found that no test did.
- **DPDP (ADR-082's rules).** The export carries it by schema; erasure deletes the row; the notice's "What we hold" gains "if you choose to save it, the role you say you do now" in English, Hindi and Malay, and `tests/test_notice_covers_inventory.py` is why (it fails until the column has a phrase). **The notice version is not bumped**: this is the same category as "the roles and places you prefer", set by the person's own act and read only by their own career page. Counsel may rule otherwise. Matching reads no role column and **no employer-facing payload can carry it** (`candidate_card` builds from an allow-list, ADR-037; a test holds the schema and the function).
- **The buttons.** Web and phone show "This is my role" with a line saying it is kept for next time and that employers never see it; a saved role shows "Saved as the role you do now." and "Forget it". A failure says what the server said, and the generic line only when it carried nothing (ADR, Sprint 17 lessons).
- **Housekeeping the research found.** `parse_credits` (and `parse_decimal`) let `Decimal("NaN")` through and Postgres stored it: five packs held NaN credits. Both now return unknown for a non-finite value. The five stay until the next `make import-nsqf`.
- **BL-12.8 is deferred, with the finding.** It needs a provider-side pack link first (`CourseIn`, a picker, validation), then the chip.

**Options considered:**

1. Backfill `published_at` from `created_at` and show the date for every vacancy
2. **A nullable column, stamped at every writer, NULL says nothing** (chosen)
3. Show "posted" from `updated_at`
4. Save the guessed role automatically once it has been shown a few times
5. **Save a role only when the person presses a button** (chosen)

**Trade-offs:**

- Option 1: ✅ every card has a date on day one ❌ it is a draft's date for rows that were published later, which is the invented date this ADR exists to refuse.
- Option 3: ✅ no migration ❌ an edit of the description would make a three-week-old vacancy "posted today".
- Option 4: ✅ nobody has to press anything ❌ a guess is a guess about a guess; the page would then start every later visit from a role the person never said, and the column would hold a claim they did not make.

**Consequences:**

- **Measured** with the review's capture script on a production build against the demonstration database (baseline `measurements.sprint73.json`, figures `measurements.sprint74.json`): `/jobs` **7.5 to 7.5 screens** (the line sits beside the experience), the vacancy page **2.7 to 2.8**, career paths **4.5 to 4.5**, small targets and text under 12 px **unchanged on every page**, no console error or failed request on any of 52 captures. **The matching benchmark** (`make benchmark`, interleaved with a clean worktree of `main`, one pair, the scale database migrated 0056 to 0057 first) is unchanged: the candidate side p95 195 ms on `main` against 187 ms on this branch, the employer shortlist 401 against 305 ms, recall 20 of 20 on both sides in both (the order of the runs and other work on the machine moved single numbers, so it is a "no regression", not an improvement). First-load JS: `/profile` is still the closest route (the career page is not on it).
- **Verified:** 1,936 backend, 739 web, 720 mobile and 136 browser tests (two new journeys: a vacancy published a moment ago says "Posted today" on its card and page; a role is confirmed, the page is reloaded, the role is still the anchor, and it is forgotten); `make evaluate` holds; `make check-contract` says 54 operations unchanged; **19 mutation checks** over every writer of the date (publish, unpublish, a live republish, reopen, takedown, the seed), both clients' boundaries and their reading of the fixture, the saved role losing to the guess, a guess being saved, an unknown role accepted, the confirmed flag, the notice phrase, the employer card, a widened `anchor_source`, both buttons and the NaN fix (all killed; one first survived and exposed that nothing held `anchor_source` closed, now tested). Migration 0057 round-trips on the development and the scale databases.
- **Not done and not claimed:** existing vacancies show **no** date until they are republished (and the demonstration database until `make seed`; the development database was dated by one SQL statement for the browser check); "posted" can be refreshed by republishing; the stored role is the person's claim and not a qualification; the Hindi lines (the posted line, the buttons, the notice sentence) were written by the engineer and need a native reader; nothing ran on a device; **credits are not built**.

## ADR-085: A Course Counts Toward a Qualification Because Its Provider Says So, and a Learner Is Told Whose Word It Is; a List Is Ordered by Something Unique

**Status:** Accepted (October 2026). Sprint 75 (BL-12.8, unblocked; and the newest-first sort Sprint 74's posted date made possible). Extends ADR-084 (a date read from a column that is NULL when nobody knows), ADR-064 (a bulk upload changes only the columns the file carries), ADR-080 (the seeker's first screens avoid the framework's vocabulary) and ADR-047 (a status the platform cannot verify is the provider's, and is labelled so). No migration, additive API only; the released surface stays at 54 operations.

**Context:** Sprint 74 deferred credit chips for want of data: **0 of 179 courses linked to a qualification pack**, because `Course.qualification_pack_code` was a free string nothing could write (it was in `CourseOut`, but not in `CourseIn`, `_PLAIN_FIELDS`, the bulk columns or any seed). Of the 4,424 packs, 4,296 have usable credits (five hold `NaN`, 18 hold 0, the median is 14); `total_hours` is set on 84, so hours can never stand in for credits. The story was therefore a provider feature first and a learner chip second. Separately, `GET /jobs` ordered by title alone, with no tie-break, and had no way to put the newest first now that a vacancy has a posted date.

**Decision:**

- **The provider links a course; the link is checked before anything changes.** `CourseIn.qualification_pack_code` (blank is none) is written by `create_course` and `update_course`, and `listings.require_current_pack` answers **422 in words** for a code that names no *current* pack, **before the first field is set** (the Sprint 55 rule; a mutation that moved it after the loop was caught only once a test called the service and then committed, which is what a bulk loop's next row does). `update_course` replaces every plain field, so an update that omits the field clears it; the web editor loads the saved value and sends it back, no released client calls a provider route, and a test pins the behaviour.
- **What the code stands for is read when it is shown and never stored.** `skills.packs_by_code` (one query per page; a later current version wins) feeds `marketplace.service.qualification_for`, attached with `model_copy(update=...)` on `GET /courses`, `GET /courses/{slug}`, `GET /skills/{slug}/courses` and the provider's own listing, the `seats_left_for` pattern. A re-import therefore cannot leave a stale name or figure, and a pack that has gone shows nothing rather than something wrong. The name is the pack's **`job_role`**, the seeker's word, never a code or "qualification pack". `usable_credits` shows a figure only when **finite and above zero**; it is held by a direct test because pydantic writes a `NaN` as `null`, so the API layer would hide a guard that had been removed.
- **It is the provider's statement, and the page says so.** The course page reads "Counts toward {name} · {n} credits" with "Stated by the provider. The credits are for the whole qualification, not only this course." beneath. A credit is the qualification's total, not what a short course earns, so the card carries only a small credit chip and **nothing sorts or filters by credits**. Nothing verifies the claim (as `enrolled` is self-reported, ADR-047).
- **One rule, two clients, one file.** `creditCount` runs on web (`lib/job-text.ts`) and phone (`core/labels.ts`) over `tests/fixtures/credit_cases.json`, held by the `readers` list in `tests/test_scannable_listing.py`; both guard what the server already nulls.
- **The editor.** `CourseEditor` gets an optional **Qualification** field: a search over `/roles/search` (the `["role-search", q]` key the career page shares; the candidate `RolePicker` is not reused because it adds skills as a side effect), each hit showing its sector and credits (`RoleHit.credits`, one extra query for the page, not a column in the ranking SQL), and "Remove qualification". A refusal shows the server's own sentence.
- **Bulk upload gets a `qualification` column, deliberately not `job_role`**: `job_role` expands into the course's standards, and a course that teaches part of a role must not claim the whole of it. **The update map had to learn the column in the same change**: `update_course` replaces every plain field, so a field missing from `_UPDATE_COLUMNS` is reset to nothing by every bulk update that never mentioned it (ADR-064: only the columns the file carries). A test per behaviour (kept when the column is absent, changed, cleared by a blank cell) and a structural test (every `_PLAIN_FIELDS` name is in the map) hold it.
- **Newest-first vacancies.** `GET /jobs?sort=title|newest` (default `title`; an unknown value is a 422; `JobSort` is a query parameter, so `tests/test_enumerations.py` excuses it from the closed-set-versus-CHECK guard by name). `newest` is `published_at DESC NULLS LAST, title, id`: **a vacancy published before 0057 sorts after every dated one, never by its draft's date**. `_paged` now takes a list of order terms that must **end in the id**: ordered by a title alone, two equal titles could swap between page one and page two (a latent defect, fixed for courses too). The web list gets a native select in the count row, drawn before the count arrives so the row has one shape (ADR-065); the phone is unchanged.
- **Demonstration data.** `seed_marketplace.COURSE_QUALIFICATIONS` links four seeded courses to the qualification role search itself would offer for an exact title (it **refuses a disability-track pack** and fails loudly on a title with none): the first run picked `PWD/RAS/Q0104` for "Retail Sales Associate", the only pack that title has, and a general course must not count toward it.

**Options considered:**

1. Show credits from the pack's own `total_hours` or derive them from a course's hours
2. **The provider links a course and says so; the learner is told it is their word** (chosen)
3. Verify the link with an operator queue
4. Store the pack's name and credits on the course when it is linked

**Trade-offs:**

- Option 1: ✅ no provider effort ❌ hours are set on 84 packs and credits times 30 matches in 83: it would invent a number.
- Option 3: ✅ a verified claim ❌ a back-office queue for something no learner is asked to rely on, and the learner is already told whose word it is.
- Option 4: ✅ one fewer lookup ❌ a re-import leaves a stale figure on a public page; the lookup is one query per page.

**Consequences:**

- **Measured** with the review's capture script on a production build against the demonstration database (baseline `measurements.sprint74.json`, figures `measurements.sprint75.json`): `/courses` **8.8 to 8.8 screens**, the course page **2.7 to 2.8** (a line and a note), `/jobs` **7.5 to 7.6** (the sort select shares the count row), small targets and text under 12 px **unchanged on every page**, no console error or failed request on 52 captures.
- **Verified:** 1,972 backend, 758 web, 734 mobile and 137 browser tests (a new journey: a provider finds a qualification in the editor, publishes, a visitor reads the course page and the credit chip, and the provider takes it back); `make evaluate` holds; `make check-contract` says 54 operations unchanged; **22 mutation checks** (all killed; two first survived and each exposed a real gap: nothing saw a validation that ran after the first write, and nothing held `usable_credits` directly). A first browser run found the new spec's assertion wrong, not the product: the fixture's General Duty Assistant has no credits (correctly no chip), and the journey now uses the role that has some.
- **Not done and not claimed:** the link is the provider's claim and is not verified; **no course shows a chip until a provider links one** (and the demonstration database until `make seed`; the development database was linked with one SQL statement for the browser check); credits are not searchable or filterable; the phone has the chip and the line but no editor; the five packs holding `NaN` credits stay until the next import (the reader hides them); the Hindi lines were written by the engineer and need a native reader; nothing ran on a device.

## ADR-086: The Look Is Chosen in One Place: Colour Ramps, a Named Type Scale and Shape Tokens in `globals.css`, Generated Into the Phone; a Ramp Step Is Never a Class, and Text Is Never Translucent

**Status:** Accepted (October 2026). Sprint 77 (Epic B19, BL-19.4, BL-19.5, BL-19.6). Extends ADR-065 (a page must not jump while it loads; the Hindi fold is a budget), ADR-077 (accessibility is held by the props that produce it) and ADR-079 (floors are asserted where they hold for every page); implements the direction the Product Owner signed off in `docs/design/design-brief.md` (Sprint 76). Frontend only: no migration, no API or contract change, the released surface stays at 54 operations.

**Context:** Sprint 68 found a product with one blue, no ramp, no named type scale (461 places used a 14 px secondary size, 238 a 12 px one) and no radius, shadow or motion tokens; the phone kept its own hand-written 13/16/18/24 scale that did not mirror the web. Nothing could be re-skinned without touching every call site, and `scripts/sync_mobile_tokens.py` treated every `--x:` in the first `:root` block as a colour, so a radius token would have been emitted to the phone as one.

**Decision:**

- **Two ramps, defined once.** `--brand-50` to `--brand-900` (700 is today's `#1f4e79`; the dark theme's primary is 400) and `--neutral-50` to `--neutral-950` (tinted to the brand hue), as variables in `globals.css`. The **semantic tokens** (background, surface, border, control edge, muted text, brand, the four tones) are re-pointed at steps in both themes. The page is `neutral-50` and a card is white, so a card is a surface instead of a border. **A ramp step is a variable only and never a Tailwind colour**: a class that named a step could not change in dark mode, and `tokens.test.ts` already forbids palette-family classes. Only the semantic tokens are utilities (`--surface-raised` and `--accent-tint` are the two added).
- **A named type scale on Tailwind's own steps.** Caption 13, small 15, body 16, lead 18, title 24, display 30 px, each with a line height, as `--type-*` and `--type-*-lh`. Tailwind's `text-xs/sm/base/lg/2xl/3xl` are mapped onto them in a plain `@theme` block (not `@theme inline`, which bakes values at build), so no call site changed and `html[lang="hi"]` can override the line heights with taller Devanagari values at runtime. **Secondary text rises from 14 to 15 px; 12 px stays the hard floor** (ADR-079). The phone's scale is generated from the same variables.
- **Shape and motion.** Radii 6, 10 and 16 px (`--r-sm/md/lg`; Tailwind's `rounded-md/lg/xl` now mean these, so the existing classes follow), a soft card shadow, 120 and 200 ms durations with one easing, and a `prefers-reduced-motion` rule that stops animation and transitions. Spacing stays on Tailwind's 4 px scale: a token for it would rename the scale without changing a value.
- **The token sync carries what is not a colour without calling it one.** A value is a colour only when it is a hex or rgb literal; `--r-*` becomes `radius` and `--type-*` becomes `type` on the phone (`mobile/src/theme/tokens.ts`, generated, and a test fails when it is stale). `mobile/src/theme/index.tsx` reads both, and the phone's secondary text is 15 as well.
- **Contrast is a test, not a review.** `tests/test_design_tokens.py` (93 tests) parses `globals.css` and checks every text-on-surface pairing the product uses, in light and dark, at 4.5:1 (text) or 3:1 (control edges, focus rings), that each semantic token resolves to a step on its ramp, that each ramp is monotonic, that the Tailwind mappings exist, that the phone receives the same values, and that the viewport colour, the manifest and the offline page agree with the page background. The helper handles an `@theme {` opener, because a first version skipped its own brace and found nothing.
- **Text is never translucent.** The first browser run failed four sweep tests, all `color-contrast 3.94` in dark: the call-to-action line was `text-brand-contrast/80`, an opacity over a lighter dark-theme brand blue (the rule "text must not use opacity to look secondary" was in `CLAUDE.md` and unenforced). It is now a guard (`TRANSLUCENT_TEXT` in `tokens.test.ts`, with a test that its detector can fail); the guard found a second, the footer's `text-foreground/80`, now `text-muted`.

**Options considered:**

1. Keep the single blue and restyle component by component
2. **Ramps and a type scale as variables, semantic tokens re-pointed, the old Tailwind names mapped onto them** (chosen)
3. Adopt a component library with its own theme
4. Make every ramp step a utility class

**Trade-offs:**

- Option 1: ✅ no global change ❌ the look stays 461 decisions; the next epic's components would each invent theirs.
- Option 3: ✅ finished components ❌ a second dark-mode mechanism, a second token set and bytes the first-load budget (`/profile`, about 3 KB of headroom) does not have; the Sprint 11 trial of one was reverted for exactly that.
- Option 4: ✅ more freedom ❌ a step used directly cannot flip with the theme, which is what the semantic layer is for.

**Consequences:**

- **A global visual shift, on purpose.** Every page changes at once: a grey page with white cards, a 15 px secondary size, rounder corners. Measured with the review's capture script on a production build against the demonstration database (baseline `measurements.sprint75.json`, figures `measurements.sprint77.json`, 52 captures, no console error or failed request): pages are about **4 percent longer on average** (up to 16 percent on the Hindi matches page, 11 percent on Hindi search), small tap targets across the 52 captures fell **121 to 92** (`/profile` 17 to 9, sign-up 8 to 4), and **no page has text under 12 px**. The first-load budget is unchanged and `/profile` is still the closest route.
- **Verified:** 2,065 backend (93 new), 760 web (two new), 734 mobile and 137 browser tests, `tsc`, `eslint`, `ruff`, `mypy`, the bundle ceilings and `make check-contract`; the Hindi fold test at 360 x 640 holds. **20 mutation checks** over the ramps, the dark and light muted text and button text, the control edge (both themes), the reduced-motion rule, the 12 px floor, the 15 px step, a Hindi line height, a missing Tailwind mapping, a ramp step offered to classes, the radii, the viewport and manifest and offline colours, the sync's colour rule, the phone ignoring the scale and translucent text returning: all killed (one first skipped because a value was repeated in both themes and was re-run against each).
- **Not done and not claimed:** no component uses the new surface, accent or radius levels yet (the next stories do); there is no icon set (BL-19.7), no theme control (BL-19.8) and no guard for the 44 px floor beyond the header and footer (BL-19.9); the colours were checked by arithmetic and by axe, **not by a person with low vision**, and the Hindi line heights were not read by a native reader; nothing ran on a device. The dark theme's brand is lighter than before by design (400, to hold contrast on a dark surface), so a dark screenshot of a button looks different from the light one.

## ADR-087: Icons Are Drawn Once and Imported One at a Time, the Revamp Is Held by Ratchets That Only Go Down, and a Person May Choose Light or Dark Without the First Load Paying for It

**Status:** Accepted (October 2026). Sprint 78 (Epic B19, BL-19.7 icon set, BL-19.9 guards for the revamp, BL-19.8 theme control). Extends ADR-086 (tokens), ADR-065 (a page must not jump while it loads), ADR-077 (accessibility is held by the props that produce it) and ADR-079 (floors are asserted where they hold for every page). Frontend only: no migration, no API or contract change, the released surface stays at 54 operations.

**Context:** After the tokens (ADR-086) the revamp had three gaps. The web app had five hand-drawn SVGs and the phone none, so a card could say nothing with a picture. The only touch-target check covered the header and footer, so a page could keep its small controls (92 across the 52 reviewed pages) and nothing noticed a new one; the phone's browser run measured nothing about layout shift (UI-21); and nothing stopped a migrated family from going back to a hand-chosen corner or size. And the product followed the device's light or dark setting with no way to override it (the owner kept the control in the epic).

**Decision:**

- **Thirty-four icons, drawn once, imported one at a time.** `web/src/components/ui/icons.tsx` holds `makeIcon("Name", [paths])` calls, each marked `/*#__PURE__*/`, on a 24 grid with a 2 px round stroke in `currentColor`: no package, no image request, no download. **Each icon is its own export so a route pays only for the icons it imports**; a table looked up by name would put every shape on every route. An icon beside its word is `aria-hidden`; one given a `title` is `role="img"` with that name. The phone's shapes (`mobile/src/ui/icon-shapes.ts`) are **generated from the web file** by `scripts/sync_mobile_tokens.py` (it matches only the pure-marked calls, so a doc comment's example is not an icon) and drawn with the `react-native-svg` the app already declared, so no native dependency is added. `tests/test_icon_shapes.py` holds the copy equal, every export pure, and every path something an SVG draws.
- **The shared header graph imports no icon.** Measured: swapping the header's and context switcher's inline marks for the module added **863 bytes to `/profile`**, which has about 3 KB of headroom (CLAUDE.md, "The header's import graph"): the factory is shared, so one icon in a component every route loads costs every route the factory and the icon. Both keep their inline marks and a test fails if `Header`, `ContextSwitcher`, `AuthNav`, `LocaleSwitcher`, `QueryProvider` or the footer's disclosure imports the module. The module is used by `JobCard`, `RoleChooser` and the lazy theme switch.
- **A ratchet for touch targets, not a wall.** `checkPage(..., { ratchet: true })` (every page in the sweep) counts the controls under 44 px **on the whole page** and compares them with `web/e2e/support/target-baseline.json`: **a page's count may only go down, and a page with no recorded count fails** until someone records one on purpose. A link inside a sentence is exempt (WCAG 2.5.8), as is a checkbox whose label is large enough. **The count is of kinds of control (tag and label), not rows**, because a first version counted five "Details" buttons on a list of five matches and failed when another journey published a sixth vacancy: the number of rows is the data's. Run ids in a page's slug are normalised. `scripts/merge_target_baseline.py` records (`TARGETS_LOG`), keeps the lower number for a known page and raises one only through a named `--allow-raise`. 128 pages are recorded, **82 distinct small controls in all**, 82 of the 128 pages at zero.
- **A migrated family may not go back** (`web/src/lib/token-adoption.test.ts`). A family listed in `MIGRATED` (today `components/ui`; each page-family story adds its own) may use a corner from the radius scale (`md`, `lg`, `xl`, `full`), text from the named steps, a shadow from the three elevations and **no pixel size in square brackets**. Comments are blanked first, the detector is proved able to fail on each rule, and an empty `MIGRATED` fails (the mutation run found it vacuously passing).
- **The phone's browser run scores layout shift** (`web/scripts/capture-app.mjs`, UI-21): the web sweep's session-window score for every screen, `CHECK=1` to fail above 0.1, `API=` to hold reads back 250 ms. **Its first run found a real defect: the signed-in home scores 0.137 to 0.217** because its personal block lands in four pieces above the search box. Two fixes were tried and reverted (a placeholder until all four reads answer, and mounting the block while the account loads): both made it worse (0.217), because a placeholder taller than the content shifts everything under it by the difference, and the content's height is the person's. A real fix is a design (the late block below what is on screen, or a card of known height), which is BL-19.22's. **The finding is recorded, not hidden**: `web/scripts/app-layout-shift-baseline.json` holds a ceiling of 0.25 for that screen, which may only go down, and every other screen is held to 0.1. `scripts/compare_captures.py` turns two runs of the review's capture into a before-and-after row per page family.
- **Light, dark or the device, on the web.** `lib/theme.ts` holds the choice in `localStorage` only (never the account: ADR-055), where "system" is no choice at all, so a person who never touches it gets exactly what they had. The override is `data-theme` on `<html>`; `globals.css` answers it with a second copy of the dark tokens and `color-scheme` (a test fails when the two copies differ, and the media query yields to a chosen light with `:root:not([data-theme="light"])`). **It must be on the page before the first paint**, so a short ES5 script built from the same constants runs in `<head>` before the body is parsed (the CSP allows inline script) and again when the document is parsed, for the address-bar tags Next writes; `<html>` carries `suppressHydrationWarning` for the attribute. `THEME_COLOURS` is the one place the address-bar colours are written and a test holds them equal to the page background in each theme. A test found that `getItem` can throw as well as `localStorage` access, and `getTheme` survived neither: it is fixed and held.
- **The switch is a closed disclosure in the footer whose code is fetched on first open.** Putting three buttons, three icons and the theme module in the footer cost `/profile` 2,460 bytes; a `<details>` whose **summary is passed from the server footer as children** (so its markup is not client JavaScript) and whose switch is a plain dynamic `import()` (not `next/dynamic`, whose loader costs more than it loads) costs **410 bytes**: `/profile` is 697,173 bytes against 696,763 before, headroom 3,237 to 2,827. **That is growth, and it is stated**: the footer is in every first load and a disclosure is not free. A source test fails if the footer imports the switch statically. The chosen theme itself never waits for the chunk.
- **Light, dark or the phone, on the phone.** `core/theme-preference.ts` is the course budget's store shape (ADR-078): held on the device, never on the profile, **forgotten when a signed-in session ends** (`forgetPersistedCache`), "system" the default. It lives in `theme/` and takes its storage by `attach`, so `useColours` reads it without importing the runtime, which every screen test replaces by hand. The choice wins over the phone's own setting; `Appearance.setColorScheme` is also called where the platform has it (the browser build does not), so what the system draws follows. Three 48 dp chips on the Me tab, outside the sign-in gate (it asks the server nothing and a visitor may prefer the dark).

**Options considered:**

1. An icon package (and a font or sprite on the phone)
2. **One module of inline strokes, imported per icon, shapes generated for the phone** (chosen)
3. A hard wall for small controls (fail any page with one)
4. **A ratchet recorded per page** (chosen)
5. The theme switch in the first load, or in the header

**Trade-offs:**

- Option 1: ✅ a ready set ❌ a dependency and bytes the budget does not have; a native package for the phone.
- Option 3: ✅ simple ❌ 46 of 128 pages would fail today, so it would be switched off the first week; a ratchet makes progress the only direction.
- Option 5: ✅ always visible ❌ 2,460 bytes on the page with 3 KB of headroom, or a header control every route pays for.

**Consequences:**

- **Verified:** see the sprint record for the counts; the browser suite runs the new theme journey (a choice against the device, kept across a reload with the attribute on `<html>` before `<body>` exists, the address-bar tag following, the device handed back) and the ratchet on all 128 sweep pages in both languages and on a phone; the phone's browser run was executed against the real API in both light and dark. **29 mutation checks** over the icon set, the generated copy, the dark copy, the layout script, the baseline merge, the family map, the adoption rules, the theme store, the disclosure's import, the header graph, the phone store, sign-out forgetting and the icon's hiding from a screen reader: all killed after three first survived and each exposed a real gap (an empty migrated list passed vacuously; an untitled phone icon's role was not asserted by its props; one mutant had a wrong target and was re-run).
- **Not done and not claimed:** no card or page uses the icons yet (BL-19.11 and the family stories), the phone's tab bar has none (BL-19.21); **the installed app's splash colour is the manifest's and cannot follow a chosen theme**; going back to "device" restores the address-bar colour on the next load, not live; the web control is in the footer only (BL-19.13 puts language and theme together); the phone's signed-in home still jumps (open, recorded, BL-19.22); the small-control counts are recorded, not zero (82 kinds remain, `/profile` 7); the Hindi and Malay labels ("दिखावट", "Rupa", and the rest) were written by the engineer and need a native reader; nothing ran on a device, and TalkBack, VoiceOver and a real dark phone are not checked.

## ADR-088: A Form Field Says What Is Wrong Next to Itself, in the Page's Words or the Server's; the Library's Controls Are the Old Helpers Under the Same Names, and What a Form Does Not Need at First Paint Is Fetched When It Is Opened

**Status:** Accepted (October 2026). Sprint 79 (Epic B19, BL-19.10, first half: the library, the validation and the four forms that matter most; the other raw controls move in the page-family stories). Extends ADR-086 (tokens), ADR-087 (ratchets, the header graph and the first-load budget) and the Sprint 29 and 30 conventions that a form mirrors the server's limits and never throws away what the server said. Frontend only: no migration, no API or contract change (54 operations).

**Context:** `components/profile/fields.tsx` had been the product's form library for a long time without being one: 25 files used its `Field`, `Text`, `Area`, `Select` and `Check`, but a field had **no place for what was wrong**, no `aria-invalid`, no `aria-describedby` anywhere in the app, a label that wrapped the control and the hint (so the hint was part of the control's name), controls a pixel or two under 44, and 66 places built an `ApiError` from `readDetail(body)`, which folds a 422's list of `{loc, msg}` into one sentence for an alert at the top and **throws the field away**. A person who left a title two characters long learned of it from the server, in a banner, naming a database column.

**Decision:**

- **One library, `components/ui/field.tsx`, and the old names stay.** `Field` (label, hint, problem), `Input`, `Textarea`, `Select` and `Checkbox`; `components/profile/fields.tsx` re-exports them as `Field`, `Text`, `Area`, `Select`, `Check`, so the 25 forms that use them changed none of their markup and the limits (`minLength={3}`) stay literal at each control where `constraints.test.ts` reads them. `Field` provides a context; the control reads from it the id the label's `htmlFor` points at, `aria-describedby` (the hint, and the problem while there is one) and `aria-invalid`. The label is now a sibling, not a wrapper, so **a control's name is its label and nothing else**. Every control is `min-h-11`; a checkbox's whole label is the 44 px target (WCAG 2.5.8 measures what a finger lands on). It is not in the `ui` barrel (Dialog's reason: the barrel is imported for a Button). `components/ui/` is held to the token scales, so the library itself was checked by `token-adoption.test.ts` on its first day (it found a bare `rounded`).
- **A problem has three sources and shows the first that exists:** the `error` a form passes, **what the server said about this field**, and what the browser's own constraints say **when the person leaves the field**. The browser's check is read, but the words are ours: `form.*` messages in English, Hindi and Malay ("Use at least 3 characters.", with the number), because the browser's wording follows the browser's language and not the page's. `tooShort` and `tooLong` are our own checks, since `validity.tooShort` is only ever true after a person has typed, so a value restored or scripted would pass the browser and fail the server. A field is **not nagged while typing**, only after it has complained once; a problem goes as soon as the value is fixed, and a server message goes when the person edits that field. **Submitting still uses the browser's validation** (no `noValidate`), so nothing here can let a bad value through.
- **The server's words reach their field.** `ApiError` gained `fields` (`{title: "String should have at least 3 characters"}`), read by `readFieldErrors` from the same `{loc, msg}` list as the sentence (the last string in `loc` is the field; a field named twice keeps its first message; a message with no field, as a model-wide validator's, stays in the sentence only). **All 64 places that built an `ApiError` by hand now go through `apiErrorFrom(status, body)`**, and `http.test.ts` fails on a new `new ApiError(..., readDetail(...))` anywhere, because one hand-built error would silently drop the parts. `FormErrors` provides `error.fields` to the fields below it; a `Field` finds its message by the **control's own `name`** (every form here reads its values from `FormData` under the schema's names), so a form passes the error once and writes nothing per field. Wired in the vacancy editor, the course editor, the organisation settings and the profile's details form; the alert at the top still says the whole sentence.
- **What a form does not need at first paint is fetched when it is opened.** The first version of the library cost `/profile`, the route nearest the 700,000-byte ceiling, **2,104 bytes** (699,277, headroom 723). Two cuts, each by the pattern ADR-083 and ADR-087 use: `validate.ts` (the checks) is a dynamic `import()` fetched the first time a field is left (-391 B), and the four repeating sections' **fields** (`section-forms.tsx`, 42 `Field`s) are fetched the first time a section's form is opened, behind `LazyForm`, which holds the height of one field until they arrive (the person pressed "Add", so nothing on the page moves). **`/profile` is now 694,556 bytes, 2,617 under where it started the sprint (697,173), headroom 5,444**; the closest route is `/employer/[org]` at 694,839 (5,161). Source tests fail if the editor imports the forms statically, or anything else in the profile does.
- **A test of a limit looks at its own element.** `constraints.test.ts` took the next 200 or 400 characters after a field, so one field's `maxLength={160}` satisfied its neighbour's (`qualification` and `institution`): a mutation check removed one and nothing failed. The window now ends at the element's `/>`; every limit still passes, which says they were all there and nothing was proving it.

**Options considered:**

1. A form library (react-hook-form, a schema resolver)
2. **A small context-wired field over the browser's own constraints, with the server's per-field parts** (chosen)
3. Validate on every keystroke
4. Put the field-set code on the first load and accept the bytes

**Trade-offs:**

- Option 1: ✅ a ready-made validation model ❌ a dependency and its bytes on the one route with 5 KB to spare, and a second source of limits beside the server's and the literal attributes the constraint test already holds.
- Option 3: ✅ immediate ❌ it tells a person who has typed one letter that the title is too short; the rule here is "after you leave it, and gone as soon as fixed".
- Option 4: ✅ simpler ❌ `/profile` at 723 bytes of headroom, so the next story that touches the shared graph breaches it.

**Consequences:**

- **Verified:** see the sprint record for the counts; a new browser journey (`forms.spec.ts`: a title left at two characters says so beside the field and the control is described by it; fixing it clears it; a refusal by the server, with the browser's validation switched off for the test, lands in the server's words beside the field and in the summary, and editing the field dismisses the former) and the whole sweep, including the ratchet (`/profile` small controls 7 to 2 and the team page 1 to 0, because a checkbox's label is now the target, recorded). **23 mutation checks** on the library, the checks, the field-error reader, the guards and the profile split: all killed after four first survived (the "not nagged" test asserted before the lazily loaded check could answer; nothing tested finding a field by the control's name; the constraint window; nothing guarded the lazy import).
- **Not done and not claimed:** **42 raw `<input>`, `<select>` and `<textarea>` remain in 23 files** (the sign-in, sign-up and message forms, the filter bars, the pickers, the back-office queues), to move in BL-19.13 to BL-19.19; a refusal by a model-wide validator (a salary maximum below the minimum) names no field and stays in the summary only; focus does not move to the first problem after a failed save; the phone's `TextField` is BL-19.14; the Hindi and Malay messages (`form.*`) were written by the engineer and need a native reader; the first time a profile form is opened a chunk is fetched (a few kilobytes, one field's height held), which on a slow connection is a short wait the sweep cannot see; nothing ran on a device.

## ADR-089: A Card Has a Level, a Status Has a Shape, an Empty List Has an Icon and a Slot for Art, and a Gallery Shows Them All in a Build That Is Never Shipped

**Status:** Accepted (October 2026). Sprint 80 (Epic B19, BL-19.11 surfaces and actions, BL-19.12 empty, loading and status states). Extends ADR-086 (tokens), ADR-087 (the icon set, the header graph and the first-load budget) and ADR-088 (the form library). Frontend only: no migration, no API or contract change (54 operations).

**Context:** After the tokens and the form controls the shared surfaces were still the Sprint 11 ones: a `Card` that was a border and nothing else, one badge size, an `Alert` whose four tones differed only by colour, buttons with no pressed or busy state, and an empty list that was a muted paragraph (ten of them, each its own class string). Nothing showed every variant together, so a variant could be unreadable in one theme and nobody would look.

**Decision:**

- **A card has a level.** `Card level="default | raised | inset | interactive"`: the default is what it always was plus the soft shadow (the page is grey and a card is white, ADR-086), `raised` is the floating surface (a menu, a dialog's panel), **`inset` is a box inside a card** (the muted surface, no shadow: a bordered, shadowed card in a card was how a form held a sub-panel), and `interactive` lifts on hover and takes the brand edge, for a card that is a link. No call site changed: the default is the old card. `Badge` gained `size` (`sm`, the 12 px floor and what cards carry, and `md`) and an `info` tone; `Button` a `soft` variant, a pressed state, and **`loading`**, which disables it, sets `aria-busy` and draws a ring that is hidden from a screen reader (the button already says it is busy); `buttonVariants` stays server-safe.
- **A status has a shape as well as a colour.** `Alert` draws a tone's icon in the margin (`absolute`, with the left padding to match), so the children's own layout (`space-y-2`, paragraphs) is untouched; `icon={false}` opts out. **The four shapes are written inside `alert.tsx`, not imported from the icon module**, and `tests/test_icon_shapes.py` holds them equal to the set's `XCircle`, `AlertTriangle`, `CheckCircle` and `Info` (two icons, `Inbox` and `XCircle`, joined the set: 36). The status pattern is `Alert` with `role="status"` for an inline confirmation: **no floating toast**, because a provider mounted in the layout would be on every route's first load, and a message that appears over the page is the layout shift and the covered control the design brief forbids.
- **An empty list says what is missing under an icon, and art is a drop-in.** `EmptyState` (title, optional why, optional action, `icon`, and `illustration` which **replaces the icon**; the CSP blocks remote images, so art is a local file): a paragraph, not a heading (it sits under the page's own), plain markup with no hooks so a server component can render it. Ten page-level empty lists use it (vacancies, courses, standards, notifications, course interests, applications, saved, both inboxes, both back-office queues), each keeping its sentence and its call to action. `Spinner` is a ring in the text colour: with a `label` a status, without one decoration, and only `placeholder` marks it `data-loading`, which hides the footer (ADR-065).
- **A gallery shows every variant, in a build that is never shipped.** `/gallery` renders every level, size, tone, state and field in the page's language; the theme and language controls show it in both. It **404s unless `NODE_ENV` is not production or `NEXT_PUBLIC_UI_GALLERY=1`, which only `build:e2e` sets** (tests fail if another script sets it or the guard is removed), so the browser sweep visits it in both languages and on a phone: axe checks every variant's contrast in **light and dark**, the layout-shift check runs, and its count of small controls is recorded at zero. A variant that stops being readable in either theme now fails the build, which is most of what a gallery is for. It carries its own `gallery.*` messages (en, hi, ms).
- **The budget, again.** The first version spent 4,124 bytes of `/profile`'s headroom (698,680; 1,320 left): the design-system barrel `ui/index.ts` had been given `EmptyState` and `Spinner`, and **a barrel puts what it names on the first load of every route that imports it for a Button** (the reason `Dialog` is not in it); they are out of it again, with a test. The `Alert` icons then cost the icon factory and four exports (about 1.3 KB), so they are drawn inline (about 0.7 KB), and `Button`'s ring is its own span, not `Spinner`. **`/profile` is 696,215 (1,659 above where the sprint began, headroom 3,785), `/employer/[org]` 696,546 (3,454)**: this sprint spent part of what Sprint 79 recovered, and says so.

**Options considered:**

1. A toast provider in the layout
2. **Inline status (`Alert role="status"`) and no floating message** (chosen)
3. Import the icons into `Alert` and accept the bytes
4. **Draw the four shapes in `Alert`, held equal to the set's by a test** (chosen)
5. A Storybook, or a gallery in production

**Trade-offs:**

- Option 1: ✅ a familiar pattern ❌ bytes on every route and a message that moves or covers.
- Option 3: ✅ one drawing ❌ about 600 B more on the route with the least headroom, for four shapes; the copy is test-held.
- Option 5: ✅ richer tooling ❌ a dependency and a build for an internal page; a gallery in production is a page nobody should find.

**Consequences:**

- **Verified:** see the sprint record for the counts; the browser sweep includes `/gallery` (en, hi and a phone) with contrast in both themes and no layout shift, and the ten empty lists are covered by the existing journeys (their sentences are unchanged). **25 mutation checks** over the card levels, badge sizes, the button's loading and `asChild`, the alert's icon, shapes and layout, the spinner's announcing, the empty state's art, title, heading and hiding, the barrel, the gallery's gate and flag, and a list going back to a paragraph: all killed after one first survived (a test that looked for any hidden element, and found the icon's own).
- **Not done and not claimed:** **no illustration exists** (the art is the Product Owner's; the slot is built and tested); the cards the product shows (job, course, match, application) have not moved onto the levels (BL-19.15 to BL-19.17), so the new shadow is visible only on what already used `Card`; error states in the lists (`loadError`, `errorGeneric`) are still paragraphs; the smaller inline empties (a card with no courses, a panel with no rows) stay text; the loading placeholders are unchanged (`ListSkeleton`'s 144 px rows) because no card has changed height yet, to be re-matched when the card story changes them; the Hindi and Malay gallery text is the engineer's; nothing ran on a device.

## ADR-090: A Job Seeker's Pages Are One Tap Away, the Bottom Bar Is a Chunk Whose Room Is Made Before It Arrives, and the Header Says Where You Are

**Status:** Accepted (October 2026). Sprint 81 (Epic B19, BL-19.13). Extends ADR-065 (a page must not jump while it loads), ADR-086 and ADR-087 (tokens, the header graph and the first-load budget) and ADR-089 (the surfaces and the barrel). Frontend only: no migration, no API or contract change (54 operations).

**Context:** The header was a row of links with no sign of which page the person was on; sign-in and sign-up carried the whole header (a menu, the account controls) over a form that needed neither; the mobile menu could only be closed by its own button, and on a short phone with a long account list it ran off the screen. Four of a job seeker's own pages (applications, notices, account, career paths) were reachable only through the account menu, and **saved jobs through nothing at all**. The phone app has a bottom tab bar; the same person on the phone's browser had none. The owner chose its four (Jobs, Courses, Matches, Profile, BL-19.2) and kept the language control where it is.

**Decision:**

- **The page you are on is marked.** `currentHref` (`lib/nav.ts`, pure) picks the **longest** link that is the path or a parent of it: `/employer/acme/jobs/x/applications` is the vacancies page's and `/employer/acme/team` is the team's, never both. The desktop and mobile nav links are `aria-current="page"` and drawn filled, so it is not told by colour alone. A link to a place in a page (`/#how-it-works`) can never be current, because a pathname has no hash (a guard that said so was dead code, found by a mutation check, and removed).
- **Signing in or up has a reduced header**: the logo to go back and the language, and no menu, nav or account controls (`isReducedHeader`: `/signin`, `/signup/*`, `/employers/signin`). It is the same header element with parts left out, not a second one (a second copy cost bytes on every route). The mobile menu closes on Escape and on a tap outside (`useDismiss`, the hook the account menus use) and **scrolls inside the screen** (`max-h-[calc(100dvh-4rem)]`), so a long list of organisations can no longer push its own close button away.
- **A job seeker's pages are in a row at the top of each of them** (`CandidateNav`): matches, applications, saved jobs, updates (the unread count drawn in the corner of its tab, out of the flow, and spoken once in words), profile, the courses asked about, career paths, the account. It scrolls sideways on a phone so Hindi labels do not wrap. The strip is a **separate chunk fetched after paint** (`CandidateStrip`); what renders at once is its **place**, a row of its own height, whoever is looking, so it arriving moves nothing. `/profile` is one of its eight routes and has the least headroom in the product.
- **The bottom bar is a chunk, and its room is made before it arrives.** `MobileTabBar` (Jobs, Courses, Matches, Profile; `fixed`, `lg:hidden`, each tab 64 px, the current one filled and `aria-current`) is brought in by `SeekerTabs` only for a signed-in account that holds a job-seeker profile, off an organisation's workspace, the back office and the sign-in pages. It is fixed, so it moves nothing; **but a page that made room for it only when it arrived would jump on a short page** (the footer rises by the bar's height). So a short script in `<head>` (`lib/auth-hint.ts`, beside the theme script) sets `data-auth` on `<html>` before the first paint when this browser holds a sign-in and the path is not one of those pages, and `globals.css` turns that into `--tabbar` (4 rem plus the safe-area inset, below the laptop width only) as the body's bottom padding. **Everything anchored to the bottom of the screen reads the same variable**: the vacancy page's apply bar (`bottom-[var(--tabbar)]`, found by the browser journey: the first design would have put the tab bar over the one button the page exists for) and the consent banner. The hint is a guess and never a sign-in: `SeekerTabs` removes it when the account turns out to need no bar (an organisation-only account, a client-side move into a workspace, an expired sign-in whose account query is off and reads as pending, held by a test). The key the script reads lives in `lib/storage-keys.ts`, because a constant imported into a server component from the `"use client"` auth module is a client reference, not a string.

**Options considered:**

1. A static header nav only, with the strip's pages in the account menu
2. **A strip of the person's pages at the top of each, and the bar on phones** (chosen)
3. The bar in the header graph, with body padding set when it mounts
4. **A lazy bar with room from a pre-paint hint** (chosen)
5. Show the bar to every signed-in account, with organisation tabs

**Trade-offs:**

- Option 1: ✅ nothing to build ❌ saved jobs stay unreachable and the account menu stays the only door.
- Option 3: ✅ simple ❌ about 2 KB on the route with the least headroom, and a footer that jumps on short pages.
- Option 5: ✅ consistent ❌ a second design (an organisation's tabs) that nobody asked for; an organisation-only account gets no bar and, until `SeekerTabs` corrects it, no room.

**Consequences:**

- **Budget:** the shared graph (the header's marking and reduced mode, `SeekerTabs`, `nav.ts`, the strip's stub) cost **`/profile` 1,751 bytes and `/employer/[org]` 1,346**: `/profile` is 697,966 (headroom 2,034), `/employer/[org]` 697,892 (2,108). The first version cost 3.5 KB because the strip was in the first load of its eight routes; making it a fetched chunk with a held place recovered 1.7 KB. **That is where the revamp's room now stands: about 2 KB, and the next story that touches the header, the footer or the `ui` barrel has to come out of it or make a chunk.**
- **Verified:** see the sprint record for the counts; two new browser journeys (a seeker on a 360 px phone: the bar, the current tab, its room, its place at the bottom edge, every page of theirs by the strip with no menu, the strip's current page, the bar gone and the room gone at laptop width; and the apply bar ending where the tab bar begins on a short phone, no bar and no room in an organisation's workspace, and the reduced header on sign-in) and the whole sweep, whose layout-shift and contrast checks ran with the strip and the bar on the seeker's pages. **25 mutation checks** over the nav rules, the hint script, the header's marking, reduced mode, Escape and scrolling, the bar's visibility, fixing, size and marking, who gets it, the room's correction, the strip's lazy import, held place and out-of-flow count, saved jobs in the strip, the banner's offset and the icon: all killed after two first survived (a dead guard, removed; a signed-out visitor whose off query reads as pending, now tested).
- **Not done and not claimed:** an organisation's workspace has no tab bar (its header nav is what it had); **an organisation-only account on a phone keeps the bar's room from the first paint until the account loads** (the correction moves the footer once on a page shorter than the screen; the sweep passed it); the language control and the theme control are still where they were (BL-19.13 no longer moves the language, and putting them together is not done); the strip is signed-in content shown to a signed-out visitor on those pages, as a row of links to pages that show a sign-in prompt; the Hindi and Malay labels ("मैच", "प्रोफ़ाइल", "आपके पन्ने") were written by the engineer and need a native reader; nothing ran on a device, and the bar's safe-area padding is untested on a real notch.


## ADR-091: The Phone Gets the Web's Vocabulary, a Bar With Icons, and a Me Tab That Reads as Places

**Status:** Accepted (October 2026). Sprint 82 (Epic B19, BL-19.14, BL-19.21, BL-19.22). Extends ADR-072 (the phone is a second client of the same API), ADR-077 (accessibility is held by the props that produce it) and ADR-087 and ADR-089 (the icons, the tones and the surface levels it mirrors). Phone only and frontend only: no migration, no API or contract change (54 operations).

**Context:** The web had five button variants, four notice tones with an icon each, six badge tones and two surface levels; the phone had two button variants, a notice with no success tone, a badge with no danger tone, one kind of card, and a bottom bar of five words with the icons hidden on purpose ("a label that is always readable is better than an icon that has to be learned"). The Me tab, where a signed-in person's own things are, was a card and **seven identical outline buttons**. The icon component (Sprint 78) had never been drawn by any screen.

**Decision:**

- **One vocabulary on both clients.** `Button` has `primary`, `secondary`, `ghost`, `danger` and `soft`, each one row of tokens (background, edge, words) in one table, not five branches. `Notice` has `info`, `success`, `warning` and `danger`, each drawn with its **shape** (info, check, triangle, cross) so a tone is never colour alone; only a `danger` notice is announced (`accessibilityRole="alert"`). `Badge` gains `danger` and `info`; `Card` gains `level="inset"` (the muted surface for a box inside a card, no second edge: never a card in a card).
- **A place is a row.** `ListRow` is an icon in a tinted disc, a title, an optional line under it, an optional count in a pill and a chevron: at least 56 dp (above the 48 dp floor, since a row is what a thumb scans), a button whose **name is the title** unless a longer one is given (it must contain the title: "Updates: 3 new updates"), the icon and the pill hidden from a screen reader because the name already says them. `RowGroup` puts rows in one rounded box with a hairline between them (a divider above every row but the first, set by the group, not by each caller).
- **The bar has icons and its words.** Each tab has its own icon (Home, Briefcase, BookOpen, Target, User) in the tab's tint **beside the label, which is kept**. The unread count is a **badge on the Me icon** (capped "99+"), and the tab's spoken name still carries the exact number ("Me, 150 unread"); the label is the plain word again, so the number is drawn once. The bar is **64 dp plus the bottom inset**, because an icon over a 14-point word did not fit the navigator's 49 dp default (the labels were cut off in the first browser run).
- **Me is two groups.** What the person did (updates with their count, applications, saved jobs, courses asked about, career paths), then the account and contact. The profile summary card stays above them. Every earlier button name and path still works (`me.test.tsx` names them all).
- **An icon's accessibility props live on a `View`, not on the `Svg`.** In react-native-web the Svg hands every prop to a DOM element, so `accessible` and `importantForAccessibility` were logged by React as errors and the development overlay covered every screen: **found only by running the screens in a browser**, the first time any screen drew an icon. A test holds the Svg free of them.

**Options considered:**

1. Keep the phone's two button variants and style the Me tab with more cards
2. **Mirror the web's variants from the same tokens, and give the bar and Me their own icons** (chosen)
3. A drawn tab badge only, dropping the number from the spoken name
4. **A badge plus the spoken number** (chosen)
5. Hand-written icons for the phone

**Trade-offs:**

- Option 1: ✅ nothing to build ❌ a danger action (delete, withdraw) has no look, and Me stays eight equal things.
- Option 3: ✅ simpler ❌ a screen reader would read "Me" and skip the number a sighted person sees.
- Option 5: ✅ none needed ❌ a second set of shapes that would drift from the web's; the generated one is already guarded by `tests/test_icon_shapes.py`.

**Consequences:**

- **Size:** the Android Hermes bundle went **3,538,200 to 3,726,798 bytes** (ceiling 3,800,000, **73,202 left**) because the tab bar is the first thing to import `react-native-svg`, which the app has declared since Sprint 78. That is the whole cost of drawing icons on the phone; the next story that adds a package has to come out of it.
- **Verified:** strict `tsc`, `eslint`, **786 Jest tests** (26 new for the primitives and rows, 2 for the icon and the bar, the tab and Me tests changed to the badge and the rows), the phone guards, both bundles, and **the real screens run in a browser** (the bar with its five icons and a badge of 3 on Me; the Updates row with its pill; the dark theme; the layout-shift run: every screen 0.000 except the signed-in home at 0.169, still its known open finding, ceiling 0.25). **14 mutation checks** over the row's floor, divider, count cap and zero, the row's spoken name, the card level, the alert role, the danger and soft looks, the Svg's props, the badge and its cap, the bar's height and an icon in the map: all killed after one first survived (the card-level test compared styles that differ in radius as well).
- **Not done and not claimed:** BL-19.23 (the profile as sections), the signed-in home's layout jump (BL-19.22's second half: the home is not rebuilt on rows), cards and job/course cards on the new tokens beyond what already used them, and the screens' own use of `ghost`, `danger` and `soft` (the primitives exist and are tested; no screen asks for a danger button yet). The Hindi and Malay are unchanged (no new string). **Nothing ran on a device**: TalkBack and VoiceOver reading of the badge and the rows, the bar's height on a real notch and at 200% text are the checklist in `mobile/ACCESSIBILITY.md`.


## ADR-092: The Phone's Profile Is a Stack of Sections, and a Home That Arrives in Pieces Waits and Arrives Once

**Status:** Accepted (October 2026). Sprint 83 (Epic B19, BL-19.23 and the second half of BL-19.22). Extends ADR-065 (a page must not jump while it loads), ADR-078 (the profile's forms are one table compared with the server) and ADR-091 (the phone's vocabulary). Phone only and frontend only: no migration, no API or contract change (54 operations).

**Context:** The phone's profile was one long screen: a sentence about completeness, the skills, six buttons for the history sections, then two forms ending in a "Save" each, with nothing to say which of the two a screen reader was on. The signed-in home read four queries (matches, profile, applications, unread count) and drew each block as it landed above the search box, so the box was pushed four times: the phone's browser run scored it 0.17 to 0.22 and it had been the one screen allowed above 0.1 (a recorded ceiling of 0.25) since Sprint 78. Two placeholder-height fixes tried then made it worse.

**Decision:**

- **The profile is a progress header and four sections.** The header is a progress bar (`ProgressBar`: a progressbar role with its value, clamped to 0 to 100, a number that is not one is drawn as 0) beside the sentence that says the same number. Then, in the order a person fills them in: **My skills** (the role picker and what is held), **About you**, **Your history** (the six sections as `ListRow`s, each with its count in the subtitle and the same spoken name as before), and **What you are looking for**. A form section is a `Panel` (an icon, a heading a screen reader reaches as a heading, its own surface) with **its own Save, named for the section** ("Save: About you"), and its own confirmation (a success notice, in that section). Date of birth and gender stay web-only. `test_mobile_section_limits.py` is untouched and green: no limit moved.
- **No card in a card.** A role the picker finds is an `inset` card inside the skills panel; the history rows are one group, not a card each.
- **The loading screen is the shape of what arrives**: a header-sized block and three section-sized ones (`SkeletonRows` takes a `height`), so a profile that loads moves nothing.
- **A block made of several queries waits for all of them and arrives once.** `SignedInHome` shows one placeholder until matches, profile, applications and the unread count have each answered (an answer that is an error counts: a failed part must not hold the rest back for ever), then draws one block. The placeholder and the block share one height (`HOME_PLACE`, 330 dp, **measured** on the seeded demonstration account whose natural height is 336), and the block is never shorter than it, so the usual account moves nothing and an unusually short one moves things once, not four times. The profile's next step, the updates and the applications with news are **rows in one group**, in that order, the updates with their count in a pill and in the spoken name.
- **The job card is on the scale.** Its place line was the one hand-written `fontSize: 13` in the phone's list code; the employer and the place are now `Text` steps with an icon each (Building, MapPin), the icon decorative beside its words.
- **The ceiling file is empty.** `web/scripts/app-layout-shift-baseline.json` held one entry, the home. It is `{}` now, so every phone screen is held to 0.1, and the capture script's own comment says so.

**Options considered:**

1. Keep one long profile screen and rename the Saves
2. **Sections as panels, each with its own Save** (chosen)
3. A tabbed profile (one section on screen at a time)
4. Fix the home's jump with a taller placeholder per part
5. **Hold one placeholder and draw one block, at a measured height** (chosen)
6. Move the personal block below the search so nothing it does can push it

**Trade-offs:**

- Option 1: ✅ nothing to build ❌ two "Save"s that cannot be told apart, and no sense of where in the profile you are.
- Option 3: ✅ shortest screens ❌ hides what is incomplete, and a half-typed section is lost on a tab change.
- Option 4: ✅ small ❌ tried in Sprint 78 and made it worse: a placeholder taller than the content shifts what is under it, and four parts arrive at four moments.
- Option 6: ✅ nothing above moves ❌ the person's own best match stops being the first thing they see (ADR-080).

**Consequences:**

- **The cost of waiting**: the home shows nothing of the person's until the slowest of four reads has answered. Each is a read the app already makes and none is slow, but a slow unread count now delays the best match. A block per part with its own reserved height would avoid that and was not built.
- **The held height is an account's, not a constant of nature**: 330 against 336 natural on the demonstration account; a person with a longer match sentence or with updates and news (56 dp a row) gets a taller block and one shift, not four.
- **Size:** the Android bundle went 3,726,798 to 3,729,584 bytes (ceiling 3,800,000, **70,416 left**).
- **Verified:** strict `tsc`, `eslint`, **814 Jest tests** (28 new across the primitives, the profile and the home; the profile and home tests changed to the sections, the rows and the one Save names), the phone guards, both bundles, and the real screens in a browser: the **signed-in home 0.169 to 0.002**, every other screen 0.000 except the signed-out home at 0.010, the profile read in full at a tall viewport (header, four sections, the history rows with their icons, two Saves). **20 mutation checks** over the bar's clamp, not-a-number, fill and role, the heading role, the placeholder's default and given height, the home waiting for all four, a failed part, the held height and the placeholder's, the updates count, both Save names, the preferences panel, the saved confirmation, the profile's loading shape, the inset card, a section's icon and the about section's presence: all killed after four first survived (the updates count, the loading shape, the inset card and the icons were each asserted by nothing).
- **Not done and not claimed:** the web (BL-19.15 onward: nothing on the web changed), a block per part with its own held height on the home, a redesign of the job or course card beyond the job card's place line (the course card is built from the same `Card`, `Badge` and `Text` and was not changed), the Hindi for the one new string ("आपके बारे में", the engineer's, needs a native reader), and nothing ran on a device: TalkBack's reading of the progress bar and the two Saves, and 200% text in a panel, are on `mobile/ACCESSIBILITY.md`'s checklist.


## ADR-093: One Card for a Vacancy and a Course, Filters as a Row of Native Chips, and a Score a Seeker Can See Where They Look

**Status:** Accepted (October 2026). Sprint 84 (Epic B19, the first half of BL-19.15). Extends ADR-079 (a card says what decides whether to open it, and never accuses), ADR-086 and ADR-089 (tokens and surfaces), ADR-065 (a page must not jump while it loads) and ADR-068 (a recommendation says whether you can act on it). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon.

**Context:** The two lists were the product's front door and the least designed pages in it: a vacancy was a title over three grey lines, a course a row of grey badges, the filters a column of four selects that put the first result about 480 px down an 812 px screen, and a signed-in job seeker's list said nothing about how well each vacancy fitted them although the product's one promise is that it knows (UI-04). A course page had none of the trust the vacancy page has (UI-10). The design brief (signed off in Sprint 76) chose an avatar-and-icon-chip card and a filter-chip row.

**Decision:**

- **One card, two uses.** `components/cards/JobCard` and the new `components/cards/CourseCard` are the same shape: a mark for the organisation and the title in one row, **the money as a tinted chip with a rupee, the place and (for a course) the start as icon chips**, and a muted line for the rest (experience and how long ago; mode, language, level, credits, hours). The mark (`ui/avatar`) is **a first letter on a tint chosen by hashing the name** (four semantic tones, both themes by token): a logo would be better and the CSP refuses remote images. The tint carries no meaning (green is not "verified": that is its own icon and words), and the mark is hidden from assistive technology because the name is beside it. **A card still never says a provider or employer is not verified** (ADR-079). `components/cards` joins the migrated families, so the scale test holds it.
- **Filters are a row of chips, and each chip is a native `<select>`.** `ui/chip` (`ChipRow`, `ChipSelect`, `ChipButton`): the row scrolls sideways on a phone and wraps from `sm`; every chip is 44 px; a chip with a value is drawn filled, so what narrows the list can be seen without opening anything; a phone opens its own picker (a bottom sheet on Android and iOS), which is keyboard and screen-reader complete and **adds no code to the first load** (Radix's dialog is ~33 KB). The design brief said "a bottom sheet" and the native picker is that sheet. **Pay and Posted chips were not built**: there is no server filter for either, and a filter is not a thing to fake on the client over a page of 24. The order (A to Z, newest first) is a chip too.
- **A seeker's own score is on the card**, from `useMyScores`: the matches page's own query (`["matches"]`, `fetchMatches`, one key, so one request and one invalidation serve both pages), **enabled only for an account that holds a job-seeker profile** (a visitor or an organisation-only account makes no request that can only be refused), silent when it fails. A vacancy outside the top 50 has **no score and the card says nothing**, not "0%"; a score of zero is a score and is shown. **The title leaves room for a score before it arrives** (`scoreSlot`, `pr-24`, for every card in a seeker's list, scored or not): the score is a second request, and a title that re-wrapped when it landed would move the list under the reader's thumb (ADR-065).
- **A course page has the strip a vacancy has** (UI-10): "Verified provider" or "Provider not yet verified" (said on its own page, never on a card), "Registering interest is free. Ask the provider what any fee covers before you pay anyone." (a statement about the product today and about what to ask, not a promise about the provider), and a link to the report form on its own line at 44 px.

**Options considered:**

1. Keep the list cards and add the score as a line of text
2. **Rebuild both cards on one shape** (chosen)
3. A bottom sheet for filters (Radix `Dialog`, or a `<dialog>`)
4. **A row of native selects drawn as chips** (chosen)
5. Show the score from a per-job request when a card scrolls into view
6. **Read it from the matches the page already fetches** (chosen)

**Trade-offs:**

- Option 3: ✅ a designed sheet, room for many options and a Pay slider ❌ 33 KB (Radix) or a jsdom with no `showModal`, and the focus-trap code to keep; the native picker already is a sheet.
- Option 5: ✅ a score for every card ❌ one gap analysis per job on a list of 24, the cost ADR-056 and ADR-060 spent two sprints removing.
- Option 6: ❌ only the top 50 of a seeker's matches are scored on a list of up to 148+ vacancies: the card is silent about the rest, and a seeker should not read silence as "poor fit".

**Consequences:**

- **Height, as the brief warned:** the page got taller. On the review's script `/jobs` went **7.9 to 8.5 screens** (English) and 8.0 to 8.6 (Hindi), `/courses` **9.4 to 9.8** and 9.4 to 9.7, `/search` 5.2 to 5.3, a course page 3.0 to 3.2. The 30 percent the mock suggested for a card did not become 30 percent of a page, because the filters are about 330 px shorter. **Small targets did not move (jobs 0, courses 0, course page 2, search 6); text under 12 px 0; icons 3 to 54 on `/jobs` and 3 to 39 on `/courses`; errors 0.**
- **First load:** `/jobs` is 677,487 and `/courses` 673,398 bytes (well under 700,000); the shared graph is untouched (`/profile` 697,945, **headroom 2,055**; `/employer/[org]` 697,871). `/matches` rose by about 360 bytes (the extracted `ScoreDial` and the shared query). The phone's bundle is 3,730,144 (the new strings only).
- **Verified:** `tsc`, `eslint`, **951 web tests** (55 new: the avatar, the chips, both cards, the browsers' score and filters, the hook, the course strip's pieces), **146 browser tests** (two new journeys at 360 x 640, each through `checkPage`: a visitor's list on the new card with no score and 44 px chips and the first result on the first screen, then a seeker's list with a score on the card; and a course page's strip and its 44 px report link), `make mobile-check` (814), the contract check (54). **31 mutation checks** (29 on the components, hook and browsers, 2 in the browser journeys by removing the trust strip and the score): six first survived. Four were each asserted by nothing (the order chip's filled state, the fee chip's, the seeker's reserved room, and the shared query key) and are tested now; one was **a redundant line, removed** (`toLowerCase` in the tint's hash: capitals are 32 apart and the tint is a number modulo four, so folding case could not change a result, which a test would have claimed and nothing could check); one is left, a contrived mutant that adds `min-h-0` to the select inside a chip (the browser journey measures the select's height at 44 px; the mutant was not run there).
- **Not done and not claimed:** BL-19.15's remaining half (the home's icon tiles, the vacancy and course pages themselves, search and standards); **a Pay chip and a Posted chip** (need a server filter); the score on a card for a vacancy outside a seeker's top 50; a logo (the CSP; and `logo_url` is not shown); the Hindi and Malay for the five new course strings and the filter group's name (the engineer's; Malay is English, as that locale still is for most of these pages); Hindi at 200% text on the card; no device.


## ADR-094: A Listing's Facts Are a Labelled Grid With an Icon, Who Is Behind It Is an Icon and a Sentence, and a Standard Is a Card Like the Others

**Status:** Accepted (October 2026). Sprint 85 (Epic B19, the second half of BL-19.15). Extends ADR-093 (one card for a vacancy and a course), ADR-079 (a card says what decides whether to open it, and never accuses), ADR-087 (icons are separate pure exports; nothing in the header graph imports them) and ADR-089 (surfaces have a level). Web only and frontend only: no migration, no API or contract change (54 operations), **no new icon and no new message string** (every word on these pages was already there; the phone is untouched).

**Context:** Sprint 84 put the two lists on one card and left everything one click further in as it was: the home's two blocks were grey boxes with a number in a square, the vacancy and course pages a heading, a bordered box of unlabelled-by-shape facts and a text strip, search a stack of three differently built bands, and the standards pages (21,303 of them, the product's taxonomy) a list of cards with a hand-made chip row. The design brief (Sprint 76) asked for icon-led trust and scannable facts on these pages.

**Decision:**

- **Three small pieces, written once, server components.** `ui/icon-tile` (`IconTile`: an icon on a tinted square, five tones, two sizes, hidden from assistive technology because a word sits beside it), `ui/fact` (`Facts`, `Fact`, `FactValue`: **a description list** of labelled values with a small icon on each label, only `div` groups of `dt` and `dd` inside it, a `wide` value takes the row) and `ui/trust-strip` (`TrustStrip`: a shield on a green tile when the organisation is verified, an "i" on a neutral one when it is not **yet**, and the sentence beside it says which, so nothing rests on colour). **None is in the `ui/index.ts` barrel** (they draw icons, ADR-089) and none is a client component, so a page that draws twenty of them ships no JavaScript for them.
- **The home's two blocks lead each tile with an icon.** The three browse panels (Briefcase, GraduationCap, Award) and the four steps (Target, Search, BookOpen, Briefcase). The step's number is kept, small and at the right of its title and hidden from a screen reader (the `ol` already says the order); a test fails if two tiles share an icon.
- **The vacancy and course pages are the same page, built from the same pieces.** The organisation's mark (`Avatar`) beside who and where; the chips (type, level, closing date; mode, language, level) are `Badge`s with an icon; the facts are `Facts` (salary and experience; fee, length, place, next intake, what it counts toward, places), the course's qualification taking the whole row with "Stated by the provider" under it; the trust strip is `TrustStrip`, **and the vacancy's report link is on its own 44 px line as the course's already was** (the inline link in the sentence was a small target); a required standard is a 44 px row with a chevron. **The words are unchanged**, so the 320 selectors in the journeys still find them. A card in a list still never says "not verified" (ADR-079): the strip is on the listing's own page only.
- **A standard is `components/cards/StandardCard`**, one card for the standards browser and for search (the browser's cards and search's had been two hand-built ones): a mark, the kind (`Badge`, a tone each) and the level, the name as a heading (`h2` in the browser, `h3` under a search band's own `h2`), where it comes from (`StandardOrigin`, `lookalikeNames`, both moved here from the browser; the browser re-exports nothing) and, **unless `compact`, a line of description and how many qualifications use it**. Search passes `compact`: **the first version without it made `/search` 16 percent taller (5.3 to 6.1 screens) for lines nobody scanning six results asked for; compact is 5.7.**
- **Search's three bands each have a mark** (`IconTile size="sm"` in the heading) and their two controls are 44 px (the role's "What this job involves" toggle, the link to the rest).
- **The standard's own page** draws its kind and level as `Badge`s with an icon, its retired notice with a warning shape, and the two links under its lists ("See all jobs needing it", "See all courses teaching it") at 44 px. The course page's skill chips are 44 px too.

**Options considered:**

1. Keep the pages and add icons beside the text where they fit
2. **Three shared pieces and every page rebuilt on them** (chosen)
3. One generic `<Detail>` page component that takes a vacancy or a course
4. **Keep the two pages separate and share only the pieces** (chosen)
5. Show a standard's description on every search result
6. **Leave it out of search** (chosen)

**Trade-offs:**

- Option 3: ✅ one file ❌ a vacancy and a course differ in facts, in the one action (apply, register interest), in the strip's wording and in the report; the shared pieces are the part that is the same.
- Option 5: ✅ a fuller card ❌ six more lines of text on a page that is already the longest of the three result bands.

**Consequences:**

- **Height, again, and said:** measured on the demonstration database in the built-in browser at 375 x 812, the same way before and after (the dev server, same data, dark scheme): the home **6.3 to 6.4 screens**, a vacancy **2.9 to 3.0**, a course **3.2 to 3.3**, search **5.3 to 5.7**, the standards browser **9.5 to 9.7**, a standard's page **9.6 to 9.6**. **Controls under 44 px: home 1 to 1 (the hero's "Browse all courses" link, left on purpose: the hero has a fold budget in Hindi), vacancy 2 to 1, course 2 to 1 (what is left is the signed-out apply and interest panel's inline "Sign in" link), search 6 to 0, standards browser 0 to 0, a standard's page 2 to 0. Text under 12 px 0 on every page; icons home 6 to 13, vacancy 3 to 10, course 3 to 12, search 9 to 19, standards browser 3 to 27, a standard's page 3 to 5.** In Hindi the course page has no horizontal overflow and the home's Search button is where it was (478 of 812).
- **First load:** every route is **98 bytes** larger than at Sprint 84 (including ones that import none of the new files, so it is the shared chunk and probably module numbering, not a feature), `/jobs` and `/courses` 246; **`/profile` is 698,043 of 700,000 (headroom 1,957, was 2,055)**, `/employer/[org]` 697,969; **`/search` fell by 3,832 to 675,688** (it no longer imports the whole standards browser to reach three helpers). Measured by building `main` and this branch the same way.
- **Verified:** `tsc`, `eslint`, **1,007 web tests (56 new)**: each piece, the two home blocks (a server component is rendered by awaiting it with the translator mocked), **the three detail pages rendered as server components against the real English catalogue**, the shared card, the standards browser and the new search and related-link controls. **47 mutation checks, all killed after three first survived** (the shared card's shadow, the verified state on the vacancy strip, and the browser's use of the card, which had no test at all: it has one now).
- **Not verified, and the reason is stated:** **nothing ran in Playwright this sprint.** The machine has no Chromium (`~/Library/Caches/ms-playwright` does not exist; a download of about 99 MB was offered and declined), so **none of the 146 existing browser journeys, the new three in `e2e/discovery.spec.ts`, the sweep's axe contrast in light and dark, its layout-shift score and its target ratchet, or the 52-capture script** was run against this change. The new journeys' selectors were checked by running the same queries in the built-in browser (three bands with a mark each, a mark on the first standards card, three tiles with a drawn icon, four steps with their numbers, two fact icons and a 44 px report link on a vacancy), **but a test that has never run is not a test that passes**: run `make e2e` where Chromium exists before merging. The target baseline (`web/e2e/support/target-baseline.json`) is **not re-recorded**: the counts above went down and the ratchet only goes down, so it cannot fail on them, but it is not tight. Contrast rests on the token tests (every pairing, both themes), not on axe on these pages.
- **Not done and not claimed:** the hero's small link; Pay and Posted chips (no server filter); a logo; the standards page's "See all" lists as cards (they are still bordered rows); a person at 200% text in Hindi on the new facts; the Hindi and Malay for the words on these pages are unchanged and still need a native reader; no device.


## ADR-095: A Form's Controls Are the Library's and 44 px, a Row's Buttons Are Named for Their Row, and a Confirmation Keeps What the Person Typed

**Status:** Accepted (October 2026). Sprint 86 (Epic B19, BL-19.16). Extends ADR-088 (a field says what is wrong next to itself), ADR-079 (floors are asserted where they hold) and ADR-083 (every control at 44 px, one primary action per row). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon (the apply confirmation uses the shield already in the set), no new message string.

**Context:** Sprint 79 gave forms a field library and migrated 25 of them; sign-in was not one (two raw inputs with their own classes, so no inline problem), the sign-up consent row was a one-line 20 px label at desktop width, and the profile, the page a person returns to most, still had a 10 px "x", 18 px "Edit" and "Remove" text buttons on every history row and every skill, and a 22 px link and an 18 px "Skip for now" at the top. On the review's own demonstration account the profile held **17 controls under 44 px**. The apply confirmation (the product's one deliberate disclosure, ADR-037) was a bordered box inside a sticky bar whose refusal, when there was one, was drawn **below the box and out of sight** on a short phone.

**Decision:**

- **Sign-in's two fields are the library's** (`Field` + `Input`): a label tied to its control, a problem shown beside the field when it is left empty (`aria-invalid`, `aria-describedby`), 44 px (50 on the page's larger type). The code field keeps its look (centred, large, spaced) and its rules (digits only, six characters). "Use a different one", "Send a new code" and the "Create an account" link are 44 px; sign-up's code step has the same two buttons at 44.
- **The sign-up consent row is the target** (`min-h-11` on the label, the box 16 to 20 px), the privacy and terms links stay inside the sentence the person agrees to. **A link inside a sentence is not changed**: the sweep and WCAG 2.5.8 both exempt it, and the sentence is the recorded consent.
- **A row's buttons are 44 px and named for the row.** `EntryRow` (the six history sections) and the skills list: "Edit: Ward attendant · Chennai Community Hospital", "Remove: Bed making". The name **contains the visible word** (WCAG 2.5.3) and is the thing a screen reader needed: sixty "Remove"s are sixty identical names. The tag chips' remove is a 44 x 44 square on the end of the chip (the chip is 44 tall, as the filter chips are). The title column is `basis-48`, not `flex-1`, so on a phone the buttons **drop under the title** instead of squeezing it into a column four lines tall (the first version did).
- **The wizard's "Skip for now" and the "My matches" link beside the badge are 44 px.**
- **The apply confirmation is one group named by its heading** (`role="group"`, `aria-labelledby`): a shield tile, the disclosure and the withdrawal note (words unchanged), the note as a `Field`/`Textarea` (its 1,000-character limit still literal at the control), **a refusal inside the group, next to the buttons that caused it** (shown outside only when the group is closed, as a failed withdrawal is), and the two buttons stacked at full width on a phone, a reversed row from `sm`. **What the person typed is kept** through a failed request and through closing and reopening the step, and cleared only by a success.

**Options considered:**

1. Raise only the controls the sweep's ratchet counts
2. **Raise every control found by measuring a real account, and fix the names** (chosen)
3. Keep Edit and Remove beside the title and let the title wrap
4. **Let the buttons drop under the title when they do not fit** (chosen)
5. Hide Edit and Remove behind a "More" menu on a phone (ADR-083's row pattern)
6. **Keep both visible: a profile row has two actions of equal weight** (chosen)

**Trade-offs:**

- Option 1: the sweep's account is a new one with nothing on it, so it saw 2 kinds on `/profile`; the demonstration account saw 17 controls. A ratchet over an empty page is a floor, not a measure.
- Option 4: ✅ nothing is squeezed, both actions are one tap ❌ **the profile is 0.5 screen longer** on an account with six history entries (7.5 to 8.0), because each row now has its buttons on a line of their own.
- Option 5: ✅ shorter rows ❌ a second tap for the commonest action on the page, and a menu is code on a route with a ceiling.

**Consequences:**

- **Measured** (the built-in browser at 375 x 812, the demonstration database, before and after the same way; `docs/design/screens/measurements.sprint86.json`): `/profile` on an established account **17 controls under 44 px to 0**, 7.5 to 8.0 screens (6,091 to 6,471 px); the first-run wizard's 2 to 0; the sign-up consent row 335 x 60 and the page 1,728 to 1,744 px; sign-in unchanged in height (1,411); the apply confirmation 335 x 444 with both buttons 301 x 44.
- **First load:** `/profile` is **698,914 of 700,000 bytes: headroom 1,086**, and this needs saying plainly. It was 698,043 at the end of Sprint 85 and **the merged Dependabot web group (Next 16.4.2, React 19.3.1, ...) took it to 698,376 before this sprint began (headroom 1,624)**; this sprint adds 538. About 400 of that is a new shared chunk's bookkeeping, **seen on routes that import none of the changed files** (`/jobs` +409, `/courses` +409, `/signup/[type]` +412, `/search` +427; the build had one more chunk file and four others each grew by 107 bytes); about 140 is the profile's own class names and row labels. `/jobs/[slug]` rose 3,855 (the apply confirmation now loads the field library, one icon and the tile; the route has 28 KB left). **The next story that touches the shared graph has to come out of ~1 KB or make a chunk.**
- **Verified:** `tsc`, `eslint`, **1,036 web tests (29 new)**: sign-in's field (its problem, its 44 px, its larger type, the code step's digits and maximum, the three controls), sign-up's consent row and code-step buttons, `EntryRow`, the tag chip's remove, the skills row, the wizard's skip, the identity link, **the apply confirmation (its group and heading, the shield, the field and its limit, a refusal inside it with what was typed kept, kept through cancel and reopen, sent trimmed, cleared by a success, the stack)**, and a failed About save keeping the typed name and headline. **36 mutation checks, all killed** after two that first survived and were not real (one equivalent: clearing the note twice; one a missing test: nothing asserted that a success clears the note, which now has one). Two existing tests looked a button up by its bare name ("Edit", "Remove") and now by its row's.
- **Not verified, and the reason is stated:** the same as Sprint 85, **nothing ran in Playwright** (no Chromium on this machine, the download declined): not the 146 + 3 existing journeys, not the sweep's axe contrast, layout shift and target ratchet. The ratchet's recorded counts (`target-baseline.json`) are **not re-recorded**; they only go down, so they cannot fail on this, but they are not tight. The live code step of sign-in and sign-up was not driven in the browser (unit tests cover it).
- **Not done and not claimed:** the profile as icon sections (BL-19.23 did that on the phone; the web's section headings are unchanged), inline validation on the sign-up form's other fields (it already used the library), the Hindi and Malay of nothing new (no string changed), the account page's controls, a person at 200% text on the longer rows, no device.


## ADR-096: A State Is a Word With a Shape on a Card That Looks Like the Others, a Notice Has a Picture of Its Kind, and a Shared Section Takes Its Mark From the Page That Wants It

**Status:** Accepted (October 2026). Sprint 87 (Epic B19, BL-19.17). Extends ADR-093 and ADR-094 (the shared card, the mark, the pieces that draw icons), ADR-087 (an icon is paid for by every route that loads it), ADR-089 (a status has a shape, an empty list says what to do) and ADR-095 (a repeated control is named for its row). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon, no new message string.

**Context:** Sprints 84 and 85 gave the discovery pages one card, a labelled fact grid and an icon-led trust strip. The pages a signed-in person returns to were still the old look: an application was a bordered box with a grey word in a corner, a course interest the same with a smaller word, a saved job a link in a box, a notice a line of text with two 12 px links, the account a stack of text sections, and the career page's budget a raw 40 px input. The matches page had been done in Sprints 70 and 84.

**Decision:**

- **A state is `StatusChip`** (`ui/status-chip`): the word, an icon and a tone from one table per list (`APPLICATION_LOOK`, `INTEREST_LOOK`), each a `Record` over the generated status type so **a new state the server can say is a compile error here, not a chip with no shape**. Nothing rests on colour (WCAG 1.4.1): "Shortlisted" and "Not selected" differ in word, shape and tone. **A rejection is neutral, not red**: it is the employer's decision about a vacancy, and "calmer" was the brief's word.
- **An application, a course interest and a saved job are on the card** (`cards/ApplicationCard`, `InterestCard`, `SavedJobRow`): the organisation's mark, the title and the organisation, the state chip and the date as an icon chip, the sentence about what the state means, and the employer's own message set apart. **What a person does next arrives as a `footer`** (why was I not selected; rating the poster), so the card owns the look and the list owns the behaviour and the mutations. A saved job is **one link** (a mark, two lines, a chevron) because it holds no button; a card that holds a button is not a link (ADR-074).
- **A notice has a picture of its kind** (`NoticeTile`): one table over the seven templates the outbox writes, the bell for any other, bright while new and neutral once read, hidden from a screen reader (the words are the notice, and a new one is also marked "New"). **A test holds the table equal to the templates `lib/notice-text` writes words for**, so a new kind cannot ship with no picture. **It is a component and not part of `lib/notice-text`**, which more routes import than draw a notice. The two lists that show notices (the unread panel and `/notifications`) use it, and their "Open" and "Mark as read" are 44 px (they were 12 px text links, the smallest controls on the page).
- **The account's four sections each lead with a mark**, and the sign-in section (`CredentialsSection`, which `/profile` also renders) **takes its mark as an optional prop from the account page** instead of importing the icon module: `/profile` has about 1 KB of first-load room and the factory costs more, so the icon is created by the one page that wants it and a test fails if the section ever imports it. The link to the privacy notice is 44 px.
- **The career page's course budget is the field library's** (`Field` and `Input`, the limits still literal at the control, 44 px) and the Why-not-me toggle is 44 px.

**Options considered:**

1. Keep each list's own box and change only the colour of the word
2. **One card per list on a shared look, the state as a chip with a shape** (chosen)
3. Put the icon table inside `lib/notice-text`
4. **A component beside the two lists that draw it** (chosen)
5. Add the mark to `CredentialsSection` itself
6. **Pass it in from the account page** (chosen)

**Trade-offs:**

- Option 3: ✅ one file ❌ `notice-text` is imported by routes that never draw a notice; an icon there is paid for by every one (ADR-087).
- Option 5: ✅ simpler ❌ the profile's first load, at about 1 KB of headroom, would pay for the factory for a heading it does not decorate.
- Option 2: ❌ the pages are a little longer (about 0.1 screen each) because the date is now a chip of its own beside the state.

**Consequences:**

- **Measured** (the built-in browser at 375 x 812, the demonstration database, signed in as a demonstration seeker, before and after the same way; `docs/design/screens/measurements.sprint87.json`): `/applications` 1.8 to 1.9 screens, `/interests` 1.8 to 1.9, `/account` 3.3 to 3.4, `/career-paths` 4.9 to 4.9; **controls under 44 px: the account 1 to 0 (the notice link, 167 x 18) and the career page 1 to 0 (the budget, 144 x 40, now 44)**; applications, interests and saved 0 to 0; icons 8 to 10 (applications and interests), 9 to 13 (account). **Not measured live:** the notification rows (the demonstration account has none; unit tests hold them) and the saved list against its empty state (different data).
- **First load:** `/profile` is **699,013 of 700,000, headroom 987** (698,914 at the end of Sprint 86): **+99 on every route that imports none of the changed files** (the shared chunk's bookkeeping, the third sprint in a row it moved by itself), so the profile's own change is about nothing; `/applications` +3,304, `/account` +4,234, `/notifications` +1,785, `/saved` +1,906, `/interests` +1,522 (the card, the shapes and the marks they now draw; each route has 14 KB or more); `/matches` and `/career-paths` -4. **The headroom has gone from 2,055 (Sprint 84) to 987 in three sprints and almost none of it was the profile's own code** (about 140 bytes in Sprint 86; the rest is a dependency bump and the shared chunk's bookkeeping). The next story that touches the shared graph has to make a chunk or come out of it.
- **Verified:** `tsc`, `eslint`, **1,086 web tests (50 new)**: the chip, the three cards (every status has a look, a rejection is neutral, two states never share word, shape and tone, the employer's message and its date, a removed vacancy, the footer), the notice tile (hidden, every template drawn and drawn apart, the bell, bright then neutral), both notice lists (a tile per row, two 44 px actions), the account's marks and tones, `CredentialsSection`'s prop and its source guard, the budget field, and `SavedList` (which had no test). **48 mutation checks, all killed after three first survived** (the saved row's mark, the saved list's link target, the toggle's 44 px: each asserted by nothing).
- **Not verified, and the reason is stated again:** **nothing ran in Playwright** (no Chromium on this machine; the download was declined for Sprint 85 and not asked again). Sprints 85 and 86 passed their CI E2E; this sprint's journeys, the sweep's axe contrast in light and dark, its layout shift and its target ratchet have not run against these pages, and `target-baseline.json` is not re-recorded. CI's E2E is the first real run.
- **Not done and not claimed:** the matches page (already on the card), the career ladder's own step cards (unchanged), a light-mode or Hindi look at any of this (Hindi words are unchanged; a status word in Hindi may wrap onto a second line beside its shape), the notification rows seen live, no device.


## ADR-097: A Workspace's Rows Say Where Things Stand With a Shape, a Dashboard Figure Has a Mark, and Neither Workspace Is in the Route's First Load

**Status:** Accepted (October 2026). Sprint 88 (Epic B19, BL-19.18). Extends ADR-096 (a state is a word, a shape and a tone, one table per list), ADR-083 (one primary action per row, every control 44 px), ADR-087 and ADR-089 (the icon factory is paid for by every route that loads it), ADR-073's lesson about a ceiling and ADR-065 (a placeholder is the same shape as what replaces it). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon, no new message string.

**Context:** The hiring side's pages were already at the floors Sprint 73 set (every control 44 px, one action per row), so there was nothing small to raise; they were still the old look: a vacancy's state a grey or green word in a corner, a dashboard a run of bare numbers, an applicant's state and a learner's state a plain badge, a team of names with a text role, and a bulk upload's result a column of coloured words. Separately, `/employer/[org]` is one route that renders the employer's workspace **or** the provider's: `OrgWorkspace` imported both.

**Decision:**

- **A vacancy's and a course's state is `StatusChip` from `cards/listing-look`**: four states (`removed`, `draft`, `live`, `closed`), a tone and a shape each, decided by two small pure functions (`jobState`, `courseState`) so a takedown wins over a draft and a published-but-not-open vacancy is **closed, never "published"** (its page is still there, so "published" would call it open) and an `is_open` that is absent is not guessed open. The place and the counts (standards, mandatory) are icon chips. **A course has no closed state**, and its type says so.
- **An applicant's and a learner's state use the tables the candidate sees**, moved into `cards/application-look` and `cards/interest-look` so a workspace can import a table without importing a card; the candidate's card re-exports them. The match score has a shape of its own. The words are the inbox's own (`New`, `Not suitable`, `Contacted`, `Enrolled`).
- **A dashboard figure is a `MetricTile`** (`ui/metric-tile`): the figure and label exactly as `StatTile` draws them (a dash for a number that has not arrived, never a zero) beside a mark, two to a row on a phone, a lone rating tile taking the row. It is **not** `StatTile` with an icon: `StatTile` is in the `ui` barrel, on every route's first load, and `/profile` has under 1 KB left.
- **The team's members have a mark and a role with a shape** (owner, admin, member; an invitation's pending, accepted, revoked and expired), the chip under the name, not beside it (beside it, "Apollo Care Hospitals team" wrapped onto two lines at 375 px). **The bulk upload's result rows are `ROW_LOOK`**, a `Record` over the server's row statuses (a new one is a compile error), five tones and five shapes; its file input and its update checkbox are 44 px (the file input was 22).
- **`OrgWorkspace` loads each workspace with `next/dynamic`** at module level, with the memberships' own `Skeleton` as the placeholder. This was **forced by the budget, not planned**: the first version, with both still imported, made `/employer/[org]` **703,701 bytes, 3,701 over the ceiling**. `workspace-structure.test.ts` fails on a static import of either.

**Options considered:**

1. Raise the ceiling for this route
2. **Lazy-load the two workspaces, which no visit needs both of** (chosen)
3. Drop the icons from the dashboards and rows
4. Lazy-load only the dashboards
5. A `StatTile` with an `icon` prop
6. **A separate `MetricTile` outside the barrel** (chosen)

**Trade-offs:**

- Option 1: the ceiling is the only thing that makes a phone on mobile data a fair test, and raising it for a route because it grew is how a ceiling stops meaning anything.
- Option 2: ✅ the route lost **31,275 bytes** (698,703 to 667,428), far more than the sprint added ❌ a short second wait: after the memberships answer, the chunk for the right workspace is fetched (the same skeleton is shown, in the same place).
- Option 4: saves less (the charts, not the unused kind's whole screen) and leaves the other kind's code in every organisation's first load.
- Option 5: a prop with an element in it costs every route a few dozen bytes.

**Consequences:**

- **Measured** (the built-in browser at 375 x 812, the demonstration database, signed in as the demonstration employer and provider, before and after the same way; `docs/design/screens/measurements.sprint88.json`): employer home **4.7 to 5.0 screens**, applicants 2.5 to 2.5, team 2.8 to 2.9, provider home 7.8 to 8.0, learners 1.9 to 1.9, bulk upload 2.4 to 2.5; **controls under 44 px: the upload page 1 to 0 (the file input, 293 x 22), every other page 0 to 0**; icons on the employer home 4 to 33 and the provider home 5 to 35. A layout-shift reading in the pane was 0 on both homes after the lazy loading, which is **not** the sweep's check.
- **First load:** `/employer/[org]` **698,703 to 667,428**; applicants +648, team +4,040, a course's learners +543, the two upload pages +3,387; **`/profile` is unchanged at 699,013 (headroom 987) and is again the closest route** (admin 695,554). Measured by building `main` and this branch the same way.
- **Verified:** `tsc`, `eslint`, **1,143 web tests (57 new)**: `MetricTile`, the listing states (a truth table and the looks), both dashboards' tiles, a vacancy's and a course's chip (each state's tone and a different shape each), the counts, both inboxes' chips (and the score's shape differing from the New chip's), the team's marks, roles and invitation states, `ROW_LOOK` and the upload's two controls, and a source guard for the lazy workspaces. **43 mutation checks, all killed** after five first survived (a course chip's icon, the score's icon, two invitation shapes: each asserted by presence of a drawing and never by its difference; and one mutant that was not a mutant, a class that did nothing).
- **Not verified, and the reason is stated again:** **nothing ran in Playwright** (no Chromium; the download was declined for Sprint 85). Sprints 85 to 87 passed their CI E2E; the existing journeys' selectors on these pages, the sweep's axe contrast in light and dark, its layout-shift score (**the two-stage placeholder is exactly what it measures**) and the target ratchet have not run against this change. The criterion "no browser journey selector breaks" is therefore **not verified**.
- **Not done and not claimed:** the candidate shortlist, the sponsor panel, organisation settings and the two editors (the editors were migrated to the field library in Sprint 79 and are unchanged); the employer's applicant name still shows when the person applied (a de-identified reference otherwise; no avatar, because a mark made of a reference's letter would be a fact about nobody); Hindi and light mode.


## ADR-098: The Back Office and the Static Pages Say Where Things Stand With a Shape, a Complaint's State Is One Table for Both Its Readers, and the Error Page Has No Picture

**Status:** Accepted (October 2026). Sprint 89 (Epic B19, BL-19.19 and BL-19.20). Extends ADR-096 and ADR-097 (a state is a word, a shape and a tone, one table per list; a figure has a mark), ADR-083 (the back office's structure and the 44 px floor), ADR-089 (the barrel puts what it names on every route) and ADR-087 (an icon is paid for by every route that loads it). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon, no new message string.

**Context:** The back office was already folded, tiered and at the 44 px floor (Sprint 73) and its queues' structure is not what this story changes. What it still had was the old look: an overview of six bare numbers, a queue card whose state was a coloured word, an overdue complaint shown as a word with no mark, a verification badge as text. The static pages (about, employers, providers, the legal pages, the contact and grievance forms, 404 and error) had text and nothing else, and a grievance's state was drawn **twice, by two different local tables**: once in the operator's queue and once in the list the person who complained sees.

**Decision:**

- **A complaint's state is one table**, `cards/grievance-look` (`GRIEVANCE_LOOK`: open, acknowledged, resolved, dismissed, each a tone and a shape), read by the operator's queue **and** by the sender's own list. Before, each had its own tone map and the person's list had no shape at all.
- **The overview's six figures are `MetricTile`s** (ADR-097), each with a mark and a dash while the number has not arrived, the same shape before and after (ADR-065).
- **Every state in the queues has a shape**: a verification request's kind (employer or provider), a complaint's overdue marks (a triangle on each overdue stage), a reported listing's removed and report-count chips, an organisation's verified badge and each decision in its history. **The queues' structure, the folded panels and `admin-sections` are untouched.**
- **The static pages' audience cards take an optional `icons` prop** (`AudiencePage`), an `IconTile` before each card title on About, Employers and Providers. The 404 has a search mark, a placeholder page a clock in its "Drafting" badge, a legal page a warning in its draft badge and a shield beside the grievance officer.
- **The error page has no picture.** `error.tsx` is in every route's first load; a mark there would be paid for by all of them, and `/profile` has under 1 KB left. The 404 is not in the shared graph and has one.
- **Controls on these pages are 44 px**: the grievance form's radio rows (22 px) and a legal page's account link (18 px).

**Options considered:**

1. Give the queues pagination while restyling them
2. **Leave their structure alone and change what each row says** (chosen)
3. Keep the two local grievance tables and add shapes to each
4. **One table for both readers** (chosen)
5. An icon on the error page

**Trade-offs:**

- Option 1: a hundred cards still render in the verification queue, but the browser journeys look organisations up in that queue, and none of them can be run here; a structural change nobody can test is the wrong kind of change to ship in a visual sprint.
- Option 4: ✅ the operator and the person describe a state in the same shape, and a new status is a compile error (`Record<GrievanceStatus, ...>`) in one place ❌ the person's list now imports a module the queue also imports, which is the point.
- Option 5: ✅ consistent ❌ every route pays for the factory and the icon; refused for the reason ADR-089 gives.

**Consequences:**

- **Measured** (the built-in browser at 375 x 812, the demonstration database, before and after the same way; `docs/design/screens/measurements.sprint89.json`): `/admin` **29.1 to 30.3 screens** (23,652 to 24,618 px; icons 6 to 112, because the queue holds a hundred rows), About 2,877 to 3,033 px, Employers 2,903 to 3,059, Providers 2,791 to 2,947, the grievance page 2,967 to 3,033, privacy 6,335 to 6,357, careers unchanged at 1,451, the 404 1,377 to 1,433; **controls under 44 px: `/admin` 0 to 0, the grievance page 1 to 0 (before the radio rows were fixed: 4), privacy 1 to 0** (the account link).
- **First load:** `/admin` **695,554 to 697,221** (headroom 2,779); **`/profile` is unchanged at 699,013 (headroom 987) and is still the closest route**; About 664,247, Employers and Providers 663,326, grievance 671,499 (sprint-start figures were not all taken: only `/admin` and `/profile` were compared against `main`).
- **Verified:** `tsc`, `eslint`, **1,178 web tests (35 new)**: `AudiencePage`'s icons and the three pages' marks (by walking the page's returned element tree), the 404, the placeholder and the legal pages (including the 44 px link), the overview's tiles, each queue's chips and their shapes, `MessageForm`'s radio rows and the person's list per status (a shape equal to the table's, and four shapes that differ). **33 mutation checks, all killed** after the grievance icons, the overdue triangle and the person's list chip each first survived (asserted by presence, not by equality with the table's shape).
- **Not verified, as in Sprints 85 to 88:** **nothing ran in Playwright** (no Chromium; the download was declined). The existing journeys' selectors on `/admin` and the contact pages, the sweep's axe contrast in light and dark, its layout-shift score and the target ratchet have not run against this change; CI's E2E is the first real run. The ratchet baseline is not re-recorded (the grievance and privacy counts only fall).
- **Not done and not claimed:** the verification queue still renders up to a hundred cards at once (paging it needs its journeys run); the alias, programme and enrolment panels were not re-looked beyond their shared pieces; the invite page and the employers' demonstration page; Hindi, Malay and light mode; the new strings none (no message changed), but every page's Hindi look is the engineer's.


## ADR-099: Text That Does Not Fit Is Wrapped or Broken and Never Cut Off, a Page Is Checked at Twice the Size in Every Language, and the Review Says What It Could Not Run

**Status:** Accepted (October 2026). Sprint 90 (Epic B19, BL-19.25 and BL-19.26). Extends ADR-086 (the type scale: secondary text is 15 px and the floor is 12 px), ADR-077 (accessibility is held by the properties that produce it, and by saying what a test cannot see) and ADR-065 (a page that works at one size is not a page that works). Web only and frontend only: no migration, no API or contract change (54 operations), no new icon, no new message string.

**Context:** Epic B19 changed how every page looks, and the language pass it ended with asked a simple question: does anything run off the screen or get cut off in Hindi or Malay at 360 px, at 200% text? Nothing had been asked at that size since Sprint 54. The test suite cannot answer it (jsdom has no layout) and the browser sweep checks English and Hindi at ordinary size only. So every page was loaded in the built-in browser at 360 px with `document.documentElement.style.fontSize = "200%"` (the layout's rem units follow it), signed out and as a job seeker, an employer, a provider and an operator, and a small checker was run on each: a page wider than the screen, a text node outside its box, an element with an ellipsis whose text is longer than it, a clipped box.

**Findings:** At ordinary size, in either language, none (about 90 page loads). At 200%, ten: a long English word or code in a chip or a card (an alias chip holding "documents/instructions/correspondence" made a skill page 668 px wide; a qualification code overflowed a card; a place name overflowed a job card), the four-tab bar (the icon wrapper was wider than its cell and labels ended in "..."), the match score beside a title (the title was left 77 px), a chart label cut with an ellipsis, an applicant's three chips, a profile row's Edit and Remove and its confidence label, the language select in the sign-in header, a filter select in the back office, and the workspace control in the mobile menu (a label of two words ended in "...").

**Decision:**

- **`body { overflow-wrap: anywhere }`** in `globals.css`. Not `break-word`: both break a word that would otherwise overflow, but `anywhere` also counts the break in the element's minimum width, so a flex item holding "documents/instructions/correspondence" can shrink instead of widening the page. It acts only on a word that would overflow, so ordinary text is unchanged (checked: page heights identical with the rule on and off on `/hi/courses` and `/hi/privacy`).
- **A group of chips wraps inside itself** (`flex-wrap max-w-full`), a row whose two halves cannot both fit drops the second under the first (`flex-wrap`, the title `min-w-0 grow basis-40`), and a select takes `max-w-full` or `min-w-0`.
- **A label that is the information wraps; a label that is a convenience may be cut.** A chart's label (a standard's name) and the bottom bar's label wrap; the header's compact workspace control still truncates a long organisation name, and wraps only in the mobile menu where it has the row. The bar's cells may shrink (`min-w-0`), and its icon wrapper may be narrower than its width (`max-w-full`).
- **`src/lib/text-fit.test.ts` holds the source of each fix** (jsdom cannot see layout) and proves its matcher can fail. 11 mutations of the fixes were run: ten were killed at once; one survived (the tab bar's `li` lost its `min-w-0` and a neighbouring `min-w-0` on the link stood in for it) and the test now asserts each of the bar's four classes by itself.

**BL-19.26, the record:** `scripts/build_ui_review.py` was brought up to date: nine findings gained a status (UI-18, 20, 21, 22, 24, 25, 27, 28, 29), the "built so far" paragraph that still described Sprint 70 was rewritten from the data, and a table of the numbers each Epic B19 sprint recorded was added. **Two findings stay open and both are the owner's: UI-03 (no photograph, illustration or logo art) and UI-23 (the launcher icon and splash are still Expo's template art).** `tests/test_ui_review.py` now holds those two as the only open ones, and that every file the new table cites exists.

**Options considered:**

1. Cap the root font size, or let text overflow at 200% as a known limit
2. **Make the layout survive it** (chosen)
3. Break words everywhere with `word-break: break-all`
4. **`overflow-wrap: anywhere` on the body** (chosen)
5. Truncate everything with an ellipsis and a title
6. **Wrap what is the information and truncate only what repeats elsewhere on the page** (chosen)

**Trade-offs:**

- Option 1: a person who sets their phone's text to the maximum is the person for whom the product is meant (a low-end phone, a first-time reader); a layout that works only at ordinary size is not a result.
- Option 3 breaks ordinary words mid-word at ordinary size; option 4 breaks only the word that cannot fit.
- Option 5: a `title` is invisible on a phone, so a cut label is a lost label.
- The global rule can change a layout that sizes itself by its content (a table, an absolutely placed menu): none was found on the pages checked, and it is the first thing to try if a page is oddly narrow.

**Consequences:**

- **First load:** `/profile` **699,013 to 699,067 bytes (headroom 933)**, still the closest route; `/admin` 697,301 (headroom 2,699).
- **Verified:** `tsc`, `eslint`, **1,187 web tests (9 new)**, `tests/test_ui_review.py` (10) and `tests/test_adr_register.py`. Every page that failed at 200% was loaded again and passed, in Hindi and in Malay.
- **Not verified, and the reason:** **nothing ran in Playwright** (no Chromium; the download was declined in Sprint 85), so the sweep, axe and the layout-shift check have not run against these changes; **the 52-capture script was not re-run**, so the review's "after" figures for Epic B19 are the sprints' own (the built-in browser against the development server) and are not comparable page for page with the production-build tables above. 200% here is the root font size, not the operating system's font scaling, and nothing ran on a device. The phone app was not checked at 200% (it caps text at twice, `MAX_FONT_SCALE`).
- **Not done:** a dialog open, the first-run wizard, the invitation page and light mode were not checked at 200%; **a native Hindi reader has not read the Hindi written in Epic B19 (BL-19.25's second criterion, the owner's to arrange)**; BL-19.24 (launcher art) waits on the owner.
