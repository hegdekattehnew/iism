# Scope reconciliation — the product definition against the tree

**Written 2026-09-24, against commit `64792e2`.** Every row was re-derived from the code at the
moment of writing, not carried from a plan or from memory. Check it rather than trusting it: the
whole value of this document is that each claim names a file you can open.

## Why this exists, and what it is not

`docs/IISM-Product-Definition.docx` is the baseline. It is a good document and it is **one release
behind reality in seven specific places** — it describes some things as built that are not, and
describes some as configurable that are constants. None of that was concealed; it accumulated the
way a written scope always does when the code moves faster than the prose.

This is a **ledger, not an amendment**. The product definition is deliberately left as written, on
the owner's instruction — so this file sits beside it and says where the two disagree. If you are
taking the baseline into a meeting, read this first.

**Nothing here is a defect**, with one exception noted at the end. The rest are deferrals, most of
them with an ADR already explaining the reasoning. The problem is not that they were deferred; it
is that §6.1 lists several of them under "In scope for version one", so the document overstates
what exists.

---

## The seven divergences

### 1. Matching is deterministic only; §6.1 says hybrid

**The baseline:** §6.1, *"Hybrid matching — deterministic components and semantic similarity
together, as specified in ADR-007."* §5.3 lists Semantic similarity as one of five scoring
components.

**The tree:** there is no embedding code in `api/` at all — `grep` for `Vector`, `embedding` or
`sentence_transformers` outside comments returns nothing. pgvector is *enabled* (migration `0001`,
and `/health/deep` reports it) and unused. `api/modules/matching/__init__.py` states the position
directly: *"Deterministic scoring only. No model client lives here and none may be added."*

**Standing:** a knowing deferral. ADR-036 says deterministic overlap ships first so there is a
baseline to measure against, and ADR-013/ADR-031 hold the embedding design. §6.1 simply does not
say so. The scorer is four components, not five.

### 2. The match weights are constants, not configuration

**The baseline:** §5.3, *"All weights live in configuration, not code, so they can be re-tuned
against measured outcomes without a deployment."*

**The tree:** `api/modules/matching/scoring.py` — `MANDATORY_GAP_CAP = 0.45` (line 47),
`COVERAGE_WEIGHT = 0.75` (52), `EVIDENCE_WEIGHT_SHARE = 0.10` (53), `LEVEL_WEIGHT = 0.08` (60),
`EXPERIENCE_WEIGHT = 0.07` (61). Module-level constants. Nothing in `api/core/config.py` mentions a
weight. Re-tuning needs a deployment.

**Standing:** worth stating fairly from both sides. ADR-036 requires `scoring.py` to be **pure** —
no I/O, no clock, no model — and reading `get_settings()` inside the scorer would break that and
the reproducibility the golden set depends on. But purity does not require *constants*: the weights
could be a frozen value object passed in, defaulted from configuration at the call site, and the
scorer would stay pure. So the baseline's goal is reachable; it has just not been built. Until it
is, a weighting change is a code change and a deploy.

### 3. Recommendations are instrumented as served and clicked, never dismissed

**The baseline:** §6.1, *"Analytics instrumentation on every recommendation served, clicked and
dismissed."*

**The tree:** 23 names in `EVENT_NAMES` (`api/modules/analytics/models.py`). `course_recommended`
is served, `course_opened` is clicked. **There is no dismissal event**, and no client code that
would emit one.

**Consequence, and this is the one that costs something:** ADR-025's precision@5 has **positive
signal only**. "Five were shown and one was opened" and "five were shown, one was opened and four
were explicitly rejected" are the same rows. A measure with no negative class cannot distinguish a
good recommendation from a tolerable one.

### 4. Course-to-job alignment — "the differentiator" — exists only through a candidate

**The baseline:** §5.5 is titled *Course-to-job alignment* and calls it **"The differentiator"**:
*"For a course and a target role, we compute how much of that role's skill requirement the course
actually covers."* §6.1 lists *"Course-to-job alignment scoring and gap-closing course
recommendation"* as two things.

**The tree:** the second exists — `courses_closing_gap` in `api/modules/matching/service.py` ranks
courses against **a candidate's** computed gap, and Sprint 29 gave it 16 labelled expectations.
The first does not: no function takes a course and a role and returns coverage. Nothing in
`matching`'s public interface exposes one.

**Standing:** the candidate-mediated form is what the product actually uses, and it is the harder
and more useful half. But the course→role score is what a *provider* would need to be told "your
course covers seven of the nine standards this occupation requires", which is §3.4's promise to
providers and is not computable today.

### 5. Three of eight actor types exist, plus a partial fourth

**The baseline:** §4, *"Eight actor types, established from day one."*

**The tree:** `TENANT_TYPES = ("employer", "course_provider", "personal")`
(`api/modules/identity/models.py:22`). So: Candidate (the personal tenant), Employer, Course
provider. Then `users.is_staff` (ADR-042, Sprint 28) is a **partial** Platform admin: it grants
`OPS_ORG_READ` and `OPS_ORG_VERIFY` and nothing else, where §4 describes platform admin as
*"seeds inventory, imports taxonomy, moderates providers"* — all three of which are scripts run
with database credentials, not a role anybody holds.

Absent entirely:

