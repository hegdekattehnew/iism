# Architecture Decision Records — Intelligent Integrated Skill Marketplace

> Workforce Mobility OS — CTO Office, March 2026

> Source: `Intelligent_Integrated_Skill_Marketplace - ADR.xlsx` (converted to Markdown for version control)

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

**Status:** `

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

**Status:** Accepted

**Context:** Need focused GTM

**Decision:** India-first, single-sector rollout

**Options considered:** 1. Multi-sector
2. Single sector

**Trade-offs:**

- Option 1: ❌ Diffused

- Option 2: ✅ Faster validation

**Final decision:** Single sector (initial)


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

**Final decision:** 


---