| Actor | What would be needed |
|---|---|
| Assessment provider | The whole assessment integration. Also the reason three of four `SKILL_SOURCES` have no writer — see the postscript. |
| Government agency | Bulk enrolment, programme-scoped reporting. No model, no route. |
| Super admin | `is_staff` is one flag with no tiers; ADR-042 deliberately gives it no HTTP writer. |
| External system | No API-key authentication and no `ServiceAccount` model, though §8.3 names one. |

**Standing:** correctly sequenced — §4.1 says B2C first — but "established from day one" describes
the *multi-tenancy* (which is genuinely there, ADR-010/038) rather than the eight actors.

### 6. A course provider cannot see what the market is short of

**The baseline:** §4's actor table, course provider: *"Publishes courses anchored to Qualification
Packs; **sees which skills the market is short of**."*

**The tree:** `scarce_skills` exists (`api/modules/matching/employer.py:357`) and takes a
`tenant_id`, filtering to `Job.tenant_id == tenant_id`. It answers *"which standards do **my**
vacancies need that few candidates hold"* — an employer's question. It is surfaced on the employer
overview only. A provider's workspace has no equivalent, and `PUBLISHES` would refuse them the
employer route.

**Standing:** the demand side of the feedback loop §2.1 describes as the training provider's
missing signal. Not built, and not currently in any queue.

### 7. `SkillRelation` — "most of the long-term value" — is not built

**The baseline:** §5.2 argues the taxonomy is a *graph* rather than a tree because of two things:
skill aliases and **typed, weighted skill relations**. *"These edges are what make inference
possible ... and they are the substrate the career-path engine will later traverse."* It says the
two structures *"carry most of the long-term value"*.

**The tree:** aliases are real (`SkillAlias`, 298 rows, and they carry the Hindi that Sprint 23's
role search leans on). `SkillRelation` appears once in the codebase — in a comment at
`api/modules/skills/models.py:38` — and has no model, no table and no migration.

**Standing:** the closest thing built is `skill_concepts` (Sprint 9), which groups rows that *mean
the same thing* — an equivalence grouping, not a typed edge. It does real work in matching, and it
is not a prerequisite graph. Inference and ADR-008's career paths are both downstream of edges that
do not exist.

---

## Where the baseline is accurate, and it is most of it

Worth stating, because a ledger that lists only gaps reads as a worse report than the evidence
supports:

- NSQF taxonomy as live base data, generic and idempotent — **done and exceeded**: 21,303
  standards, the full hierarchy, 4,424 qualification packs, ~614k content rows. §6.1 asked for
  three or four Sector Skill Councils to prove the pipeline; there are 43 sectors and 106 awarding
  bodies.
- Candidate profiles with proficiency and provenance — **done** (see the postscript for provenance).
- Jobs and courses decomposed into skills, from both ops seeding and self-serve publishing — **done**,
  both actors, both write paths (ADR-026).
- Skill-gap computation as a **structured object** rather than a score (§5.4) — done, and it is
  what the gap panel and the course suggestions both read.
- Identity: dual-credential, multi-tenant, one identity many roles — **done and hardened** beyond
  the baseline (ADR-038, and Sprint 25's invitations).
- Hindi and English throughout — **the interface, yes**, 1,031 keys at parity across three locales.
  **The corpus, no** — it is English-only, which §12 of `projectContextForMe.md` already states
  plainly and which is the honest caveat on the Hindi-first thesis.
- Deterministic decides and the model explains (§5.3) — **kept absolutely**: there is no LLM in the
  product at all, so no generated number can reach a score.
- "No business logic in route handlers" (§8.2) — **now fully conformant, and enforced**. The audit
  that produced this ledger found 17 violations in 107 handlers; Sprint 32 moved every one into its
  service layer and `tests/test_route_delegation.py` fails on the next one.
- Every external system behind an adapter (§8.2) — **kept**, with the caveat that only two
  integrations exist (`notifications`, `nsqf`), so the rule has not been tested by a payment or
  assessment vendor yet.
- Asynchronous work never inline in a request (§8.2) — **kept**, and now guarded:
  `tests/test_worker_schedule.py`.

---

## Postscript: the one finding that is in no document

**Three of the four `SKILL_SOURCES` have no writer outside the seed.**

`SKILL_SOURCES = ("self_declared", "inferred", "assessed", "certified")`
(`api/modules/marketplace/models.py:55`). `EVIDENCE_WEIGHT` in `scoring.py` scores them 0.6, 0.7,
0.95 and 1.0. But `assessed` and `certified` are written only by `scripts/seed_candidates.py`, and
`inferred` is written nowhere at all — it is the resume parser's output (§5.6) and the skill
inference the missing `SkillRelation` edges would drive.

So for **every real candidate**, every skill scores the 0.6 floor, and
`EVIDENCE_WEIGHT_SHARE = 0.10` of the match score is a constant. A tenth of the number carries no
information in production. The golden-set ordering that demonstrates "verified evidence outranks
self-claims" is real and passes — against fixtures that are the only rows in the system with a
stronger source.

This is not a bug: it is the assessment integration's absence, correctly sequenced, showing up in
the arithmetic. But §5.6's claim that provenance *"lets verified evidence systematically outrank a
candidate's own claims in scoring"* is, today, true only of seeded data. It is also the single
cheapest argument for why the assessment provider is the next actor worth building.
