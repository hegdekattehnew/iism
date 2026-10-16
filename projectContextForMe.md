# Project context — read this first

Working notes for Claude Code. Purpose: recover full context on a new session without
re-reading the codebase or the conversation history. Update it at the end of any session
that changes the shape of the project.

**Last updated:** 2026-10-16 · **Sprints 1–69 built and merged into `main`** (Sprints 41–50 as PRs #17–#27; 50.5 and 51 as PR #29; 52 as PR #30; 53 as PR #35; 54 as PR #38; the code review's ten fixes as PRs #39 and #40;
the roadmap documents as PR #41; 56 as PR #42; 57 as PR #43; 58 as PR #44; 59 as PR #45; the three Dependabot bumps as #46 to #48; 60 as PR #49; 61 as PR #50; the mobile sprints 62 to 66 as PRs #51 to #57); **`main` is `f07728c`** (Sprint 72 is merged as PR #63; Sprint 73, below, is built on `workspace-pass` and uncommitted), and the dev database, API, worker and web run it
(migration 0055). **Sprint 62 (M1 of the mobile app: ADR-072, BL-15.1 and BL-15.7) is merged (PR #51 and #52). Sprint 63 (M2, browse on the phone: ADR-073, BL-15.2) is merged (PR #53). Sprint 64 (M3, the candidate's side on the phone: ADR-074, BL-15.3) is merged (PR #54). Sprint 65 (M4, updates, push, links, account and a way in for store reviewers: ADR-075 and ADR-076, BL-15.4/15.6/15.8, migration 0055) is merged (PR #55). Sprint 66 (M5, store readiness: ADR-077, BL-15.5, no migration) is merged (PR #56, and the ADR register as #57). Sprint 67 (M6, candidate parity on the phone: ADR-078, BL-15.9 to BL-15.11) is merged (PR #58). Sprint 68 (a whole-product UI review, Epic B16) is merged (PR #59). Sprint 69 (scannable jobs, ADR-079, BL-16.1) is merged (PR #60). Sprint 70 (a candidate's first minute, ADR-080, BL-16.2) is merged (PR #61). Sprint 71 (role search you can trust, ADR-081, BL-12.12) is merged (PR #62). Sprint 72 (a DPDP readiness slice, ADR-082) is merged (PR #63). Sprint 73 (the hiring side's design pass, ADR-083) is built on `workspace-pass`, uncommitted.** The six-sprint MVP roadmap (§11) is complete; the mobile programme (§11, "The mobile app, Sprints 62 to 66")
is the next body of work. SEO, deployment and monetisation were deferred by the owner on 2026-10-12 and **deployment is now on the mobile launch's critical path**. K stays 500; real external integrations stay deferred.

> Every count in this file is dated. An undated number in a document that survives fifteen
> sprints is a number nobody can trust and nobody can check — the header above claimed
> "Sprints 1–5" through nine further sprints, which is how §10 came to assert the branch was
> pushed while four sprints sat on one laptop.

---

## 0. Status at a glance

*Everything here is checkable in under two minutes. Check it rather than trusting it — this file
has been wrong before, and §10 explains how.*

| | |
|---|---|
| **Branch** | `workspace-pass` (Sprint 73, **uncommitted**, 2026-10-17), cut from `main` at `f07728c`, which has everything through Sprint 72. `docs/help/` (the owner's untracked user guides) and `web/AGENTS.md` (rewritten by Next's tooling on every build) are **not** part of any change. |
| **CI** | Green on every PR through #40 (2026-10-12): Web about 1m30s, API about 3m30s, **E2E 4m43s to 5m00s**, up from 3 minutes since the phone pass and the read delay (the split is due at about 8). Read it yourself with `~/bin/gh run list --repo hegdekattehnew/iism --branch main` (§6 explains `gh`; §11 "CI facts" has the rest). |
| **Last sprint** | 73 — **the hiring side's design pass** (ADR-083, UI-14, 15, 16, 26, no migration, no new operation): **/admin** keeps the three daily queues open, folds its four reference panels (programmes, skill gap, aliases, enrolment) into rows that **load only when opened** (`next/dynamic`), and gets a tier-aware jump nav: **40.2 to 27.9 screens on a phone, targets under 44 px 181 to 0, first-load JS 698,039 to 686,248 bytes (headroom 1,961 to 13,752)**. Every **vacancy and course row** has one primary action, Edit beside it, the rest behind "More" (`RowActions`; employer-home small targets 52 to 0, provider-home 69 to 0). The pool bars say what amber means. A **support-tier operator** is no longer shown verify/revoke buttons that 403. **UI-26 was mis-stated**: bulk upload never inherited a generated description; the demonstration seed wrote 258, now written without one (`make seed` to see it); the bulk check says once per file how many descriptions are blank or short; the editors say what to write. Found by the browser: the overview's placeholder shifted the queue under it (same shape before and after now), and Playwright's `getByText("Published")` matched the new actions container (`PublishEdit`). 26 mutants. **Expert judgement with measurements, not user research; Hindi labels need a native reader; no device.** Before it: 72 — **a DPDP readiness slice** (ADR-082, migration 0056, three additive operations, 51 to 54 released): **withdrawing consent no longer means deleting the account** (Account page, web and phone: a pause, with who holds your details shown first; out of every employer pool, alert and people figure, no apply or interest, no tracking, no push, live applications and interests taken back; restore by confirming the notice); a **changed notice asks and never blocks** (a *fixed* banner: a placement in the flow measured 0.108 layout shift); the **18-and-over promise** rides on the consent sentence and an under-18 date of birth is refused; the **privacy notice was rewritten because it was wrong** (it said employers never see contact; applying shares it) and a test fails when a stored column is missing from it; a **breach runbook** (`docs/release/incident-response.md`, the law's timings left to counsel). **Pause is not erasure: a question for counsel.** Found on the way: a brand-new candidate's first page made two requests that both created the profile and one got a 500 (`ensure_profile`, fixed). Scale harness: employer shortlist p95 ~6% over `main` after a correlated `EXISTS` (+~100 ms) became an uncorrelated `IN` over a partial index; recall unchanged. 35 mutants (a redundant lock found and removed). **Not certification; no encryption at rest, nominee or dormant-account erasure; Hindi needs a native reader, the notice a lawyer; no device.** Before it: 71 — **role search you can trust** (ADR-081, BL-12.12, no migration, no new operation, no ranking change): role-alias coverage from 114 forms onto 41 roles to **307 forms onto 88** (English, romanised Hindi, Devanagari; every target a general pack, checked against the real corpus), **measured for the first time** by `make evaluate-roles` over 146 titles written before any alias (`tests/fixtures/role_titles.json`): top-1 all 65.5% to 81.7%, tuning 76.5% to 99.0%, Devanagari 43.8% to 81.2%, romanised Hindi 50.0% to 66.7%; **the hold-out did not move (37.5% top-1, 40.0% top-3 before and after): an alias covers the word it names and the ranker does not generalise**, and "accountant" still leads with a corporate-law diploma (a corpus gap). The old note that "waiter" and "mason" had no general pack was wrong (corrected). **An engineering draft nobody who works in these labour markets has read**: `docs/IISM-Role-Aliases-for-Review.xlsx` is the reviewer's copy and an admin-tier operator retires or changes any row on `/admin`. 17 mutants (the alias ones survived until the checks synced the table: `make check-role-aliases` reads the table, not the dict). **Not user research, not usage; no device.** Before it: 70 — **a candidate's first minute** (ADR-080, BL-16.2, no migration, no new operation; web and phone): a **task-first homepage** (search, five one-tap example jobs with an English query and a label in the visitor's language, the chooser under it, two links for employers and providers), the seeker-facing words **free of NSQF and framework vocabulary (a three-language test)**, and **only the framework band moved** to About (`FrameworkBand`; the owner chose that: the live people figures and browse counts stay, the "three sides" cards went); the **matches page opens on the matches** (`MatchesStrip`: "14 matches · best 87 · profile 100% complete", the charts behind "Your numbers", five cards then "Show more", "your best 50 of N" when there are more); **every match says in a sentence** what the person has and lacks (`matchSummary`, web and phone, one fixture `tests/fixtures/match_summary_cases.json`; generic standards left out, said so), one main action, the report behind Details; the **phone's signed-in home** is the person's own (`SignedInHome`: best match, completeness and next step, updates, applications with news in the last 14 days; no apply there). **Found on the way: `GET /me/matches` `total` was the page length; now the count** (`match_jobs_with_total`). Measured with the review's script: `/matches` 15 to 4 screens, small targets 45 to 1, tiny text 215 to 0; the homepage 7.7 to 6.0 (the plan said about 5). 30 mutants (one survivor, a real gap, closed). **Not user research; Hindi copy needs a native reader; not run on a device.** Before it: 69 — **scannable jobs** (ADR-079, BL-16.1, no migration; web and phone): cards that say what, who, where, how much **a month** and by when (no NSQF badge, no generated sentence, a verified mark and **never a "not verified" on a card**); `/jobs` and `/courses` page 24 at a time with the **server's** total and a state filter that is the catalogue's own (new `GET /jobs/states`); an apply bar that follows the thumb (web: `order-last sticky bottom-0`, resting above the footer; phone: `Screen footer`, none for an account that cannot apply); each standard once in sentence case, generic ones under "Also covered"; a trust strip (verified / not yet verified, never pay to apply); nothing under 12 px and the header and footer at 44 px, **asserted on every page of the browser sweep**; **both operator queues return `{items, total}`** and the screen says "Showing 100 of 162". Shared rule files `tests/fixtures/pay_cases.json` and `requirements_cases.json` are read by both clients' tests. **Measured with the review's script**: `/jobs` 42.3 to 7.5 screens, `/courses` 53.4 to 8.8, text under 12 px 296 to 0 (every page), targets under 44 px on `/jobs` 15 to 0; baseline kept (`measurements.json`) beside the new `measurements.sprint69.json`. 37 mutants (two survived, each a real test gap, closed). **No posted date** (the payload has none: needs a `published_at` migration). **Not user research, not a device.** Before it: 68 — **a whole-product UI review** (Epic B16; no migration, no ADR, one small fix): 29 findings from a production web build, the phone app and the back office, each with a screenshot or a measurement, a severity and an effort (`docs/design/ui-review.md`, `IISM-UI-Review.xlsx`, `design-system-plan.md`, `docs/design/screens/`, scripts `web/scripts/capture-review.mjs`, `capture-app.mjs`, `scripts/build_ui_review.py`). **Headlines**: the product is an expert's tool (homepage 7.7 screens; job cards like database rows; pay per year; skills in capitals; no image on any page; icon-less tab bar; 15+ tap targets under 44 px on every web page); **three silent caps** (jobs and courses at `limit=200`, the operator's queue at 100 printed as the total against 162); brand and launcher art are the owner's. **Recommended**: Sprint 69 "scannable jobs" (UI-04 to 11, 17), a five-person usability check, Sprint 70 "a candidate's first minute". Also fixed: a Sprint 67 defect (a 100% match showed the budget and "no course covers this gap"). **Not user research.** Before it: 67 — **M6 of the mobile app: candidate parity** (ADR-078, no migration, no endpoint, BL-15.9 to BL-15.11): the **six history sections** of the profile (work, education, certificates, languages, roles you want, places) through **one table-driven editor whose limits `tests/test_mobile_section_limits.py` compares with the server's schema**, **"why not me"** on a rejected application (`/gap/[id]`), **career paths** (`/careers`), the **course budget** (device-held, sent as `?budget_inr=`, forgotten at sign-out) and the profile's salary, notice, work type, relocation and alert fields. **Date of birth and gender stay web-only.** Five operations joined the released surface (46 to 51; the old 46 byte-identical). Housekeeping: four ADR headers corrected, `scripts/build_adr_register.py` and `tests/test_adr_register.py`. **601 mobile tests**, 1,818 backend, 27 mutation checks (one survivor exposed an untested claim about key prefixes), run in a browser in both languages against the real API. **Not run on a device.** Before it: 66 — **M5 of the mobile app: store readiness** (ADR-077, no migration, BL-15.5): a **release build refuses to start** on a missing, `http://` or local origin (`core/release.ts`, a plain "not set up correctly" screen); `eas.json` (`preview` and `production`, origins and store links per profile, never a default), a hardened `app.json` (one Android permission, encryption declared, splash, Face ID string removed; verified by `expo prebuild` in a scratch copy); **`make check-release`** reports defects and every decision still open (**`PROFILE=production` fails today on thirteen**: bundle id, the Expo template's artwork found by hash, no EAS project id, placeholder origins and store links, the grievance officer); a size ceiling (`make check-mobile-budget`, 3.43 of 3.8 MB); an accessibility pass held by tests (48 dp, roles and names, text capped at 200%, `mobile/ACCESSIBILITY.md`); `docs/release/` (the listing in English and Hindi, Data Safety answers checked against the export, reviewer notes, a runbook); four Expo patch packages updated (`expo-doctor` 21/21) and `expo-splash-screen` added. **499 mobile tests**, 1,798 backend, 27 mutation checks, the release screens run in a browser. **Nothing has run on a device, in an EAS build or in a store console.** Before it: 65 — **M4 of the mobile app: updates, push, links, account and a way in for store reviewers** (ADR-075, ADR-076, migration 0055, BL-15.4/15.6/15.8): the person's **updates** (every notice, paged, the website's own words, the number that are new in the Me tab's label), **export** through the share sheet and **delete the account** from inside the app, **contact the team** with the status of what was sent, **report a vacancy or a course**, `iism://` links through one table (`core/links.ts`), an **invitation link that hands off to the website**; **push built except real delivery**: `device_tokens` (a token belongs to one person at a time, in the export without the token, erased with the account), a **`pushed_at` stamp swept by the worker** (not a channel: a first design queued a companion row and failed the alert-sweep statement-count test), fixed words that take **nothing from the payload**, a console provider that refuses production; **reviewer login**: named phones, a fixed code, off by default, refused for staff and organisation members, `scripts/create_reviewer.py`. **473 mobile tests**, 1,758 backend, 53 mutation checks (52 killed, one equivalent), the real screens run in a browser, push and reviewer login verified against the real worker and API. Before it: 64 — **M3 of the mobile app: the candidate's own side** (ADR-074, no migration, BL-15.3): Matches and Me tabs; match detail with the score, the gap (required standards first), what caps it and the suggested courses; one Apply panel (confirmation naming what is shared, withdraw while undecided, save) on the vacancy page and on a match; applications with the employer's message; saved vacancies; course interest; the profile basics and the **role picker** (name a job, tick what you hold, nothing pre-ticked). Everything personal is keyed `["me", ...]`, in memory only, and dropped whole at sign-out. **329 mobile tests**, 43 mutation checks, both bundles reach Hermes bytecode, and the real screens run in a browser as two seeded candidates. Before it: 63 — **M2 of the mobile app: browse on the phone** (ADR-073, no migration, BL-15.2): Home, Jobs, Courses and Standards tabs, three details and a search, all without signing in; a remembered language; a public-only offline cache (allow-list keyed `["public", locale, ...]`); money and dates formatted without `Intl`. **329 mobile tests**, both platforms bundle to Hermes bytecode, 28 mutation checks, and the real screens run in a browser through `react-native-web` (not native, not Hermes). Before it: 62 — **M1 of the mobile app: foundations** (ADR-072, no migration), **partly verified**. `mobile/` is an Expo / React Native job-seeker app **in this repository** (no fork, no rebaseline). Verified: `AppVersionMiddleware` (**426 Upgrade Required** to a build below `MOBILE_MIN_VERSION_ANDROID/_IOS`, fails open, `/health` exempt), `api/core/contract.py` + `mobile/contract/{surface.txt,openapi.snapshot.json}` + `scripts/check_api_contract.py` (`make check-contract`, `make snapshot-contract`: additive-only for the operations the released app calls), `make gen-api-mobile`, `make sync-mobile-messages`, `scripts/sync_mobile_tokens.py`, and `mobile/src/core` (the API client, token store, sign-in flow; strict `tsc` and 39 tests using the **web's** TypeScript and Vitest). **Completed on `mobile-bootstrap` (the owner allowed the install): the whole app compiles under strict `tsc` (one type error found and fixed), passes `eslint`, bundles for Android and iOS with Metro, and passes 53 Jest tests under `jest-expo` (the 39 core tests plus the sign-in and home screens rendered against the real catalogues); `make mobile-check` and a `mobile` CI job run them. Still never run on a device or emulator.** Before it: 61 — a pilot with an agency (ADR-071).
| **Next sprint** | **The mobile programme's code is done.** What stands between it and the stores is the owner's, and `make check-release PROFILE=production` names it: **the app's name and bundle id, real artwork (the icons and splash are Expo's template), the Apple and Google accounts, an EAS project id, a deployed HTTPS API and website, a domain for App Links, a real push vendor, real SMS (DLT), the appointed grievance officer, legal review of `docs/release/`**. The first run on a phone (README, "Run it", five minutes with Expo Go; `mobile/ACCESSIBILITY.md`'s checklist) is the first unchecked risk to retire (Hermes, scrolling, TalkBack), and a third mobile sprint exists only if it finds defects. The remaining web and platform backlog is unchanged (§11). *The old M5 line, kept for the record:* M5 (Sprint 66): store readiness and release (BL-15.5): icons, splash, store listings in English and Hindi, the privacy and data-safety answers, TalkBack/VoiceOver and low-end checks, a release runbook, domain-based links. **Blocked on the owner**: the Apple and Google accounts, the real bundle id and name, an EAS project id, a deployed API, and a real push vendor. An owner run of the app on a phone (README, "Run it", five minutes with Expo Go) is the first unchecked risk to retire (Hermes, scrolling, TalkBack). Prerequisites that are the owner's: the app name and bundle id, the store accounts, deployment, SMS/DLT (§11 "The mobile app"). `BL-1.3` stays not started. |
| **Tests** | 1,913 backend (`make check`, 2026-10-16), 714 web (`cd web && npm test`), **134 browser tests** (`make e2e`), **697 mobile tests** (`make mobile-check`: `tsc`, `eslint`, Jest, an Android Metro bundle, the size ceiling) — and `cd web && npx tsc --noEmit` plus `npm run lint`. First-load budget: `/admin` **680 of 684 KB**, `/profile` 678 |
| **Migrations** | head `0056` (applied to the dev database `iism`; Sprint 72 added `users.consent_withdrawn_at`; the scale database `iism_scale` was migrated to it too); 83 ADRs (001-083) |
| **Golden set** | `make evaluate` must print **all 34 golden pairs, 7 orderings and 16 course expectations hold** — note the *numbers* behind several `CAPPED` cases dropped this sprint (e.g. the visual-merchandiser case fell from 45 to 31) because the mandatory-gap cap now tapers with thin coverage; the orderings and booleans are unchanged by design |
| **Deployment** | deferred by the owner; nothing is deployed anywhere |

**To get running** (Docker must be up; ports are non-default — 5433 / 6380 / 27018):

```
make up && make migrate && make import-nsqf && make seed    # first time, ~2 minutes
make api        # :8000   — reloads on change
make worker     # does NOT reload: restart it after any api/ change
make web        # :3000
```

**Demo logins** (all seeded, `OTP_EXPOSE_IN_RESPONSE=true` returns the code in the response):
`hiring@apollo-care.example` (employer, 5 applicants, **and a three-person team**),
`admin@skillbridge-institute.example` (provider, interested learners), `+919000000001`
(candidate with matches and a gap). Never sign in as the owner's real number, `+919880663641`.
Apollo Care is the only seeded organisation with more than one member — a second owner, an admin
and one pending invitation — so `/employer/apollo-care-hospitals/team` is where Sprint 25 demos.

**Sessions last 15 minutes and now refresh silently** — before 2026-09-23 they did not, because
the refresh guard matched `/auth/me` by substring. If a signed-in screen ever looks like it has
revoked your rights, check `/auth/refresh` is being called before believing it.

**The three things most likely to waste an hour**, all in §8: the worker not reloading, a stale
API process serving old code, and `make check | grep` reporting grep's exit status rather than
the suite's.

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
| `docs/adr/architecture-decisions.md` | **65 ADRs — the source of truth for every design decision.** Read before any structural change. |
| `docs/IISM-Product-Definition.docx` | 20-page product definition: problem, actors, intelligence layer, scope, risks, decision appendix. Written for the founding team, deliberately candid. **Read the next row with it.** |
| `docs/scope-reconciliation.md` | **Where the product definition and the tree disagree** (2026-09-24). Seven divergences, each naming the file that proves it — semantic similarity, weights-in-configuration, dismissal instrumentation, course↔role alignment, five of eight actor types, the provider's market signal, `SkillRelation`. The `.docx` is deliberately not amended; this sits beside it. **A status table at the top (2026-10-03) says where each stands now**: five closed or mostly closed, two partly closed; the body is left as written. `docs/IISM-Scope-Reconciliation.docx` is the same ledger rewritten for top management (executive summary, scorecard, decisions requested, what to say plainly); regenerate or edit it when a gap's status changes. |
| `docs/IISM-Product-Backlog.docx` | **Every story's status** — done, in progress, to do (Now / Next / Later), waiting or deferred. Version 1.23 (2026-10-14) adds Epic B15 (the mobile app) and records Sprint 62 (M1) as done, compiled and tested but not run on a device, on top of the completed Sprint 56-61 roadmap on top of a status-at-a-glance table, Epic 13 (what shipped in Sprints 33–42), Epics B11–B13, and §4.4 with a proposal for the next sprint. It had stopped at Sprint 38 and still tagged the dashboards `[NOW]`. **Update it when a story's status changes** — it went five sprints stale once. |
| `CLAUDE.md` | Working conventions, repo layout, current state. Auto-loaded each session. |
| `README.md` | Setup and run instructions. |
| `~/.claude/plans/i-want-to-create-lively-phoenix.md` | **The most recent sprint plan** (overwritten each sprint — currently the Sprint 61 plan; the roadmap is mirrored in §11 and in the backlog's section 4.4). Lives outside the repo. |
| `docs/nsqf-source-data-findings.md` | **Everything measured about the NSQF corpus** — field-naming traps, level distributions, content volumes, deduplication rates, translation costs, data-quality issues. Read before touching the importer. |
| This file | Session-to-session continuity, environment quirks, hard-won gotchas. |

ADR-001–023 came from a March 2026 spreadsheet. **ADR-024–035 were written in this project
(Sept 2026)** and cover: multi-sector scope, monetization deferral, supply acquisition, ARQ over
Celery, AWS topology, Next.js client, in-house identity, AI provider abstraction, dual credentials,
language scope, the NSQF source of record (034), and selective ingestion — why the PII-bearing
`ssc` collection is deliberately not imported (035). Three repairs were also made: ADR-014's malformed status, ADR-015 marked superseded,
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

*This section's sprint-by-sprint record stops at Sprint 24. Sprints 25–27 are written up in
`CLAUDE.md` → Current state; Sprints 28 onward are in §11 below. Read those for anything recent.*

**Sprint 24 (somebody is interested) — complete, 2026-09-21.** Deployment deferred; the question was
which functionality is worth most, and a scan across all three actors found one that got nothing at
all. A learner shown "the courses that close your gap" could not act on one — no enrol, no enquiry,
not even the provider's website that the API already returned — and providers published into
silence. Now a learner registers interest (sharing name, contact, district and a note with that
provider, revoked on withdrawal), the provider gets an inbox, a roll-up of which courses people
want, and the first notification they have ever received. `api/modules/interests/` is a sibling of
`applications/`; the provider payload has **no score**, because a course publishes what it teaches
and inventing a scorer for it is what ADR-037 forbids. Migration 0025. Two defects fixed alongside:
`course_recommended` was recorded against the job with a bare count (ADR-025's click-through has
been uncomputable since Sprint 10 — now one row per course, carrying `from_job`), and
`_delete_tenant` never deleted applications explicitly. 527 backend and 89 web tests. **Still open:**
teammate invitations and the sole-owner trap (agreed as the next sprint — a sole owner deleting
their account still destroys the organisation and every application to it); a learner-facing notice
when a provider marks "contacted"; vacancy lifecycle; `is_verified` still has no writer.

**Sprint 23 (say what you do, and we'll name the standards) — complete, 2026-09-18.** Asked as "should
a CV populate the profile?"; answered by finding that only `candidate_skills` changes a score, and
that the only way to add one was naming a National Occupational Standard nobody can name. A CV would
have filled experiences and education, which no scorer reads. Now a candidate types their job ("ward
boy", "ड्राइवर"), the qualification behind it names its standards, and they tick what they can do —
one request, written `self_declared`, nothing pre-ticked. A curated alias map bridges colloquial
titles the corpus does not use (**awaiting labour-market review**). Profile location now resolves on
save; experience enters the score by a split of the level weight that is neutral for anyone who
fits (golden set bit-identical); locality orders equal scores and never changes one. Migration 0024
(trigram index on `job_role`, two analytics names); `migrations/env.py` repaired — it would have
dropped the live skill trigram index. 501 backend and 66 web tests; verified in the browser as a
brand-new account in English and Hindi. **CV upload deferred** until the residual gap is visible.
**Follow-up the same day:** the homepage search now lands on `/search` — open jobs, then roles, then standards — instead of the standards browser, and every standard card shows its code, level and the qualification it belongs to, flagging same-named results. **Found, not fixed** (task raised): three district names exist in two states and resolve
arbitrarily, and every NSQF import rewrites every profile's `updated_at`.

**Sprint 22.5 (demo readiness) — complete, 2026-09-17.** No new product surface: the readiness
check before demoing found that the whole of Sprint 21 could not be shown cold, because all six
seeded applications sat in organisations **nobody could sign in to**. All ten seeded organisations
now have owner accounts on the reserved `.example` domain, provisioned the way the product does it;
sixteen applications spread across all five employers in mixed states; fifty courses instead of
twenty, chosen so that **every mandatory standard across the twenty vacancies is taught by at least
one course** (two were taught by none, and their gap panels were empty). Thirteen leftover fixture
organisations were removed by `scripts/clean_fixtures.py` — explicit slugs, `--dry-run` by default,
**no account deleted**. Malay is hidden from the switcher and still routed. The browser walkthrough
found one real defect: the employer's inbox rendered `employerConsole.matchScore` as text, because
that key only ever existed in `matchesPage`; the test harness now fails on any missing key and the
inbox has its own test file. Verified: `make seed` twice identical, the coverage query, `make
evaluate` unmoved, 440 backend and 56 web tests, and a cold-start walkthrough in both languages.
**Still open:** publishing a listing in two languages, notification preferences, a real email
provider, deployment, and per-country taxonomy (needs its own ADR first).

**Sprint 22 (many languages, and something arrives) — complete, 2026-09-17.** Two problems, both
visible only once someone looked. The language switcher was two tabs, and under it the product was
bilingual by construction: 18 `_en`/`_hi` column pairs, 16 API fields, 37 client ternaries. Now the
base column holds the row's own text and every other language is a row in `content_translations`
(ADR-041, migrations 0021–0022) — 187 rows moved, adding a language is INSERTs. The API negotiates
the language and the client renders what it is given; a Malay skeleton ships as a third locale so
the machinery is exercised beyond two. And the loop Sprint 21 closed no longer closes silently: an
outbox (0023) queues an email to the employer when somebody applies and an in-app notice to the
candidate when their status changes, drained by an ARQ cron. **Migration 0022 was rehearsed against
a full copy of the development database** — three GENERATED search vectors had to be dropped and
rebuilt. **Still open:** publishing a listing in two languages (the employer editors lost their
Hindi inputs), notification preferences, and translating the corpus itself.

**Sprint 21 (the loop closes) — complete, 2026-09-17.** The marketplace can finally produce an
outcome. A candidate applies to a vacancy (sharing name and contact with that employer, for that
vacancy, recorded as consent), withdraws (which takes the contact back and keeps the row), and saves
vacancies privately. An employer sees who applied, ranked by the same scorer, with the contact
details to act on, and moves each one to shortlisted, not suitable or hired. Export and erasure
cover both new tables; a rolling 24-hour cap answers spraying. Migrations 0019 (applications,
saved_jobs) and 0020 (four analytics names). Seeded candidates gained work histories and six demo
applications, so a fresh machine shows a profile and an inbox with something in them. **Verified end
to end against the running API and in the browser in both locales.** Details in `CLAUDE.md`.
**Still open:** teammate invitations, membership removal and `is_verified` still have no writer;
deployment moved to Sprint 22.

**Sprint 20 (safe to deploy) — complete, 2026-09-11.** No new product surface; the NFR gaps that
need no outside account, closed before the first deployment. Consent recorded server-side at
signup (DPDP Act 2023), self-serve export and deletion at `/account`, privacy notice / terms /
grievance pages in both languages **marked draft pending legal review**, analytics purged after
12 months. Security headers on API and web (web CSP enforced in production builds since Sprint 54), rate limiting on every class of
request, body-size cap, `/docs` local-only, DB pool and statement timeout. Encrypted backups outside
the tree, **MongoDB covered for the first time**, restore drill run and passed. `uv.lock` committed
and CI installing from it, dependency audits and Dependabot, a first-load JS budget, axe checks,
error pages that say "unavailable" instead of 404, and the employer overview's N+1 gone. Details in
`CLAUDE.md` → Current state. **Still open, needing the owner:** a named grievance officer
(`web/src/lib/legal.ts`), legal review of the three pages, and the pull request.

**Sprint 19 (every door opens onto all three) — complete, 2026-09-11.** The registration page at
`/signup/[type]` now switches between job seeker, employer and training provider in place, instead
of committing whoever arrived to the type in the URL. Links, not a toggle; the form is keyed so
switching gives a clean one. No backend change — registration already handled all three.

**Sprint 18 (one identity, honestly) — complete, 2026-09-11.** Prompted by three defects found by
hand: "profile" inside an organisation opened the candidate editor; re-registering an existing
number silently signed you in; there seemed to be no way to be only an organisation. All three
were one defect, and a scan found seven more — most seriously that `POST /auth/org/register` forked
a signed-in candidate into a second account, which Sprint 16's homepage chooser had made easy to
reach. Fixed and verified end to end in a browser; `web/` gained its first test runner. Details in
`CLAUDE.md` → Current state. **Still open:** nothing can remove a membership, so an account that
already has a personal tenant stays a job seeker; no organisation can add a second member; and
`is_verified` has no writer.

**Sprint 17 (logging you can run a customer on) — complete, 2026-09-10.** One structured JSON stream
on stdout for the API, the worker and stdlib loggers alike (ADR-040), a redaction filter in the
shared processor tail that masks phones, emails and OTPs so no logger can route around it (ADR-023),
and a request id, user id and tenant id on every line. The worker's heartbeat noise (~34,500
lines a day) was silenced by pinning `arq.worker` to WARNING. Details in `CLAUDE.md`.

**Sprint 16 (who is this for) — complete, 2026-09-10.** The homepage now says which three roles the
marketplace serves (a role chooser beside the hero), the job-seeker landing makes clear where you
are, and the header switcher names contexts instead of saying "Switch". Also found and fixed:
`BrowsePanels` and `Audiences` had sat unpadded on the homepage for four sprints after the `Card` /
`CardBody` rename, and `divide-y` emits no border width in this build. The hero's fold budget is
measured in Hindi, the binding case. Details in `CLAUDE.md` → Frontend conventions.

**Sprint 15 (consolidation) — complete, 2026-09-09.** No new product surface. The push, the
deletions, the shared-policy extraction, three new test files, and this document made true.

*Counted live on 2026-09-09.* Database **557 MB** (not the 485 MB written here for three sprints).
`skills` 21,355 · `skill_aliases` **298** (not 149 — the importer carried more than the seed) ·
`skill_concepts` 18,958 · `qp_entry_routes` 14,405 (the table is `qp_entry_routes`; this file
called it `entry_routes`) · `tenants` 49 · `users` 38 · `memberships` 40 · `jobs` 23 · `courses` 21
· `job_skills` 91 · `course_skills` 66 · `candidate_profiles` 34 · `candidate_skills` 90 ·
`analytics_events` 41. **39 ADRs**, 17 migrations.

The tenant count is lower than it was mid-sprint because verifying the journeys end to end left
throwaway organisations behind, and clearing them also removed **11 orphaned personal tenants**
from earlier sessions — rows with no membership at all, which no account could reach. Worth
knowing if a number here looks smaller than a memory of it: the seed is the floor, and everything
above it is journey debris.

**Scale, with the generated code separated out** — because quoting a gross figure to anyone
technical invites exactly one question, and it should be answered here first:

| | files | lines | |
|---|---|---|---|
| `api/` | 68 | 9,861 | authored |
| `scripts/` | 7 | 2,484 | authored |
| `tests/` | 18 | 4,170 | authored |
| `migrations/` | 18 | 1,714 | authored |
| `web/src/` excl. generated | 92 | 8,197 | authored |
| `web/src/lib/api-schema.d.ts` | 1 | 4,675 | **generated** — `make gen-api` |
| `web/src/messages/*.json` | 2 | 1,556 | authored (650 keys × 2 locales) |
| `backups/schema.sql` | 1 | ~2,127 | **generated** — `make db-schema` |
| `web/package-lock.json` | 1 | ~8,100 | **generated** — npm |

So roughly **26,400 lines of authored code**, of which 4,170 are tests. Anything that quotes a
number near 40,000 is counting a file a tool wrote.

**Five of the six rich-profile collections are empty.** Sprint 5 built experiences, educations,
certifications, languages, preferred roles and preferred locations; across all six the database
holds **one row** (an experience). The schema is real, the generic route and editor are real, and
`tests/test_profile_sections.py` exercises them — but nothing has ever put data through them at
volume, and no seeded candidate has a work history. That is a fact about the seed, not the code,
and it is the reason a demo of the profile wizard looks thinner than the schema behind it.

**What Sprint 15 found, which is more useful than what it deleted:**
- `record()` raised `TypeError` on an unknown event name, from above the `try/except` that exists
  to absorb exactly that, and its docstring says "Never raises". `log.warning(..., event=name)`
  collides with structlog's own first positional argument. `analytics/` had no test file; writing
  one found it in the first run. The same collision sat in the `except` branch.
- Three of eight publishing writes had no tenant-type guard while `CLAUDE.md` asserted all eight
  did. Fixed structurally, not by adding three call sites.
- Two profile columns were closed `Literal` unions on a response model with no CHECK behind them
  (migration 0017). Found by writing the test that asserts unions and constraints agree.
- The seed never resolved geography and relied on a backfill that runs **before** the rows it
  fixes exist. A clean `make import-nsqf && make seed` left every seeded job invisible to
  location-filtered matching.
- 37 dead message keys per locale, `orgAuth` entire. The audit produced two rounds of false
  positives first; **do not delete an i18n key on a grep alone** (§8).

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

**Sprint 6 (NSQF master data) — built, then rolled back** on 2026-09-04. The audit that prompted
it is in [docs/nsqf-source-data-findings.md](docs/nsqf-source-data-findings.md).

**Sprint 14 (three ways in, one way back) — done** on 2026-09-08. Prompted by the observation that
the product looked job-seeker-first and would "restrict an identity who wants only to come to either
hiring people or provide training". Partly true, and the audit found worse.

- **An employer-only identity was already possible** — `/auth/org/register` creates a user with an
  employer tenant and no personal workspace. The problem was discoverability: every homepage route
  to an account went to the candidate phone form, and `/employers/signin` sat two clicks behind a
  marketing page.
- **A training provider could not register at all.** `OrgSignInForm` hardcoded
  `tenant_type: "employer" as const`. The API had accepted `course_provider` since Sprint 12; no UI
  could produce it.
- **And a provider account led nowhere.** No write path for `Course` existed anywhere in `api/`. A
  provider got an employer's heading, a nav reading "Vacancies", and a "New vacancy" button whose
  save returned 403 into a mutation with **no `onError`** — so the form sat there having silently
  done nothing. A `course_provider` tenant with a member and zero courses already existed in the
  database when this started.
- **`/org/{slug}/candidates` answered 200 to providers** with two empty arrays and
  `candidates_total`, which has no tenant filter. The only number on the screen was a global count
  of every candidate on the platform, presented as a pool they could reach.
- **Pushed back on one half of the request, and the reasoning held up.** The proposal was to fork
  *login* by user type as well as registration. ADR-032's rule is about the credential at
  registration; after Sprint 13 one identity holds both credentials, so at sign-in the credential no
  longer identifies anyone. Two doors would punish exactly the people who linked both. Registration
  is type-aware; sign-in detects an `@` and routes on what the account holds.
- **Course publishing is a sibling of job publishing, not a generalisation.** `CourseSkill` carries
  only `level_taught`, so duplicates collapse on the **highest level** where a job's collapse on the
  strongest signal. Resisting the urge to unify them is the point.
- **No migration.** Everything needed already existed in the schema — the first sprint in six that
  did not touch it.
- **A stale Turbopack cache cost ten minutes.** Every page 500'd with a `JSON.parse` error at a fixed
  byte offset while `npm run build` passed cleanly. `rm -rf web/.next` fixed it. Suspect the cache
  first when the build disagrees with the dev server.
- **Its second disguise (Sprint 16) is a hydration mismatch.** Fast Refresh updated the *client*
  bundle and left the *server* module graph behind, so one `<a>` was server-rendered with the old
  `href` and client-rendered with the new one — reported as "some attributes of the server rendered
  HTML didn't match the client properties", which reads like a bug in the component and is not one.
  **The tell is that the React diff shows two values you recognise as the before and after of your
  own edit.** Same fix: stop the dev server, `rm -rf web/.next`, restart. Do not add
  `suppressHydrationWarning` — it would hide the real ones.

**Sprint 13 (multi-tenancy you can see) — done** on 2026-09-07. Prompted by a single observation:
*"I was expecting an option on the frontend to change tenancy after login."* There wasn't one, and
auditing why turned up more than a missing control.

- **The Sprint 12 plan said "the header gains a switcher" and I built it inside `EmployerWorkspace`
  instead, without flagging the deviation.** That is the root of everything below. A switcher inside
  the page is invisible to anyone who has not already reached the page, and `/employer/{org}` had no
  inbound link from anywhere a signed-in person could be — its only entry was a one-shot
  `router.push` at the moment of email verification.
- **A candidate's personal tenant resolved as an organisation context — a real hole, mine.** Every
  candidate is `owner` of a personal tenant, `_context_for` filtered on membership and slug alone,
  and `owner` carries `JOB_CREATE`, `JOB_PUBLISH`, `CANDIDATE_SHORTLIST`. Confirmed against the
  running API: `GET /org/personal-…/candidates` returned **200**. It returns 404 now. The lesson is
  narrow and worth keeping: *a permission set answers "may this person act here", never "is this the
  right kind of place".*
- **The only visible "create an organisation" path created a second account.** It posts
  `/auth/org/register`, which mints a new `User` for an unknown address. So the one affordance a
  candidate could find produced exactly the outcome ADR-038 exists to prevent, while
  `POST /me/organisations` — which does the right thing — was called from nowhere in `web/src`.
  Endpoints without an interface are not features; they are tests that happen to pass.
- **Sign-out did not clear the TanStack cache.** The `QueryClient` outlives the session, so the
  previous person's profile, matches and memberships stayed in memory for whoever signed in next.
  On a shared phone that is the same problem the service worker's DENY list exists to stop.
- **Circular import when identity started importing `core.authorization`.** `authorization` imports
  identity's models, and importing a submodule runs the package `__init__`. Solved the way
  `get_current_user` already solves it: `TYPE_CHECKING` for annotations, a local import inside the
  function for runtime.
- **`TenantOut` is embedded in every public job and course payload.** Any column added to it is
  published. `contact_email` therefore lives on `OrganisationOut` only.
- Still true and still deliberate: `CandidateProfile` is 1:1 with `User`, not with a tenant. A
  person's skills are theirs; forking them per employer would fragment the history the matching
  engine scores against.

**Sprint 12 (one identity, many roles) — done** on 2026-09-07. Organisation identity, the
authorization primitive both ADR-012 and ADR-022 had described for eleven sprints without anyone
building it, and self-serve job publishing. ADR-038 and ADR-039. 233 tests. 557 message keys per
locale.

What a future session should not have to rediscover:
- **A person is not an actor type.** The multi-role case is the load-bearing design decision, and it
  is cheap now and expensive later: every org-scoped query depends on how the active tenant is
  resolved. It comes from the request path and is granted by the membership — never from the token,
  never from a request body.
- **404, not 403, for an organisation you are not a member of.** A 403 confirms it exists, and an
  employer could enumerate competitors by guessing slugs. Inside an organisation you *do* belong to,
  an insufficient role is a 403.
- **Registration had a readable enumeration oracle and it was caught by running the flow, not by
  reading it.** The first version sent a "you already have an account" note instead of a code, so
  the two responses differed by one field whenever `expose_otp` was on. It now sends a real sign-in
  code and creates no second organisation — indistinguishable, and friendlier.
- **`scripts/seed_candidates.py` was creating a personal tenant with no membership.** Invisible for
  four sprints because nothing read `Membership`. It now provisions through the real sign-in path,
  so seeded candidates are shaped like real ones.
- **`Job.status` defaults to `"published"` in the model.** Every create path must set `draft`
  explicitly. This is a footgun aimed squarely at the code this sprint added.
- **Geography resolved only inside the NSQF importer's backfill.** A job created through the API had
  a NULL `state_id` and was invisible to location-filtered matching while appearing normally at
  `/jobs` — the worst kind of bug, because nothing looks wrong. Resolution moved into
  `api/modules/geography/service.py` and happens on write.
- **`SkillOut` carried no `nos_code`**, so a picker could show three standards with identical names
  and no way to tell them apart. Verified in the browser: searching "infection control" returns
  three rows named the same, distinguishable only by `MSU/HSS/CRS0093-004` and friends.
- **A design-system `Button` defaulting to `type="submit"` is a footgun.** The picker's Add button
  saved a half-written vacancy instead of adding a standard. `Button` now defaults to
  `type="button"`; every form already declared its submit explicitly.
- **next-intl reads a dot as a namespace separator**, so `"employment.full_time"` as a flat key
  renders as the literal key string on screen. It must be a nested object.
- **The Sprint 11 mount guard was wrong** and I wrote it: `environment == "production"` mounted the
  unauthenticated console on staging, on CI, and anywhere `ENVIRONMENT` was unset. It is an
  allowlist now, and `/health` reports it — which the old comment falsely claimed it already did.
- **`email-validator` rejects the reserved `.test` TLD**, which is exactly the sort of thing a
  hand-written address regex waves through. Test fixtures use an ordinary domain.

**Sprint 11 (make it sellable) — done** on 2026-09-07. Six parts, in the plan's must-land order:
a component library, the landing page proving scale from live counts, the employer console, an
installable PWA, match visualisation, and real content on the three audience routes. Migration 0015
(the analytics event CHECK). ADR-037. 208 tests. 487 message keys in each locale.

What a future session should not have to rediscover:
- **The shadcn CLI was tried and reverted.** It adds a second dark-mode mechanism (a `.dark` class)
  beside the `prefers-color-scheme` one already in `globals.css`, 62 duplicate oklch tokens
  including `--background` / `--foreground` / `--border`, a Geist font override in `layout.tsx`, and
  installs `cn` and `shadcn` as runtime dependencies. Its components would have rendered light
  inside this app's dark theme. Radix primitives plus `cva` over the existing tokens, directly,
  cost about a day and owe nothing.
- **`buttonVariants` must not live in a `"use client"` module.** Exporting the cva from
  `button.tsx` broke prerendering of every server component styling a button:
  `Error: Attempted to call buttonVariants() from the server`. It lives in `button-variants.ts`.
- **`ui.tsx` and `ui/` both resolve for `@/components/ui`.** Having both is a silent collision; the
  file was deleted and its contents folded into `ui/layout.tsx` and `ui/button-link.tsx`, so no
  import in the codebase changed.
- **The employer console is the same `score_match`, arguments swapped** (ADR-037), and it refuses
  to mount in production. It is unauthenticated and reads the candidate pool, so the guard is code,
  not a comment: `mount_employer_console` returns `False`, and a test boots the app in both
  environments to prove the route is present in one and absent in the other.
- **No employer-facing payload identifies a candidate** — reference, headline, district, years and
  the gap only. A test asserts the absence of `full_name`, `phone`, `email` and `user_id`.
- **Adding an analytics event needs a hand-written migration.** Alembic does not diff CHECK bodies,
  so a new `EVENT_NAMES` entry is accepted by the model and rejected by the database — and
  `record()` swallows its own failures by design, so the only symptom is events that silently never
  appear. This is the third time a CHECK constraint has cost time in this project.
- **A label overstated the data and had to be corrected.** "Fully qualified" appeared beside "holds
  3 of 6 required standards", because the flag means *all mandatory held*. It now says exactly
  that. Worth naming: the failure was in the words, not the arithmetic, and only a screenshot
  caught it.
- **`qlmanage -t -s 512` honours an SVG's `width`/`height`, not its viewBox.** The 64px source
  rendered 64px in the corner of a 512 canvas. The icon sources are 512-sized SVGs; the maskable
  one has no rounded corners, because the launcher applies its own mask and a rounded source is
  cropped twice.
- **The service worker registers in production builds only.** In development it caches hashed
  chunks that hot reload then replaces. Demonstrate installability with `npm run build && npm start`.
- **The in-app browser pane refuses `serviceWorker.register`** — "an unknown error occurred when
  fetching the script", although the same page fetches `/sw.js` fine at 200 with
  `application/javascript`. Registration therefore has **not** been confirmed in a real browser;
  that check is still outstanding and needs Chrome or a phone.
- **Twenty seeded candidates now, not five.** The original five are unchanged and still first in
  the list, because the golden set is asserted against them.

**Sprint 10 (matching and the gap) — done** on 2026-09-06. The payoff, after three deferrals.
`/matches` ranks jobs for a signed-in candidate with the score broken down, names the gap standard
by standard, and lists the courses that close it plus how to become qualified. Migration 0014
(`analytics_events`). ADR-036. 195 tests, plus a golden set behind `make evaluate`.

Non-obvious things:
- **`scoring.py` is pure and must stay pure** — no I/O, no clock, no model. That is what makes a
  score defensible to an employer and measurable against the golden set.
- **`record()` commits.** `get_db_session` never commits, so the first wiring flushed three events
  per request into an empty table. Only call it from handlers with no other uncommitted work.
- **Zero matched standards scores zero.** Letting level and evidence through alone gave every job
  a small non-zero score for everyone — noise that ranking then had to see past.
- **A missing mandatory standard caps at 45**, not zero: a candidate one short of a strong match
  needs telling, not hiding.
- **Golden-set expectations are relative, never absolute.** "This candidate outranks that one"
  survives a weighting change; "scores 82" does not, and a suite failing on every improvement is
  one people stop running.
- **`openapi-fetch` resolves rather than throws on non-2xx.** A 401 arrived as `data: undefined`
  and rendered as "nothing matches" — telling a signed-out visitor they had no matches. Authenticated
  queries must check `error` explicitly.

**Sprint 9 (connect the graph) — done** on 2026-09-06. The national taxonomy is now the
operational vocabulary. 87 job links, 64 course links and 4 candidate skills all point at real
National Occupational Standards; the 52 curated skills are `source='legacy'`, hidden from search
and browse but still reachable by URL because profiles reference them. 149 aliases carried across,
so `khoon nikalna` resolves to `HSS/N0513`. `skill_concepts` holds 18,958 concepts over 21,303
rows. Migration 0013. 179 tests.

Two things worth knowing:
- **`scripts/legacy_skill_map.py` is hand-authored and is the only place the old vocabulary maps
  to the new.** It cannot be automated: full-text search gets `Blood sample collection` →
  `HSS/N0513` right and `Customer service` → a hair-and-beauty NOS wrong, and nothing in the data
  distinguishes the two cases.
- **52 curated slugs collapse to 38 standards**, because the curated vocabulary is finer-grained
  than NSQF. Seeding merges duplicate links on the strongest signal.

**Sprint 8 (complete NSQF migration) — done** on 2026-09-05, against the full master data after
four further collections arrived (`sectors`, `ssc`, `state`, `district`).

```
states 36 | districts 766 | sub_districts 7,100
awarding bodies 106 (43 SSC + 63 AB) | sectors 43 | sub_sectors 796 | occupations 1,808
skills 21,303 | qualification_packs 4,424 | qp_skills 27,278 | model_curricula 1,950
qp_entry_routes 14,405 | nco_codes 2,541 | qp_skills with weightage 25,522
performance elements 38,340 | criteria 238,370 | knowledge 185,559 | generic 151,840
```

Migrations 0011 (geography) and 0012 (structure, entry routes, content, pruning). `make
import-nsqf` runs in ~90s and is idempotent — verified by identical counts across consecutive
runs. New module `api/modules/geography/`; new file `api/modules/skills/content.py`.

Things a future session must not relearn the hard way:
- **The `ssc` collection is never imported.** Portal accounts with 4,027 emails, 4,042 mobiles and
  50 bank accounts. `sectors` supplies the same organisations, cleanly, with four times the reach.
- **The owning body is the code prefix.** 97% of qualifications, 99.8% of standards.
- **Sector-local ids.** Occupation `code` *and* `occupationID` are both scoped to a sector;
  keying on the id alone collapsed 1,811 occupations into 529 before it was caught.
- **`minEduQual` is a structured array of alternative entry routes**, not a text description.
- **`alignedTo` is dirty**: 1,914 clean NCO codes, 507 variant, 793 free text that is discarded
  and counted.
- **Content keys on ordinals**, because `pcID` repeats within a unit.
- **7,459 of 21,263 current standards have no performance criteria.** Real, not a bug.

**Verified at last run:** 160 Python tests pass · Ruff + mypy clean · tsc + ESLint + `next build`
clean · migrations round-trip and autogenerate reports no drift · import idempotent across two
runs · all endpoints 200 · multi-script search still resolves `khoon nikalna` and `रक्त` ·
21,355 skills / 149 aliases / 8 tenants / 20 jobs / 20 courses, all 20 job locations resolved
to the geography master.

**Not built yet:** matching, typed `SkillRelation` edges, embeddings, analytics instrumentation,
observability, the encryption path, and **Hindi for the national corpus** (§12).

## 5. Repository map

*Refreshed 2026-09-24 (after Sprint 32).* Authored code: `api/` 113 files / 18,597 lines ·
`scripts/` 9 / 4,056 · `tests/` 35 / 10,813 · `migrations/` 29 / 2,945 · `web/src/` 178 / 18,174
(excluding the generated client, which is another ~7,523 lines and is never counted here).

```
api/                    FastAPI modular monolith
  main.py               app assembly, health, middleware order, demo task endpoints
  worker.py             ARQ entrypoint -- configures logging, registers crons (analytics purge)
  core/                 config, database (pool + statement timeout), cache, tasks (ARQ),
                        health, security (tokens, OTP, get_current_user), authorization
                        (permissions from membership, ADR-039), logging + redaction
                        (ADR-040/023), middleware (request context, security headers,
                        body-size cap, rate limiting -- all pure ASGI), text
  modules/skills/       models.py     Skill, SkillAlias (the leaf)
                        hierarchy.py  AwardingBody, Sector, SubSector, Occupation,
                                      QualificationPack, QpSkill, QpEntryRoute,
                                      QpNcoCode, ModelCurriculum
                        content.py    PerformanceElement, PerformanceCriterion,
                                      KnowledgeParameter, GenericCriterion (~614k rows)
                        concepts.py   SkillConcept -- rows that mean the same thing
                        + schemas, service, routes, __init__ (public interface)
  modules/matching/     scoring.py (pure), service.py (retrieval + gap + courses),
                        employer.py (the same scorer reversed, batched per employer),
                        schemas, routes. No model client, by ADR-036.
  modules/analytics/    analytics_events (ADR-025). record() commits.
  modules/geography/    State, District, SubDistrict, plus `PlaceIndex` -- the
                        state-constrained resolver Sprint 28 gave the service layer
                        after an ambiguous district name (Bilaspur, Hamirpur,
                        Pratapgarh) resolved to the wrong state's row. Its own module
                        because jobs and profiles reference it and neither is a skill.
                        `GET /geography/states` and `/districts` are its only routes.
  modules/marketplace/  Job, JobSkill, Course, CourseSkill, CandidateProfile + collections;
                        publishing.py (jobs) and course_publishing.py (courses) are siblings,
                        listings.py their shared policy
  modules/identity/     User, Tenant, Membership, Invitation. OTP sign-in by phone or email,
                        credential linking, organisations and their profile, consent record.
                        invitations.py holds the **three rules about who may do what to a
                        team** -- escalation, the last owner, and enumeration-safety -- each
                        in one function, because Sprint 15's finding was that a guard every
                        handler must remember is one that eventually is not there.
                        member_routes.py carries two routers: the org-scoped one, and a
                        public one keyed on the invitation token, because somebody accepting
                        is not yet a member and `require()` would 404 them out of their own
                        invitation.
  modules/privacy/      DPDP export, deletion preview and erasure. Depends on every module;
                        nothing depends on it.
  modules/applications/ Applying, withdrawing, saving, and the employer's inbox. Holds the
                        product's first deliberate disclosure: contact reaches an employer
                        because the candidate applied, and goes when they withdraw.
  modules/interests/    Registering interest in a course, and the provider's view of who did.
                        The **second** disclosure, on the same terms. A sibling of
                        applications/, never an extension: a course publishes what it teaches,
                        so a learner cannot be scored against it, and the provider inbox
                        therefore carries no card and no score at all (ADR-037).
  modules/notifications/  The outbox (ADR-006): queued in the request, sent by the worker.
                        The row names a recipient by id and never holds an address --
                        that is resolved at send time, so contact stays out of a dumped
                        table and out of every log line (ADR-023).
  modules/alerts/       Telling a candidate about a vacancy they never went looking for,
                        and closing one whose date has passed -- both run in the worker,
                        never a request. Reaches the one scorer through
                        `matching.candidates_for_job` (ADR-037); no second, looser rule
                        for "close enough to email about".
  modules/operations/   The back office (ADR-042, Sprint 28): `tenant_verification_events`,
                        the verification queue, `require_operator()`'s permissions. A
                        second leaf beside privacy/ -- depends on identity and marketplace,
                        nothing depends on it. `scripts/grant_staff.py` is the only writer
                        of `users.is_staff`, ever, by decision.
  adapters/notifications/  NotificationProvider protocol + console impl
  adapters/nsqf/        base.py       NsqfSource port (6 iterators)
                        documents.py  ALL document parsing, shared by every source
                        mongo.py / jsonfile.py  the two sources
                        normalise.py  levels, HH:MM, credits, slugs, NCO codes
                        importer.py   phased projection into Postgres
web/                    Next.js 16 PWA
  src/app/[locale]/     39 routes, all bilingual: browse (skills, jobs, courses), signin,
                        signup/[type], profile, matches, account, employer/[org] (+ settings,
                        team, candidates/[job], jobs/[job]/applications,
                        courses/[course]/interests, interests), admin + admin/[slug] (the
                        back office, ADR-042), invite/[token], audience pages,
                        privacy/terms/grievance, status (local only), error.tsx,
                        not-found.tsx, a catch-all
  src/lib/legal.ts      PRIVACY_NOTICE_VERSION (must match api/core/config.py) + grievance officer
  src/test/harness.tsx  the three mocked seams for Vitest component tests
  src/components/       Header, Hero, HowItWorks, Audiences, BrowsePanels, CtaBand,
                        Footer, SkillBrowser, SkillRequirements, SkillQualifications,
                        SkillRelated, SystemStatus, DevPanel, PlaceholderPage, ui
  src/messages/         en.json, hi.json — no user-facing string is hardcoded
  src/lib/api-schema.d.ts  GENERATED from OpenAPI, never hand-edit
infra/docker-compose.yml   Postgres 16 + pgvector (5433), Redis 7 (6380), Mongo 7.0 (27018)
migrations/versions/    0001 (pgvector + skills), 0002 (taxonomy + search),
                        0003 (tenants, jobs, courses),
                        0004 (users, memberships, candidate profiles),
                        0005 (rich profile), 0006 (list-filter indexes),
                        0007 (widen nsqf_level to Numeric(3,1)),
                        0008 (NSQF hierarchy), 0009 (widen level_taught),
                        0010 (skills.qp_count), 0011 (geography),
                        0012 (structure, entry routes, content, pruning),
                        0013 (skill concepts + 'legacy' source),
                        0014 (analytics events), 0015 (employer analytics events),
                        0016 (organisation profile), 0017 (profile enum CHECKs),
                        0018 (user consent), 0019 (applications + saved jobs),
                        0020 (application analytics events),
                        0021 (content translations), 0022 (locale base columns),
                        0023 (notification outbox), 0024 (job_role trigram index +
                        role analytics names), 0025 (course interests + two widened CHECKs),
                        0026 (invitations), 0027 (vacancy lifecycle + alerts, `alerted_at`
                        backfill), 0028 (operator authority: `users.is_staff`, `verified_at`
                        + evidence CHECK, `tenant_verification_events`)
scripts/                seed_skills.py, seed_marketplace.py, import_nsqf.py,
                        legacy_skill_map.py (hand-authored, the only curated->NOS map),
                        retire_legacy_skills.py, seed_candidates.py (demo profiles,
                        the golden pairs -- 34/7/16 as of Sprint 29), evaluate_matching.py,
                        grant_staff.py (the only writer of `users.is_staff`; refuses to
                        create an account it cannot find), clean_fixtures.py (named
                        fixture slugs only, `--dry-run` by default, never touches an
                        account) — all idempotent except clean_fixtures and grant_staff,
                        which are one-shot by design
tests/fixtures/         nsqf_sample.json — the corpus in miniature, so tests need no Mongo
backups/                schema.sql (committed DDL) + README.md (restore paths, drill record).
                        Dumps are encrypted and live in ~/iism-backups, never here.
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
- **Homebrew at `/usr/local` is the Intel build, and Rosetta is not installed, so it does not run at
  all** (checked 2026-10-12: `brew install` fails with "Bad CPU type in executable" and a misleading
  "'git' must be installed"; `/opt/homebrew` does not exist). Python comes from uv (native arm64)
  instead. Do not install project dependencies through brew. Fixing it properly means a native
  Homebrew in `/opt/homebrew` and moving packages over; nothing needs it yet.
- **`/usr/local/bin/git` is also x86_64 and also fails** when something execs it by that path (the
  `gh` CLI does; `/usr/bin/git` works). So `gh pr create` needs `PATH="/usr/bin:$PATH"` in front of it,
  and every `gh` call should pass `--repo hegdekattehnew/iism` (its repo lookup runs git).
- **`gh` is a native arm64 binary at `~/bin/gh` (2.102.0, installed 2026-10-12 straight from
  `cli/cli` releases because brew is broken), logged in as `hegdekattehnew`** with scopes `repo`,
  `workflow`, `gist`, `read:org`: broader than the fine-grained, repo-only token that was
  recommended (Contents, Pull requests, Actions, Workflows read-write); tighten with `gh auth logout`
  and `gh auth login --with-token` if wanted. `~/.zshrc` now has `export PATH="$HOME/bin:$PATH"` (the
  first attempt did not add it: its `grep` matched a commented-out template line). A
  `compinit: no such file ... _brew_cask` warning in every new shell is a dangling symlink from the old
  Homebrew and is harmless.
- **`uv sync --locked` alone uninstalls the dev tools** (ruff, mypy, pytest). Always
  `uv sync --locked --extra dev`.
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
make seed        # taxonomy + marketplace + demo candidates (idempotent)
make evaluate    # score the matcher against the golden set
make db-dump     # encrypted Postgres dump -> ~/iism-backups (needs IISM_BACKUP_PASSPHRASE)
make db-restore DUMP=~/iism-backups/iism-pg-....sql.gz.enc   # DROPS and recreates the target
make mongo-dump  # encrypted dump of the NSQF source of record
make mongo-restore DUMP=...  # [INTO=<db>]
make restore-drill  # dump both, restore into scratch dbs, compare counts, clean up
make db-schema   # refresh backups/schema.sql (DDL only, committed)
make import-nsqf # project the NSQF corpus from Mongo into Postgres (idempotent)
make api         # uvicorn on :8000
make worker      # ARQ worker
make web         # Next.js on :3000
make check       # ruff + mypy + pytest  <- run before claiming anything works
make gen-api     # regenerate the TS client after ANY endpoint change (reads local /openapi.json)
cd web && npm test && npm run build && npm run budget   # web tests, build, first-load JS budget
```

Three processes must run for the full stack: **api, worker, web.** The API and web reload on
change; **the worker does not** — restart `make worker` after any change to `api/`, or it keeps
running old code (found 2026-09-15: a worker from 2026-09-10 plus two orphaned copies).

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

42. **Sector-local identifiers are not global, and this trap fires twice.** An occupation's
    two-digit `code` is scoped to a sector -- that was caught. Its `occupationID` is *also* scoped,
    reusing `"1"`, `"2"`, `"3"` across forty-odd sectors -- that was not, and keying on it collapsed
    1,811 occupations into 529. Nothing failed; the count was simply wrong. **When a source id looks
    global, count the distinct values before keying on it.**
43. **`minEduQual` is a structured array, never a text description.** 14,877 alternative entry
    routes across 4,564 qualifications, each pairing an education requirement with an experience
    one. An earlier pass counted non-empty arrays and called them text values. `"NA"` experience
    stays NULL -- "no experience required" and "not stated" would score differently.
44. **`alignedTo` is dirty and must be parsed, not stored.** Of 3,214 values: 1,914 well-formed NCO
    codes, 507 in variant formats (U+2010 hyphens, `NCO 2015- ` spacing, comma-separated multiples),
    and 793 free text like `(CNC Operator)`. The free text is discarded and counted. Sampling one
    clean value and generalising is how this was first misreported -- the same mistake shape as the
    level error.
45. **Content rows key on `(parent, ordinal)`, never the source's own id.** `pcID` repeats within a
    unit in 17 of 6,000 standards, `kpID` in 1, `skillID` in 2. A natural key on the source id fails
    partway through the import, after thousands of rows are already written.
46. **Content is deleted and rewritten each run, not upserted.** It is wholly derived and owned by
    the importer, and a revised standard with fewer criteria must not leave the surplus behind.
    Anything later attached to content (translations, embeddings) must therefore live in its own
    table, not as a column on these rows.
47. **Free prose columns are `Text`, not `String(n)`.** Two import runs died on `varchar(512)`
    overflow -- occupation names reach 894 characters and entry-route specialisations 735. Postgres
    stores `Text` and `varchar(n)` identically, so a cap buys nothing except a future failure. Keep
    a bound only on genuine codes and enums.
48. **Autogenerate emits unnamed foreign keys.** `op.create_foreign_key(None, ...)` produces a
    downgrade calling `op.drop_constraint(None, ...)`, which fails outright. Name every FK before
    applying a generated migration -- twelve appeared across 0011 and 0012.
49. **A source iterated more than once double-counts its own diagnostics.** `iter_nos` now runs
    three times (collect, then two content passes), so `skipped_documents` tripled. Capture
    per-source counters at the end of the collect phase, not at the end of the import.
50. **Regenerating a migration: never delete the old file before the new one exists.** A glob that
    did not match left the database at a revision whose file was gone, and alembic could then do
    nothing in either direction. Autogenerate against a scratch database instead, and reconcile.
51. **`make check` is not enough after a data-model change.** It passed while `occupations` held 529
    rows instead of 1,811. Compare the import report against independently computed expectations --
    for content, the ceiling is the sum over the *current version* of each code, which is how
    38,340 elements was confirmed correct rather than short.

52. **A model with a cross-module foreign key must import the target module.** SQLAlchemy resolves
    `ForeignKey("districts.id")` against the metadata at mapper-configuration time, so a script
    importing `marketplace.models` without `geography.models` dies with `NoReferencedTableError`.
    This fired twice in one sprint — marketplace→geography, then skills→concepts. Import for the
    side effect and say why in a comment; the alternative is every script needing to know the
    whole graph.
53. **A `Literal` on an output schema is a latent 500, and this is the second time.** Adding
    `legacy` to `skills.source` broke `GET /skills/{slug}` for every retired row until the schema
    listed it. Output models stay permissive; the constraint belongs on input.
54. **A many-to-one remap creates duplicate association rows.** 52 curated skills collapse to 38
    standards, so a job listing both "hand hygiene" and "infection control" tried to insert
    `HSS/N9618` twice and hit `uq_job_skill`. Merge on the strongest signal — highest importance,
    mandatory beats optional — rather than taking the first or last.
55. **`scripts/` is not an importable package.** Sibling imports work (`from legacy_skill_map
    import ...`) because Python puts a script's own directory on `sys.path`; `from scripts.x import`
    does not, because only `api*` is installed.
56. **A session running `make api`/`make web` against a checkout you then `git checkout`/merge/pull
    on will briefly break, and that's expected, not a regression.** Fast-forwarding `v2/foundations`
    → `main` (117 commits, Sprint 40) while both dev servers were live rewrote the working tree out
    from under their file watchers mid-flight: the API hit `Error loading ASGI app. Could not import
    module "api.main"` and Next hit `ENOENT` scandir-ing `web/src/app`. Both `uvicorn --reload` and
    `next dev` recovered on their own within seconds once the checkout finished — confirmed by
    re-checking `/health/deep` and a fresh page load a few seconds later, not by assuming "it said
    error so it's broken." Don't restart anything reflexively on seeing this; re-check first.
57. **A Dependabot bump and your own dependency fix can target the same `uv.lock` block, and the
    resolution is "keep the newer one," not "keep yours" or "keep theirs."** `main` had merged
    Dependabot's `python` group bump (`pyjwt` → 2.14.0) while a branch here independently bumped
    `pyjwt` → 2.15.1 for a CVE; `git merge` conflicts on the exact lines since both touch the same
    package block. The correct resolve kept 2.15.1 (newer, already audit-verified) and took every
    *other* package in that Dependabot bump (`alembic`, `pymongo`, `ruff`) from `main` as-is — not a
    blanket "ours" or "theirs." After hand-editing out the conflict markers, **run `uv lock` again**
    to let it confirm the file is self-consistent (it re-resolved in under 30ms and changed nothing
    further, which is the signal the hand-edit was correct), then `uv sync --locked --extra dev` and
    the full suite before trusting it.

58. **The Terminal panel's shell eats the first character of a command.** oh-my-zsh's prompt
    redraw swallowed the `m` of `make api`. Start commands with a leading space, and confirm the
    prompt is back before sending the next one.
59. **A foreground or background shell has a time limit; a long suite needs `timeout` set.**
    `make check` is ~85 s and passes at the default, but an import plus a seed does not — pass the
    explicit timeout rather than concluding the command hung.
60. **Edit a file in one step, not two.** A string replace that adds a use before the declaration is
    live to HMR the instant it is written: the browser logged `ReferenceError: now is not defined`
    from the half-applied state. The console buffer is cumulative, so judge a fix by whether the
    **count grows after a fresh load**, not by whether old errors are still listed.

61. **A nullable boolean sorts first on `DESC`.** `qp.occupation_id = f.occupation_id` is NULL when either
    side is, `NULL OR false` is NULL, and Postgres puts NULLs *first* on `ORDER BY ... DESC`. Python's
    `bool(row.x)` then hid it from every read. `coalesce(expr, false)` in the SQL, and a test whose two
    candidates differ only in that flag.
62. **A rule that passes every fixture can still read as nonsense on the real corpus.** The ladder's first
    version passed its tests and "led" a General Duty Assistant to an Automotive technician. Print real
    output for a handful of roles you can judge before trusting a derived rule, and measure its reach over
    the whole corpus rather than a sample — a 310-role sample said 42% and 79% for two versions of the
    same query; the full run said 38%.
63. **`/careers` is not the career ladder.** It is the company's own hiring placeholder (`PlaceholderPage`
    with `titleKey="careers"`), linked from the footer. The ladder is `/career-paths`; the API is
    `/me/careers`. Check `ls web/src/app/[locale]/` before naming a route.
64. **macOS `sed -i` takes the next argument as a backup suffix.** `sed -i 's/a/b/' file` fails with
    "undefined label"; use `sed -i.bak ... && rm file.bak`, or a short Python replace. This cost a failed
    edit twice this sprint.
65. **Next 16 keeps dev output in `.next/dev`, so `npm run build` is safe beside a running `make web`.**
    The budget script reads `.next/diagnostics/route-bundle-stats.json` from the build.

66. **Role search reads the `role_aliases` TABLE, not `ROLE_ALIASES`.** Editing `role_aliases.py` changes
    nothing in the running product until the table is re-projected (`make seed`, or just
    `scripts/seed_skills.py::_seed_role_aliases`). The first snapshot comparison for ADR-050 ran against a
    stale table and showed no effect from the alias edits — `telecaller` still reached the old target.
67. **Diff a ranking change on real queries, not fixtures.** Both defects in the first demotion rule
    (exact titles demoted; the only literal match buried) were invisible to the fixture corpus and obvious in a
    before/after diff of 726 real queries. Snapshot first, then change, then read every top-result change.
68. **A shared SQL fragment changes every caller.** `ROLE_REPRESENTATIVE_ORDER` is used by role search,
    career ladders and the alias checker. Changing it is one edit and three behaviours; the ladder's tests and
    the 699-query snapshot both ran after it.
69. **Rolling back the `db` test fixture rolls back the whole test, including the organisation you just
    registered.** A "stand or fall together" test that rolls back and then looks for the tenant finds
    nothing. Prove ordering with a spy on `enqueue` and `commit` instead.

70. **A benchmark run from `nohup` or a background script may use the wrong `git`.** In Sprint 49 a script's `git stash` failed with
   `/usr/local/bin/git: Bad CPU type in executable` (an x86 binary ahead of the arm64 one on that PATH), so the "old code" baseline
   silently ran the **new** code and printed a perfect 20/20. It was noticed only because the number was too good. Take a baseline
   from a clean `git worktree add /tmp/x main` with `PYTHONPATH=/tmp/x` (and check `python -c "import api; print(api.__file__)"`),
   never from a stash.

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

**Merged 2026-10-09 to 2026-10-12.** PR #30 (Sprint 52, `63ba8a0`) and PR #35 (Sprint 53, `6993241`), then the dependabot PRs one at a time (#28 python group, #34 web group, #32 `upload-artifact` 6,
#33 `cache` 6, #3 `checkout` 7, #2 `setup-uv` 7, #4 `setup-node` 7), then PR #36 (the e2e job's own `checkout`/`setup-uv`/`setup-node` to v7, merge commit `d8cf469`). The stale dependabot duplicates
(`python-5113e460e3`, `web-d4d48f29cf`, `web-0caa1ab034`, `setup-node-6`, `@types/node-26.6.3`) and every merged branch were deleted on `origin`; local and remote both hold only `main`. Branch
deletes on `origin` are done by the owner or with `git push origin --delete <name>` (one was blocked by the permission system on 2026-10-09 and went through on 2026-10-12).

**Merged 2026-10-06.** PR #29 (`sprint-51` → `main`, merge commit `a18e79a`) carried Sprint 50.5 (`1681de7`) and Sprint 51 (`136d81e`, `a2243ae`); `sprint-50-5` and `sprint-51` were deleted on `origin` and locally. `gh` is not installed, so PR state is read from `git fetch` and ancestry. **Sprint 52 merged as PR #30 (`63ba8a0`, 2026-10-09) and `sprint-52` was deleted. Since then: `sprint-53` (2026-10-09), uncommitted.** Sprint 51's change list is in §11 ("Sprint 51: bulk upload"). Sprint 50.5's
changes: `marketplace/stats.py` (one statement, ten new figures and `demo`), `marketplace/models.py` (`skilled_profile()`), `marketplace/schemas.py`, `matching/employer.py`
(`candidates_total` reuses it), `web/src/components/StatsBand.tsx` (two rows; a test, there was none), `web/src/lib/format.ts` (the shared digit grouping), `LiveCount`, `ApplyPanel`,
`lib/profile.ts` and `lib/counts.test.tsx` (invalidation), en/hi/ms `stats.*`, the generated `api-schema.d.ts`, `tests/test_homepage_figures.py`, ADR-061, `CLAUDE.md`, the backlog document.
**No migration, no new endpoint.**

**Earlier, 2026-10-02: `v2/foundations` merged and was deleted.** PR #14 (`v2/foundations` → `main`, head
`8e7e179`) merged into `main` at `b15e0c6`; both CI jobs passed on that exact commit (checked via
the API, not assumed). `v2/foundations` was then deleted both locally and on `origin` — there is
**no feature branch right now**, only `main`. PRs #12 and #13 show as closed-without-merging in
GitHub's history; that's GitHub auto-closing other open PRs for the same branch once #14 merged, not
a failed attempt worth investigating. The merge itself needed resolving one real conflict — `main`
had a Dependabot bump to the same `uv.lock` block this branch's own CVE fix touched — written up in
full in §11's Sprint 40 entry and as a general gotcha in §8. **Before starting the next sprint, cut
a new branch first** — there is nothing to continue on top of.

**Merged 2026-09-21.** `v2/foundations` reached `origin`, PR #1 was opened and merged into `main`
(merge commit `7b6337a`), and **CI ran green on it** — the first time CI had ever run on this work.
Verified with the API, not assumed.

This section was wrong in the most expensive possible way, and the shape of the mistake is worth
keeping. It said "Pushed 2026-09-07 … that risk is closed", because the last commit to actually
reach the remote was one called *"Correct the git section: the branch is pushed"*. Sprints 11, 12,
13 and 14 — five commits and several thousand lines — then accumulated locally while the document
went on asserting they were safe. **A claim about the remote is only true at the moment it is
checked**; re-check it, do not read it here.

- **Merged 2026-09-29.** PR #9 (`v2/foundations` → `main`, the correct direction) merged at
  `2026-09-29T07:50:50Z`, merge commit `4345571`. Both CI jobs — *API: lint, types, tests* and
  *Web: lint, types, build* — passed on it, verified via the API. `main` now contains everything
  through Sprint 38; `git log origin/main..origin/v2/foundations` is empty. Work continues on
  `v2/foundations`, which will again run ahead of `main` with no CI until its next PR — **re-check
  this section's dates before trusting it**, the same discipline that caught this file asserting a
  four-sprint-stale push once already (see the paragraph above).
- **A PR from this branch came out backwards twice before the correct one merged, despite the
  compare link below being right.** PR #7 (2026-09-24) and PR #8 (2026-09-29) were both created
  with **head `main`, base `v2/foundations`** — the reverse of what a merge into `main` needs — and
  both were closed without merging once caught. Checked via the API
  (`mergeable_state`/`changed_files`/`additions`/`deletions`) before either was trusted: a
  `main`-into-`v2/foundations` PR shows **0 changed files**, because `main` has nothing
  `v2/foundations` doesn't already have — and its CI checks are the base branch's stale ones, not a
  real test of the diff. **Do not read "a PR exists" as "the right PR exists"** — fetch
  `GET /repos/hegdekattehnew/iism/pulls/{n}` and read `head.label`/`base.label` before reporting CI
  status on any PR from this branch again. The fix, the second time it happened, was the same as
  the first: close the backwards PR and open a fresh one from
  `https://github.com/hegdekattehnew/iism/compare/main...v2/foundations?expand=1` — that URL's
  `BASE...COMPARE` order is already correct (base `main`, compare `v2/foundations`); the mistake
  happens inside GitHub's form after landing on that page, not in the link itself, so re-check the
  base/compare dropdowns before submitting rather than trusting the URL alone got it right.
- Verified with `git log origin/v2/foundations..HEAD`, which must be **empty**. Comparing the
  branch tip against the document is what failed for four sprints.
- **CI runs on pull requests and on `main`.** Both jobs — *API: lint, types, tests* and *Web: lint,
  types, build* — passed on the merge commit, which is what finally exercised Sprint 20's
  dependency audits and the first-load budget outside this laptop.
- **`gh` is still not installed**, so PRs are opened in the browser at
  `https://github.com/hegdekattehnew/iism/compare/main...v2/foundations`, and their title and
  description have to be pasted by the owner. Two consequences worth knowing: the session cannot
  read CI itself without the GitHub API (unauthenticated reads work for this public repo), and
  **pasting a rendered Markdown file loses its formatting** — send raw text, not a `.md` the
  client will render.
- **Dependabot is live on `main`** and opened 5 PRs the moment it merged (16 web updates, 4 Python,
  three GitHub Actions bumps). Its `uv` update job fails; the npm and actions jobs succeed. That is
  Dependabot's own infrastructure, not this repo's CI.
- Two things a reviewer needs telling: it is a 211-file, +35,107-line change spanning eight
  sprints and is not reviewable as a single unit, and it **contains a deliberate rollback**
  (`c10829f` discards `a62d964`), so reading commit-by-commit means passing through work that was
  undone on purpose.
- The NSQF work reads as a sequence worth understanding in order: `a62d964` projected the corpus,
  `5cf496f` made it usable at 21k rows, `75abc17` added tests, **`c10829f` rolled the whole thing
  back** after an audit, and `4230c9c` re-migrated against the complete master data. The rollback
  commit is not a failure to skim past — it carries the audit that made the second attempt right.
- `1fd92af` connected the taxonomy to the marketplace; `3b69a42` added matching.
- The original `app/` (identity module, auth, 8 actor types) remains in history on `main` at
  `ef59c4e`. Recoverable if that work is ever worth mining.

## 10a. Backup and restore

`backups/README.md` is the full account. In short:

- **A crashed container loses nothing** — the data is in Docker volumes. Deleting one loses it.
- Since Sprint 20 every dump is **encrypted** (`IISM_BACKUP_PASSPHRASE`, openssl aes-256-cbc with
  pbkdf2) and written to **`~/iism-backups`, outside the working tree**. `make db-dump` /
  `db-restore` for Postgres, `make mongo-dump` / `mongo-restore` for MongoDB — **which had no
  backup at all before**, although it is the corpus's only source (ADR-034).
- **`make restore-drill`** dumps both, restores into scratch databases, compares exact counts and
  drops them. **Run 2026-09-11, passed**: Postgres 36 tables, key counts identical; MongoDB 7
  collections, every count identical.
- The last plaintext dump (`backups/iism-20260907-1003.sql.gz`, pre-encryption, real accounts in
  the clear) was **deleted by the owner on 2026-09-11**. It was gitignored and never committed.
- `backups/schema.sql` (DDL) is committed and refreshed with `make db-schema`.
- Almost every Postgres row is derived and rebuilds from MongoDB with `make import-nsqf && make
  seed`. People — accounts, consent, profiles, analytics — exist only in a dump.

## 11. What comes next

*Rewritten 2026-09-22. The previous version had gone stale in the way that misleads rather than
merely ages: it called deployment "Sprint 22" (Sprint 22 was languages and notifications), and
listed course-provider self-serve publishing and organisation email sign-in as upcoming when both
shipped in Sprints 12–14. **Delete an item here when it ships; do not let it drift.***

**Deployment is deferred by the owner.** It is not blocked on design — §13 lists what it needs —
and it stays out of the sprint queue until they say otherwise.

### The homepage counts (reported twice, 2026-09-23, fixed the same day)

"I added a job listing and the numbers under the marketplace section are not updated." Two
distinct causes, a day apart, and the second is the more interesting one.

**First: two caches, neither invalidated.** The figures are computed live, but
`useOrgJobMutations` refreshed `["org-jobs", slug]` and nothing else, and `sw.js` served
`/marketplace/` stale-while-revalidate — so on a production build the number was permanently one
visit behind. Probed against the committed worker: all three count endpoints answered from cache
while online. `web/src/lib/counts.ts` now holds the keys and `LIVE_DATA` in `sw.js` makes the
counts network-first.

**Second: the number was right and its definition was not the reader's.** The panel counted
**open** vacancies, and `scripts/seed_marketplace.py` closes `inventory-clerk-nagpur` on every run
— so publishing a twenty-first vacancy moved the figure 19 → 20. Nothing was broken and nothing a
cache fix could reach. The panel now leads with `jobs_posted` and names `jobs_open` underneath
when they differ.

- `posted_job()` is the count's predicate, `open_job()` stays the listings'. A bare
  `status == "published"` in a count is deliberate; the docstring says so, because the rule beside
  it says every public listing must use `open_job()` and the next reader would file this as the
  one that was missed.
- **Both payloads carry both names.** `jobs` meaning "open" in one response and "posted" in
  another is the trap; the rename made `tsc` fail on the one stale reader, which is the whole
  reason it was a rename and not a redefinition.
- **Not monotonic, and that is the honest shape.** Unpublishing removes the page and removes the
  row, so the figure never names a vacancy a visitor cannot open. A true lifetime tally needs
  `first_published_at` and would advertise vacancies that exist nowhere on the site. Walked
  through every state against the live API: draft 21/20 → published 22/21 → closed 22/20 →
  reopened 22/21 → unpublished 21/20.
- **The second line hides when the two figures converge** — the branch a seeded database never
  shows, because the seed always closes one. It has its own test for exactly that reason.

No migration: `ix_jobs_status_closed` is on `(status, closed_at)`, so the posted count uses the
leading column and gets the same index-only scan.

### Sprint 28 — clear the decks (done 2026-09-23)

The monetisation ADR and payment port are **deferred by the owner**; the gate ADR-025 sets cannot be
cited honestly yet (five golden pairs, all candidate→job where ADR-025 means course; click-through
computable since Sprint 24 and computed nowhere; enrolment conversion at zero and deliberately not
modelled). Scoped as one sprint this came to ~44 files, so it is two — Sprint 29 carries the admin
pages and the golden-set expansion.

**Geography — done 2026-09-23.**

- **`PlaceIndex` is the one resolution rule**, pure and session-free, with two loaders:
  `resolve_location` narrows to the names one write could reach, `load_place_index` loads the master
  for the import sweep. `resolve_location`'s signature is unchanged, so none of its six callers moved.
- **The importer's private alias map and private lookup are gone.** A test asserting the two maps
  were identical had kept the letters in step and not the algorithm.
- **The churn is fixed and measured.** Two consecutive `make import-nsqf` runs:
  `locations_updated=20` then `locations_updated=0`, with sha256 digests over
  `(id, state_id, district_id, updated_at)` on `jobs` and `candidate_profiles` **identical before
  and after both**.
- **A second defect found while measuring**: `scripts/seed_candidates.py` never resolved geography
  at all, so all twenty seeded preferred locations carried NULL on both FKs and `candidate_facts` —
  which reads exactly those columns — saw nothing. Half of Sprint 23's locality tie-break had no
  input. Fixed the way Sprint 15 fixed the marketplace seed; probed by clearing the twenty and
  running the seed alone, 20 unresolved before and 0 after.
- `make evaluate` still prints **88 / 45 CAPPED / 86 / 100 / 0**, bit-identical, which matters
  because resolving preferred locations changes what the tie-break sees.
- 606 backend tests (was 598). Non-vacuity: neutering the state filter fails six of the seven new
  tests; reverting the change-guard fails the seventh on `assert 1 == 0`.

**The operator surface — done 2026-09-23.** `tenants.is_verified` had existed since Sprint 12 with
**no writer of any kind**. A marketplace whose verified badge nobody can grant has no verified
organisations.

- **ADR-042** records a second authority beside ADR-039's: global, granted by `users.is_staff`
  alone, expressed as `OPS_*` members of the same closed `Permission` enum. `require_operator()`
  sits beside `require()` and returns an `OperatorContext` with **no tenant on it**.
  `ROLE_PERMISSIONS` may never hold an `OPS_` member — `owner` is the widest role there is.
- **No HTTP writer for `is_staff`, ever.** `scripts/grant_staff.py` (`make grant-staff`) is the only
  one; it needs database credentials, refuses to create an account, and prints the full roster after
  every run including the dry one.
- **Migration 0028 dropped `is_verified`** and derives it from `verified_at`. Free only in this
  sprint: nothing had ever written the boolean, so no row could disagree. `verified_at` +
  `verified_by` + a ≥10-character `verification_note`, with a CHECK making an unevidenced badge
  **unrepresentable**. Down-and-up rehearsed; `alembic check` clean.
- **`tenant_verification_events` is append-only** and revocation is a new row. On revoke the
  tenant's three columns go NULL, so a revocation's reason survives only in the log — which is why
  both exist. `_delete_tenant` went from eleven tables to twelve.
- **Exercised live, not inferred**: granted MedLife through the API and watched `is_verified` flip
  to true on the public `/jobs` payload for both its vacancies; granted Apollo Care and read
  **"Verified"** on `/en/employer/apollo-care-hospitals/settings` in the browser; revoked it and
  read **"Not yet verified"**. Anonymous 401, non-staff 404 with a body byte-identical to
  `/ops/nonsense`, operator 200 on the same URL.
- **`hiring@apollo-care.example` is now an operator** on the dev database, and the verification
  events from those demonstrations are still there — they are append-only by design, so deleting
  them to tidy up would contradict the thing being demonstrated.
- 628 backend tests (was 606). Four probes: removing a route's guard fails four tests including the
  route walk; letting `_OWNER` reach `OPS_ORG_VERIFY` fails the disjointness test; removing the
  CHECK **from migration 0028** fails the database test (removing it from the model does not — the
  test database is built from migrations, which is the point).
- **A finding worth keeping**: this FastAPI keeps included routers nested, so `app.routes` holds
  `_IncludedRouter` objects and exactly two bare `APIRoute`s. The first route-guard test found zero
  `/ops` routes and **failed on its own anti-vacuity assertion** rather than passing against an
  unguarded back office.

**Still to do in Sprint 28:** nothing. Sprint 29 carries the `/admin` pages and the golden set.

### Sprint 29 — a back office you can see, and a matcher you can defend (done 2026-09-23)

**The `/admin` pages.** `OperatorOnly` keeps three answers apart that a permission gate usually
collapses: not-found for a signed-in non-operator (the same answer the API gives), a sign-in prompt
for somebody signed out, and **nothing at all while the answer is in flight** — the branch that
rots, because it is invisible on a fast connection and 404s every operator on a slow one. It has
its own test, and the first version of that test passed against the bug: it asserted the children
were absent, which is also true when the signed-out prompt is showing. It now asserts the prompt is
absent too.

- `is_staff` rides on `/auth/me`, so the gate costs no extra request.
- **The harness was lying about signed-out.** `derived()` returned a populated account regardless of
  `world.signedIn`, so every signed-out branch was untestable through that seam. Fixed; the whole
  suite still passed, which says the old behaviour was never load-bearing.
- Budget unchanged at **672/684 KB** — admin routes are route-local, not in the header or the barrel.
- Exercised in a browser: granted MedLife through the UI and watched the badge reach the public
  `/jobs` payload, then withdrew it. **The withdrawal note corrects the grant**: the note I typed
  when granting claimed a lab licence had been checked and nothing had been, and a false evidence
  note undermines the one field the whole feature exists for. Both decisions are in the history.
- `/hi/admin/...` at 360×640: no overflow, dates localised, the operator's own note left in the
  language they wrote it in.

**The golden set: 5 pairs → 34 pairs, 7 orderings, 16 course expectations.**

- **Nine labels failed on the first run and all nine were mine.** Three claimed
  `capped_missing_mandatory` for candidates already scoring below 45 (`capped` is
  `raw > MANDATORY_GAP_CAP`, so it was correctly False — they get `missing_mandatory` now); four
  named `inventory-clerk-nagpur`, which the seed closes as filled; one ordering was written
  backwards. The scorer was right every time.
- **`below_assessed_peer` is gone as a per-pair label**, and the reason is structural rather than an
  oversight: "ranks below that other candidate" names a *pair*, and a per-pair label has nowhere to
  put the peer. It lives in `GOLDEN_ORDERINGS` now. The `if/elif` chain gained the `else` it never
  had, so an unrecognised label fails instead of asserting nothing.
- **Course recommendation has labelled data for the first time** — ADR-025's precision@5 is about
  course recommendation, and `courses_closing_gap` had none of any kind. That is one third of
  Sprint 28's uncitable gate now citable.
- **`make evaluate` is still not in CI and should not be.** It needs the corpus, which is not in the
  repository, so a scheduled workflow would be red every morning for a reason nobody could fix.
  `tests/test_golden_set.py` (19 tests) runs in CI instead and catches both classes of mistake above
  **statically** — probed by re-introducing each and watching the named test fail.
- Probes on the scoring run itself: making `self_declared` score like `certified` fails the evidence
  ordering by name; removing the mandatory cap fails fourteen expectations by name.

### Sprints 30 and 31 — the audit, and acting on it (done 2026-09-24)

No new functionality, by instruction: *"check the Scope from our baseline documents and the reality
of completed items."* Three axes audited — route-handler delegation, tenant scoping, swallowed
exceptions — and the result is worth stating as a whole: **the server is in better shape than the
documents claim, and the client was in worse shape than its tests suggested.**

- **Tenant scoping audited clean, and no security work followed.** All 29 `{org_slug}` routes
  carry `require(...)`; every service reachable from them re-filters on `tenant_id` in the same
  `WHERE` as the slug or id, including both classic IDOR shapes. The one auth-free surface is the
  demonstration console, behind an allowlist that fails closed. Saying so *is* the result.
- **Eleven frontend writes failed in silence, and the worst were not obscure.** `SkillsSection` --
  the file whose own docstring calls it "the only part of a profile that changes a match score" --
  had no `error`, `isError` or `onError` anywhere. `Notices.markRead` never read `error` at all,
  and openapi-fetch resolves on a non-2xx, so `onSuccess` ran on a 500 and the button did nothing
  for ever. See the frontend conventions in `CLAUDE.md`.
- **One was actively misleading**: an expired session was told its vacancy needed a required
  standard it already had. Fixed and verified in a browser against the real API.
- **`ProviderWorkspace`'s docstring described a fix the file never contained** -- past tense, four
  sprints old, `isSignedOut` never imported there. Found while writing the tests, not by the audit.
- **`web/src/lib/mutation-errors.test.ts`** reads the source and fails when a `useMutation` has
  neither an `onError` nor anything reading its `.isError`. **`tests/test_worker_schedule.py`**
  asserts the four feature crons are registered where arq actually reads them.
- **`docs/scope-reconciliation.md`** is the ledger: seven places the product definition and the
  tree disagree, each naming the file that proves it. The `.docx` is deliberately not amended.
  Its sharpest finding is in no other document: **three of the four `SKILL_SOURCES` have no writer
  outside the seed**, so `EVIDENCE_WEIGHT_SHARE = 0.10` is a constant for every real candidate --
  a tenth of the match score carries no information in production.

### Sprint 32 — every handler delegates (done 2026-09-24)

The audit recorded 17 route-handler violations as accepted; the owner reversed that and asked for
them fixed before any other work. All 17 moved, plus two the audit had classed as borderline, so
the route layer now makes **zero** calls to `db.*`, `select()` or `record()`.

- **The point was to preserve the ordering, not bury it.** Fifteen of the seventeen existed because
  `record()` commits and therefore has to run after the business commit. Each service function now
  commits and then records, with the reason written beside it -- one function owns the sequence
  instead of every handler remembering it.
- **`tests/test_route_delegation.py` is the guard**, and it names the module, the handler and the
  call when it fails. Probed by restoring `update_organisation`'s old shape.
- **One deliberate behaviour change**: `member_removed` now fires when somebody *leaves*, not only
  when an owner removes them. Moving the record into the single writer is what exposed it -- the
  leave path had never been measured. `{"self": true}` keeps the two apart.
- Also found and fixed while doing it: `update_organisation` had **no service layer at all**, which
  is how `contact_email` went eight sprints without the normalisation every other address has.

### Sprint 33 — a management-facing MVP push (done 2026-09-26)

The owner's instruction superseded the monetisation-first plan below before any of it was built:
optimise the next sprint for demonstrating the platform's full actor breadth to higher management,
ahead of revenue. Full stories, acceptance criteria and sizing are in
`docs/IISM-Product-Backlog.docx` (Epic B7 and BL-2.3, sequence in §4) — this entry is the decision
record, not the detail.

- **Government agency and external-system actors, thin slice.** Shipped: an ops-run CSV enrolment
  (`scripts/bulk_enrol_candidates.py`, reusing `identity.provision_candidate` rather than a second
  construction path), a programme-scoped reporting view (`GET /ops/programmes/{name}`), and API-key
  auth (`ServiceAccount`, a fourth credential beside JWT) on a partner-facing `GET /partners/jobs`
  route. The super-admin tier stayed cut, per the original decision — no audience-visible payoff and
  ADR-042 already argues against speculative admin escalation paths.
- **The course-to-role alignment score, pulled forward to run alongside it.** Shipped:
  `course_role_alignment` and `GET /org/{slug}/courses/{slug}/alignment/{role_slug}`, independent of
  any candidate (ADR-037 does not apply the way it does to `candidates_for_job`, because there is no
  candidate in this comparison at all). `docs/scope-reconciliation.md` #4 is now closed.
- **The rest of Epic B2, pulled forward again once B7 and BL-2.3 landed**, on the owner's
  instruction to keep going rather than stop at the originally-scoped slice:
  - **BL-2.1, configurable match weights.** `ScoreWeights` is a value object built by
    `weights_from_settings()` and passed into `score_match`; `scoring.py` still reads no
    configuration at all (an AST-based test checks this, not a substring search — a naive one
    false-positived on `ScoreWeights`'s own docstring). `make evaluate` printed the identical
    baseline with default weights, confirming bit-for-bit equivalence.
  - **BL-2.2, `course_dismissed`.** `course_opened`'s negative half — precision@5's missing class,
    named in `docs/scope-reconciliation.md` #3 as absent. Migration 0031 widens the CHECK by hand,
    per the established pattern; the two events are counted separately, not collapsed.
  - **BL-2.4, market-wide scarce skills.** `market_scarce_skills` reuses `scarce_skills`'s query
    with `tenant_id=None` via a shared `_scarce_skills` helper, rather than a second copy of the
    demand query — the same "one construction site" discipline as `candidate_card()`. New
    `GET /org/{slug}/market-demand`, reachable by a course provider for the first time.
- **B7 alone is not "all actors."** Assessment Provider is a separate epic (B3, Sprint 35 in the
  backlog's sequence) — a demo must not claim full actor coverage before it lands too.
- 724 backend tests (was 606 at the start of Sprint 28). `make gen-api` regenerated twice, both
  purely additive diffs. Every feature verified live against the running dev server and seeded data,
  not only through pytest.

### Sprint 34 — ADR-043, and a payment adapter port (done 2026-09-26)

The owner's stated direction is a marketplace that also **sells courses** and carries **gig work**;
Sprint 33 demonstrated the platform to management with no monetisation story at all, which made
continued deferral's cost visible rather than theoretical.

- **ADR-043 supersedes ADR-025's deferral clause — carried forward, not declared satisfied.**
  ADR-025 named three gate metrics. Precision@5 is now citable (34 golden pairs, up from 5, per
  Sprint 29). Click-through is joinable since Sprint 24 but has near-zero real volume. Enrolment
  conversion has **no surface at all** — Sprint 24 deliberately modelled interest, not enrolment,
  because a provider's own system is the source of truth for whether somebody enrolled. The ADR
  says this plainly rather than treating the port's existence as having passed the gate.
- **The port, and only the port.** `api/adapters/payments/` — a `PaymentProvider` protocol
  (`create_payment(amount_paise, currency, reference) -> transaction_id`) and
  `ConsolePaymentProvider`. No gateway, no `Order`/`Entitlement`/`Payout` table, no route or service
  calls it — `tests/test_payment_adapter.py` statically asserts nothing under `api/modules/` imports
  it, which is the ADR's whole premise and the thing to re-check if it ever fails.
- **It differs from its `notifications/`/`email/` siblings in one respect, deliberately.** Those
  have a real development-mode success path because real features call them today. This one has no
  caller anywhere — course checkout does not exist — so `ConsolePaymentProvider.create_payment`
  refuses **unconditionally**, not only in production; succeeding would fabricate a transaction for
  a flow that is not built. The production check stays anyway, in the same shape as its siblings, so
  the day a real provider replaces this one, the line that must never be deleted is already the one
  being overwritten.
- 729 backend tests (was 724). `make check` clean.
- **Sequencing after this** is in the pillar assessment below: course checkout (~2 sprints, its own
  ADR for `Order`/`Entitlement` and the real gateway implementation), then gig as its own module with
  its own ADR. Neither is started.

### Sprint 35 — Epic B3, verified evidence (done 2026-09-26)

`docs/scope-reconciliation.md`'s postscript named the sharpest, cheapest finding of the whole
ledger: three of four `SKILL_SOURCES` had no writer outside `scripts/seed_candidates.py`, so
`EVIDENCE_WEIGHT_SHARE = 0.10` was a constant for every real candidate. This gives two of them one.

- **BL-3.1, the assessment-provider webhook.** `api/adapters/assessment/` is a `AssessmentProvider`
  protocol (`parse_result`, turning one vendor's payload into a normalised phone/standard-code/
  pass-fail) plus `ConsoleAssessmentProvider`, the reference implementation BL-3.1's own acceptance
  criteria call for pending "a signed provider partnership" (a business dependency, not an
  engineering one). `POST /partners/assessment-results` resolves the phone to a candidate (lazily
  creating their profile if they have never opened it, the same rule `/me/matches` follows) and the
  standard code to a `Skill` via the new `get_skill_by_nos_code` (nos_code is unique in the corpus,
  unlike names or sector-local ids), then writes through `record_verified_skill` -- never a second
  construction site. A failed attempt writes nothing and is not an error; an unknown candidate or
  standard is a 404, not a silent 200, because a real partner needs to know a result did not land.
- **No new table, deliberately.** ADR-023 names "assessment results" among the data an encryption
  path must exist for before it is collected, and that path is unbuilt (§13.4 below). The webhook
  persists only a coarse pass/fail through the already-plaintext `CandidateSkill.source` column --
  never a score, a transcript, or free text -- and answers synchronously with what happened instead
  of writing an audit trail, which is also what a real integration partner actually needs.
- **`ServiceAccount.scope` stopped being a set of one.** `assessment:write` joins `read`
  (migration 0032, hand-written CHECK widen, the established pattern); `require_service_scope()` is
  a second question beside `get_service_account`'s -- not just which partner, but what they may do.
  A read-only key against the webhook is a 403, not a 401: the key is real, ADR-038's rule that an
  authenticated identity's insufficient permission is a 403 applies to a service account too.
- **BL-3.2, an operator-verified certification.** `CandidateCertification` gained
  `verified_at`/`verified_by`/`verification_note` (migration 0033), with the same evidence CHECK
  ADR-042 put on `tenants.verified_at` -- a badge with no evidence must not be representable,
  whichever table it lives on. Deliberately simpler than `tenant_verification_events`: a candidate's
  own certification is theirs to edit or delete at any time, unlike an organisation's badge, so
  there is no symmetrical need for an append-only history an operator must consult before acting.
  `OPS_CANDIDATE_VERIFY` is a new operator permission; `GET /ops/candidates/certifications` is the
  queue (certifications naming a standard, not yet verified) and `POST .../verify` the decision,
  which writes through `record_verified_skill` in the same transaction as the certification's own
  columns.
- **`_write_skills` gained a `source` parameter and an upgrade-only rule.** Re-adding a
  self-declared skill can never downgrade one already `assessed` or `certified` --
  `SKILL_SOURCES.index(new) > SKILL_SOURCES.index(existing)` before overwriting, and a test cross-
  checks that tuple's order against `matching.scoring.EVIDENCE_WEIGHT`'s own ascending order, since
  the two silently drifting apart would be a scoring regression nothing else would catch.
- **Verified live against the seeded database, not only pytest**: issued a real `assessment:write`
  API key, POSTed a pass for the seeded candidate `+919000000001` against a real NOS code
  (`MSME/ASC/N1514`) and watched `CandidateSkill.source` land as `assessed`; a read-only key against
  the same route came back 403, and against the pre-existing `/partners/jobs` still 200. Signed in
  as the existing operator (`hiring@apollo-care.example`), added a certification against the same
  candidate, verified it through `/ops/candidates/certifications/{id}/verify`, and confirmed
  `source='certified'`, `proficiency=4`, and the row leaving the queue. Both demo API keys revoked
  afterwards.
- 759 backend tests (was 729). `make check` clean; migrations 0032/0033 rehearsed down and up with
  zero further autogenerate drift; `make gen-api` regenerated, purely additive.

### Sprint 36 — semantic similarity, and the skill graph's foundation (done 2026-09-27)

BL-5.1/5.2 per `docs/HLD` §9.2 and ADR-036's own deferral ("deterministic overlap ships first so
there is a baseline to measure any addition against"); BL-6.1 alongside it, both NEXT in the
backlog's near-term sequence.

- **`api/adapters/embeddings/`** — an `EmbeddingProvider` protocol pinned to 384 dimensions
  (ADR-031) and `HashingEmbeddingProvider`, an honestly-labelled placeholder: deterministic feature
  hashing over lower-cased word tokens, not the ADR-013/031-mandated self-hosted
  sentence-transformers model. **Not silently substituted** — that model needs `sentence-
  transformers` added to `pyproject.toml` (torch, a ~470 MB download), which is an infrastructure
  decision flagged rather than made inside this story. Swapping it in later touches only
  `get_embedding_provider()`; nothing else in the pipeline knows which provider is behind the port.
- **`Job.embedding`/`CandidateProfile.embedding`**, migration 0034 — plus `embedding_provider`,
  `embedding_model`, `embedding_computed_at` on both (ADR-031: "every stored vector records the
  provider, model identifier and model version"). `NULL` means "needs (re)computing", not "has
  none" — a skill write sets it back to `NULL` (`marketplace.profile_service._write_skills` /
  `remove_skill`; `marketplace.publishing._write_skills`) rather than leaving a vector that no
  longer describes what the row now holds.
- **`matching.tasks.refresh_embeddings`** is the only thing that ever fills a `NULL` back in — a
  worker cron every two minutes, the same "claim by writing, cheap when nothing is NULL" shape the
  alert sweep uses, never inside a request or inside `scoring.py` (ADR-036). Text comes from
  `skills.embedding_text_for_skills`: performance criteria, never a skill's own title ("OJT" and
  "Project" are real unit titles that embed to noise on their own, per the outstanding-work note
  this closes); falls back to a skill's `description`, then its `name`, for the ~35% of standards
  with none.
- **`score_match` gained `job_embedding`/`candidate_embedding` and a `semantic` weight, default 0.0
  in both `ScoreWeights` and `Settings.match_weight_semantic`.** Cosine similarity, clamped to
  `[0, 1]` (never a penalty for a dissimilar or missing embedding), added into `raw` *before* the
  mandatory cap so it narrows toward the cap like every other component rather than escaping it —
  and `raw = min(raw, 1.0)` is a new safety clamp, since the four original weights already sum to
  1.0 and `semantic` is additive on top rather than carved from an existing share. `make evaluate`
  prints the identical baseline — bit-for-bit, because the default weight is 0.
- **`SkillRelation`** (`api/modules/skills/graph.py`, migration 0035) — a typed (`implies`,
  `related_to`), weighted, directed edge between two skills. Explicitly the foundation only: no
  inference and no career-path output reads it yet (BL-6.2/6.3, held for the next planning cycle,
  per the backlog's own reprioritisation note). Left `skill_concepts` (Sprint 9's equivalence
  grouping) untouched — a different structure answering a different question.
- **Verified live against the seeded database**: ran `refresh_embeddings` directly — 20 published
  jobs and 20 of 40 candidate profiles got a real 384-dim vector (the other 20 have no declared
  skills, correctly left `NULL` rather than a meaningless zero vector); confirmed
  `embedding_provider='hashing'`, `embedding_model='feature-hash-word-v1'`. Re-fetched
  `/me/matches` for the seeded candidate with matches (`+919000000001`) and confirmed the known
  score (88) is unchanged. Worker restarted and its startup line lists `cron:refresh_embeddings`
  alongside the other four.
- 793 backend tests (was 759). `make check` clean; migrations 0034/0035 rehearsed down and up with
  zero autogenerate drift; `make gen-api` shows no new routes (this sprint is entirely internal to
  matching — no schema or endpoint changed).

### Sprint 37 — tiered operator authority, then gig work as a `Job` (done 2026-09-28)

Two pieces of direct owner instruction, in sequence, not a story picked off the backlog. First:
"reprioritise what is left in B7 and take up Epic B8 post that" — so BL-7.3, the only unbuilt piece
of Epic B7, shipped first. Second, arriving mid-design-review for Epic B8: "a gig work can also be
considered as a temporary job assignment and should be treated like a job in our system" — which
overrode ADR-045's own design (a wholly separate sibling module, written and reviewed but never
built) before a line of BL-8.2 was written.

**BL-7.3 — tiered operator authority (ADR-044).**

- `users.staff_tier` (`support`/`admin`) sits beside `is_staff`, with a CHECK pairing them
  (`is_staff` true iff `staff_tier` is not null). `TIER_PERMISSIONS` in `core/authorization.py`
  maps each tier to a `frozenset[Permission]`, with `assert TIER_PERMISSIONS["support"] <
  TIER_PERMISSIONS["admin"] == OPERATOR_PERMISSIONS` holding the two in a known relationship.
- `require_operator()`'s single 404 split into two answers, generalising ADR-038's rule one level
  up from tenant membership to operator tier: **404** if the caller is not staff at all (the same
  refusal a stranger gets), **403** if they are staff but this tier lacks the specific permission
  (they have already established standing as an operator, so the refusal can say so).
- `scripts/grant_staff.py --tier {support,admin}` is still the only writer of either column — no
  HTTP route grants either, the standing rule since Sprint 13 unrelaxed.
- Hit the harness's own permission-grant safety gate once while writing `STAFF_TIERS` into
  `identity/models.py` — a classifier distinct from normal tool-use permissions, triggered by
  defining new privilege-escalation logic. Stopped, explained, and re-implemented from a
  user-approved design rather than working around it.
- Migration 0036 backfills every existing `is_staff=true` row to `staff_tier='admin'`. Verified
  live: a fresh `support` operator reads the verification queue (200) but gets 403 on
  `OPS_ORG_VERIFY`; a stranger gets 404 on the identical URL; the pre-existing `admin` operator
  was backfilled and unaffected.

**Epic B8 — gig work reuses `Job`/`Application` (ADR-046, superseding ADR-045 §1-4).**

ADR-045 had argued from first principles that a gig is a different *kind* of market — a scheduled
need rather than a standing offer, proximity as a hard filter rather than a tie-break, a real
completion event, bidirectional reputation — and proposed four new tables in a new sibling module,
`api/modules/gig/`, with its own scorer. None of it was ever built. The owner's instruction
rejected the premise, not just the conclusion: the physics ADR-045 named are properties a `Job`
row can be given, not proof it cannot hold them. Verified against the actual code before writing
anything, not assumed: `open_job()`, `match_jobs`'s retrieval SQL, `score_match`, and the hourly
`close_expired_jobs` worker cron contain **zero references to `employment_type`** — a `Job` row
with `employment_type="gig"`, a real `closes_at` and a real `positions` count already flows
through the existing matching, ranking and auto-close pipeline with no code change to any of those
three files.

- **A genuine pre-existing bug, found while grounding the redesign and fixed as a prerequisite**:
  `publishing.py`'s `_PLAIN_FIELDS` tuple never included `"positions"` or `"closes_at"`, even
  though `JobIn` has always accepted both with real validation. `create_job`/`update_job` silently
  dropped whatever an employer submitted for either field — ten sprints latent, harmless for a
  permanent vacancy (nothing read them), fatal for a gig (both are load-bearing). No test anywhere
  exercised either field through the HTTP API; every existing test used direct ORM construction.
  Added a regression test that failed against the old code first, then fixed it.
- **`EMPLOYMENT_TYPES` gains `"gig"`**, shared by `Job.employment_type` and
  `CandidateProfile.preferred_employment_type` — the owner's own second decision, when asked
  directly whether a candidate should be able to state gig work as a preference. Two new
  invariants close the actual gap: `publishing._require_gig_has_a_place` refuses a gig whose
  district does not resolve (422, service-layer, same place `resolve_location` already runs — not
  a schema `NOT NULL`, because a permanent vacancy's district may still be null); `JobIn`'s
  validator refuses `employment_type="gig"` with `closes_at=None` ("a shift with no end is not a
  gig").
- **No second scorer — this satisfies ADR-037 rather than testing it.** ADR-045's case for a
  separate scorer rested entirely on gig-against-candidate being a different comparison from
  job-against-candidate. Once a gig is a `Job`, that premise is gone: `score_match` never asked
  what kind of `Job` it was scoring, and `matching._locality` keeps its existing tie-break role for
  gigs exactly as it does for permanent vacancies — the owner's instruction was to treat a gig as a
  job, not to give proximity a different role for one `employment_type`.
- **`Application` gains `completed`/`no_show`**, reachable only from `hired`, and only when the
  underlying `Job.employment_type == "gig"` — enforced in `employer_service.set_status` as a
  service-layer refusal (409/422), not a CHECK, since the rule spans two tables. A permanent
  vacancy's `hired` stays terminal exactly as before.
- **Full two-sided rating, not status-only** — the owner's explicit scope choice when asked
  directly. New table `application_reviews`: `subject_role ∈ {poster, worker}` names who the
  rating is *about*, never who wrote it, so `UNIQUE (application_id, subject_role)` makes each
  direction write-once without one party's review waiting on the other's row to exist. Reviewable
  only once `Application.status == "completed"` — `no_show` is deliberately not reviewable,
  ADR-045's own reasoning carried forward unchanged: a no-show is evidence about the cancellation,
  which the status already carries. `review_service.py` sits beside `service.py`/
  `employer_service.py` in `applications/`, reused from both identity contexts (`POST
  /me/applications/{id}/review` and `POST .../applications/{id}/review`).
- **No new module.** Everything landed in the two modules that already own the concepts —
  `marketplace/` for the posting-side invariant, `applications/` for the outcome and the review.
  This formally supersedes BL-8.2's original acceptance criteria ("does not extend
  `marketplace.Job`") and ADR-045 §1-4; ADR-045's §5 (no payment, no payout) is untouched.
- **One `Job` row per shift/date, stated as the shape rather than deferred as a gap.** A recurring
  gig ("every Saturday for a month") is multiple postings, the same way a staffing agency books
  each shift separately — building a multi-shift sub-model would reintroduce the complexity the
  owner's steer was deliberately avoiding.
- **Foundation only, by the same discipline `SkillRelation` shipped under**: `application_reviews`
  has a writer and no reader. No aggregate rating, no completion-count badge, and reputation must
  never feed `score_match` without its own design pass following `weights_from_settings()`'s
  precedent (a value passed in, never read inside the scorer).
- ~~**The frontend gap is named, not routed around.**~~ **Closed the same day — see the
  follow-up below.** It was worse than "named": the gap broke the web build.
- **Live-verified end to end against the running dev server and seeded data**, not just pytest:
  posted a real gig via `curl` in Chennai/Tamil Nadu requiring a skill the seeded candidate
  `+919000000001` actually holds — `positions`/`closes_at` persisted (the bug-fix proof), and the
  gig ranked at the top of that candidate's real `GET /me/matches` (score 96, district match) with
  zero code changes to `matching/service.py` or `scoring.py`. Walked a second real application
  through `applied → shortlisted → hired → completed`, submitted both review directions (201 each),
  confirmed a duplicate direction (409), a review before `completed` (409), and a review on a
  `no_show` application (409) are all refused. `make gen-api`'s diff widened three unions and
  removed nothing — which was reported here as "purely additive", and was not: a widened union
  breaks every hand-written narrower copy of it downstream (see the follow-up).
- 827 backend tests (was 793), 259 web tests unchanged (backend-only sprint). `make check` clean;
  migration 0036 (tiers) and 0037 (gig + outcomes + reviews) each rehearsed down and up with zero
  autogenerate drift; `make evaluate` printed the identical 34 pairs/7 orderings/16 course
  expectations — bit-for-bit, since nothing in `matching/` or `scoring.py` changed.
- ADR-044 (operator tiers) and ADR-046 (gig reuses `Job`, superseding ADR-045 §1-4) both written to
  `docs/adr/architecture-decisions.md`, with amendment-record bullets at the top of the file.
  `docs/IISM-Product-Backlog.docx` updated: BL-7.3, BL-8.1 and BL-8.2 marked done, the Epic B8
  intro and the "Following This Window" sequence table both rewritten to describe what was
  actually built rather than what was originally proposed.

**Follow-up, 2026-09-28 — a pre-sprint architecture audit found Sprint 37 had shipped broken.**

- **The pushed branch did not build.** `npx tsc --noEmit` failed in `SearchResults.tsx`: the
  regenerated client typed `employment_type` with `"gig"`, and `JobBrowser.tsx` still declared a
  four-value copy. `npm test` was green because Vitest does not type-check, and CI never ran
  because it triggers on pull requests and `main` only (§10). The sprint's own claim that the
  client diff was "purely additive" was the error — additive to the schema, breaking downstream.
- **Fixed by deleting copies, not by adding a value to each.** `lib/profile.ts`'s
  `EMPLOYMENT_TYPES` is now the one list; `JobBrowser` and `JobEditor` import it.
  `ApplicationList` had `application.status as Status` onto a hand-written five-value union —
  the cast is what hid `completed`/`no_show` from the compiler — and now derives `Status` from
  `components["schemas"]["ApplicationOut"]["status"]`, so its colour map is exhaustive and the
  next status is a compile error. Labels for `gig`, `completed` and `no_show` in `en`/`hi`/`ms`;
  `ApplicationList.test.tsx` renders both statuses and **fails against the previous messages**
  (`MISSING_MESSAGE`), checked before trusting it. The "completed" hint does not promise a
  rating screen, because none exists yet.
- **Two counts were wrong in Sprint 37's own backend.** A finished gig worker moves `hired` →
  `completed`, and both `_close_if_filled` and the programme report counted `status == "hired"`
  alone — so a two-position gig took a third person once the first had finished, and the report
  dropped everybody whose gig ended. Two named sets in `applications/models.py`, because they are
  different questions: `FILLED_STATUSES = (hired, completed)` for "occupies a position" — a
  **no-show leaves the seat empty** (the owner's call) — and `WAS_HIRED_STATUSES` adding
  `no_show` for "was this person ever hired". Both regression tests fail against the old code.
- **The module-boundary rule in `CLAUDE.md` was half fiction.** "Never import another module's
  `.models`" — about sixty imports do, enforced by nothing. The half that *is* true everywhere —
  no module imports another's `service`/`*_service`/`routes`/`*_routes` — is now
  `tests/test_module_boundaries.py`, which asserts it found the modules and the cross-module
  imports first, and feeds its detector a known-bad snippet. `CLAUDE.md` states the real rule
  and names the shared-models debt an ADR-014 split would have to pay.
- Verified: `tsc`, `eslint`, `next build` and the first-load budget clean; 832 backend and 260 web
  tests; the seeded candidate's `/en/applications` and `/hi/applications` show "Completed" /
  "काम पूरा हुआ" and "Did not attend" / "उपस्थित नहीं हुए" in the list and in the notices, and
  the gig's job page shows its employment type in both languages with no raw key anywhere.
- **Still open, deliberately:** the employer inbox offers only shortlist / not suitable / hire, so
  `completed`, `no_show` and both review directions are reachable by API only. That is a real
  follow-up story (a gig-specific inbox action plus a rating form), not a label.

### Sprint 38 — closing ADR-025's structural gate, not its volume gate (done 2026-09-29)

Per the backlog's own sequence, next was `BL-1.2`/`BL-1.3`. Checked against the code rather than
the backlog document: `BL-1.2` (the payment adapter port) was already done in Sprint 34 — the
document's `[NEXT]` tag was simply stale. `BL-1.3` (the billing module) genuinely is not built, and
is not a free pick: ADR-025 requires a successor ADR citing three metrics before any billing code is
written, and ADR-043 (Sprint 34) explicitly declined to claim that gate was passed — precision@5
was citable, click-through was "joinable, not populated," and enrolment conversion "has no surface
at all." Asked how to proceed, the owner chose: close the gate first, then build `BL-1.3` — ADR-043's
own named "Option 4."

- **`course_interests` gained a fourth status, `"enrolled"`, rather than a new table or module**
  (migration 0038, ADR-047). It slots in beside `"contacted"` in `PROVIDER_STATUSES` at the same
  unverified, self-reported trust level, reusing the existing `PATCH .../interests/{id}` route with
  **zero route or handler changes** — the whole surface a provider needed already existed, it just
  had nowhere to report an enrolment. `LIVE_STATUSES` gained it too, so an enrolled learner's contact
  stays visible rather than disappearing the way a withdrawal's does.
- **`scripts/report_conversion_metrics.py` (`make monetisation-metrics`)** is the sibling `make
  evaluate` never had: click-through from `course_recommended`/`course_opened` pairs already
  carrying `user_id` and `subject_id` since Sprint 24/33 (nobody had ever queried it), and enrolment
  conversion from `course_interests.status`. Both filtered to `subject_type="course"` explicitly —
  the same pre-migration-0025 trap `matching/service.py`'s own docstring already names.
- **Verified live, not just in pytest — and the numbers are real but small, deliberately reported
  as such.** Seeded a couple of `"enrolled"` rows into `scripts/seed_candidates.py`'s
  `COURSE_INTERESTS`, then generated genuine traffic against the running dev server: signed in as
  `+919000000002`, called `/me/matches/general-duty-assistant-chennai` (which recorded a real
  `course_recommended` row) and `POST /me/events/course-opened` for the course it suggested —
  `make monetisation-metrics` then printed a real `1/5 (20.0%)` click-through. Signed in as
  `admin@nsdc-healthcare-academy.example` and `PATCH`ed a live interest to `"enrolled"` through the
  actual API (200); the same call against a withdrawn interest still refused with 409, as before.
  Enrolment conversion read `3/15 (20.0%)` afterward. **Neither number is fabricated, and neither is
  strong** — this is a handful of seeded actors on a dev database, not real product usage, and the
  report script says so in its own output rather than only in this file.
- **`cd web && npx tsc --noEmit` was run this time, unlike Sprint 37's first pass**, and passed
  clean against the widened `InterestStatus`/`ProviderStatus` unions. The frontend gap is real but
  benign: `ProviderInbox.tsx` hardcodes `{ status: "contacted" }`, so a provider has no button to
  mark somebody enrolled through the web UI today — named in ADR-047 as a small follow-up story,
  not bundled here because it was never part of what the metric needed.
- **This does not authorise `BL-1.3`.** ADR-047 is explicit that it closes the *structural* gap
  only; the *volume* gap — real traffic — cannot be closed by writing more code, and the ADR takes
  no position on whether the owner should override it (the same kind of call already made once this
  session for Epic B8 over ADR-045) or wait for real usage. That decision is Sprint 39's, not this
  one's.
- Verified: `make check` (835 backend tests, 3 new), `ruff`/`mypy` clean, migration 0038 rehearsed
  down-and-up with `alembic check` reporting zero drift (the two seeded `"enrolled"` rows correctly
  fell back to `"contacted"` on downgrade, never to `"registered"`), `make evaluate` bit-identical
  (34/7/16, untouched by this change), and `make gen-api`'s diff purely additive (confirmed by
  reading the diff, not assumed).
- **The owner's answer (2026-09-29): wait for real traffic, do not override.** Asked directly which
  way to resolve the open question above, the instruction was "wait for real traffic before billing
  code gets written." `BL-1.3` therefore stays not started — this is now a standing decision, not an
  open question, until real usage moves either metric or the owner says otherwise. Do not treat a
  future re-run of `make monetisation-metrics` showing a slightly larger denominator as license to
  start `BL-1.3` without checking back — nothing in this decision named a threshold.

### Sprint 39 — Epic B10, actor dashboards (done, before this session)

Every actor type (candidate, employer, course provider, operator, government agency) gets a real
numbers dashboard on sign-in — `StatTile` rows only, composed from data each actor's own module
already computed. No new scorer, no cross-module "dashboard" service (ADR-014). This is the
foundation Sprint 40 later replaced the *rendering* of, without touching the backend numbers.

### Sprint 40 — dashboard visualisation (Epic B11), a cross-sector matching fix, and landing it on `main` (done 2026-10-02)

Two unrelated pieces of work, planned separately and executed back to back, plus a third,
unplanned one needed just to get the result onto `main`.

**Part 1 — charts and drilldowns on all five dashboards, zero new dependencies.** `web/package.json`
had nothing chart-shaped before this (Radix dialog/progress/slot, TanStack Query, next-intl,
openapi-fetch). Rather than add a charting library — even the lightest costs 15–50 KB against a
~62 KB shared first-load budget, and would be a second way to draw a bar next to `CoverageBar`'s
existing hand-rolled one — four SVG/Tailwind primitives were built in a new, deliberately
barrel-excluded `web/src/components/charts/`: `RankedBarList`, `ProgressRing`, `StatusFunnel`, and
`TrendSparkline` (built and tested, left unwired — no backend aggregation feeds it yet). Each
dashboard's backend `dashboard()`/`platform_dashboard()` function was extended to return the
per-row array it was already computing and discarding (`job_pools()`, `counts_by_course()`,
`market_scarce_skills()`, `scored[:5]` from `match_jobs()`) — one exception,
`GET /ops/programmes/{name}/districts`, is a genuinely new, heavier `GROUP BY` query and got its own
endpoint rather than riding the base report. Drilldowns are a local `useState` on the dashboard
component revealing a panel beneath the clicked row — `aria-expanded`/`aria-controls`, not a
`Dialog` (reserved for true modal interruptions) and not a route. **Verified live in a browser**,
not just in tests: signed in as each of the three reachable demo actors and clicked a drilldown row
on the candidate dashboard — it correctly reuses the pre-existing `CoverageBar`/`LevelScale`
component with that match's own fields, exactly as planned, rather than a new detail UI.

**Part 2 — the same bug, twice, is a systemic one.** Reported live: a candidate profile's role
search for `"software engineer"` returned **"Certificate course in Coding Skills"** — an
entry-level certificate — instead of anything resembling a software engineering qualification. This
is the second time this exact shape of bug was hit this project: an earlier session had hand-added
25 IT/tech `role_aliases.py` entries, including that exact wrong mapping, to fix a *different*
reported symptom (`"tech"` surfacing irrelevant "Technician" roles in search). Investigated rather
than just re-patched: `role_aliases.py` held 124 hand-written entries against **3,442 real, current,
standards-bearing qualification packs across 40 sectors** — ~3.6% coverage. Hand-writing one Python
dict entry per lay term, one sector at a time, is not a fix that scales; it is the same bug
recurring under a different term every time someone types a phrase nobody has curated yet. Four
changes, landed together:

- **Fixed the immediate mapping**: `"software engineer"` now points at `"Software Development"`
  (`MSU/SSC/CRS0033`, NSQF 6, 10 standards), not the Coding Skills certificate. Verified live via
  `GET /roles/search?q=software+engineer` after the fix: Software Development ranks first with
  `match_kind: "alias"`, followed by genuinely related roles (Software Engineering Fundamentals,
  Embedded Software Engineer, Software Test Engineer) via the prefix/contains tiers.
- **`role_aliases` moved from a Python dict to a database table** (migration 0039), mirroring the
  existing `SkillAlias` pattern. `role_aliases.py`'s hand-authored dict is still the source of truth
  and the thing a reviewer reads in a diff — `scripts/seed_skills.py` projects it into the table on
  every run, the same relationship `SKILLS` already has to `skill_aliases`. This doesn't by itself
  write the missing ~3,300 entries; it removes the actual bottleneck (a code change + PR + deploy
  for every new synonym), so filling the gap can become a data-entry or admin-screen problem later
  rather than an engineering one now.
- **Generic word-synonym expansion** (`WORD_SYNONYMS`/`expand_query_terms` in `api/core/text.py`,
  tested in isolation in the new `tests/test_text.py`): `tech→technology`, `dev→developer`,
  `eng→engineer`, and similar sector-agnostic abbreviations, applied as additional OR terms in both
  `_text_filter()` (the public `/jobs`/`/search` path, `api/modules/marketplace/service.py`) and
  `search_roles()`. This is what actually fixed the original `"tech"` symptom's job-search half:
  verified live, `/en/search?q=tech` now surfaces real IT-sector jobs (a Business Analyst role, a
  Web Designing & Multimedia trainee programme) alongside the literal `%tech%` substring matches on
  "Technician" (which were never a bug — "tech" genuinely is a substring of "Technician" — just an
  incomplete answer on its own).
- **A real embedding provider, built and tested, switched off everywhere by default.**
  `HashingEmbeddingProvider` was always documented as an honest placeholder for the model ADR-013/031
  already mandate by name — self-hosted `sentence-transformers`,
  `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions (ADR-031's fixed size), CPU-only,
  multilingual for ADR-033's Hindi requirement. `api/adapters/embeddings/sentence_transformer.py` is
  that adapter; `QualificationPack` gained `embedding`/`embedding_provider`/`embedding_model`/
  `embedding_computed_at` columns (migration 0040, same "NULL means needs computing" convention as
  migration 0034), and `api/modules/skills/tasks.py`'s `refresh_role_embeddings` cron fills them in
  (registered in `api/worker.py`, **and the running worker had to be restarted to pick it up** — see
  the new §8 gotcha). `search_roles()` only runs the semantic tier when
  `get_embedding_provider().name != "hashing"`, which it is nowhere today — `embedding_provider` in
  `api/core/config.py` defaults to `"hashing"`. **Real, honestly-reported calibration finding**:
  measuring actual cosine similarities with the real model showed it does *not* cleanly separate
  true/false role-matching pairs at this short-phrase task — an unrelated pair ("cashier"/"AC
  Technician") scored *higher* (0.329) than a genuinely related one ("ward boy"/"General Duty
  Assistant", 0.319). `SEMANTIC_MIN_SIMILARITY = 0.30` is a conservative placeholder threshold,
  explicitly flagged as needing a real tuning pass before anyone flips the config switch — the same
  discipline `SEMANTIC_WEIGHT` already established on the scoring side of this ADR.
- **The mandatory-gap cap now tapers with coverage.** A second, related bug found while
  investigating: `MANDATORY_GAP_CAP` (0.45) was flat regardless of how much real overlap sat behind
  it, so a candidate whose only shared standard was a generic, widely-reused one (e.g.
  `employability-skills-60-hours-dgt-vsq-n0102`, required by dozens of unrelated jobs) could land in
  the same low-40s band as someone genuinely one standard short of a strong match. `scoring.py`
  gained `MIN_COVERAGE_FOR_CAP = 0.40`; below that coverage the cap scales down proportionally
  (`effective_cap *= coverage / MIN_COVERAGE_FOR_CAP`) rather than applying flat. `scoring.py` still
  takes `ScoreWeights` as a passed-in value and reads no settings itself (ADR-036 intact). Verified
  against `make evaluate`: the orderings and `capped_by_mandatory` booleans are bit-identical, but
  several previously-45 scores now correctly read lower (e.g. `visual-merchandiser-mumbai` 45→31,
  `ecg-technician-chennai` and others down to 16–35).

**Part 3 — an unplanned detour: getting it onto `main` needed fixing CI, which needed resolving a
merge conflict.** PR #12 (carrying the role-search fix) had red CI on both jobs, from **pre-existing,
unrelated** vulnerabilities — `pyjwt`/`urllib3` (API job, `pip-audit`) and a critical Next.js RCE,
GHSA-vcvr-r3jv-pc5j (Web job, `npm audit --omit=dev --audit-level=high`). Asked how far to go, the
owner chose "bump the vulnerable packages now." Both bumps were verified clean against the exact CI
commands (not just "tests pass") before pushing: `pip-audit` clean + 870 backend tests; `npm audit`
clean + `tsc --noEmit` + `eslint` + 288 web tests + `next build` + the bundle budget. **Pushing that
fix then surfaced a real merge conflict against `main`**: a Dependabot PR bumping the same
`python` group (`alembic`, `pyjwt`, `pymongo`, `ruff`) had already merged into `main` while this
branch was open, and both sides touched the same `pyjwt` block in `uv.lock`. Resolved by keeping
this branch's newer `pyjwt==2.15.1` (already CVE-verified) over Dependabot's `2.14.0`, taking every
other bump from `main` as-is, then re-running `uv lock` to confirm the hand-resolved file was
self-consistent and re-verifying the whole stack (`pip-audit`, `make check` — ruff/mypy/870 tests,
`alembic check` for drift from the `alembic` 1.19.2→1.20.0 bump). See the new §8 gotcha for the
general shape of this trap. The resulting merge commit (`8e7e179`) is what PR #14 actually merged
into `main` as `b15e0c6`; **PR #12 and #13 show as closed-without-merging in GitHub's history** —
not failures, just earlier attempts GitHub auto-closed once #14 (for the same branch) merged.

**Verified end to end, live, after landing**: `make check-role-aliases` and `make evaluate` both
clean on `main`; all three containers (Postgres/Redis/Mongo) and all three dev processes
(api/worker/web) confirmed healthy after restarting each cleanly on `main`; a real browser session
against each of the four reachable seeded demo accounts (`+919000000001`,
`hiring@apollo-care.example` as both employer *and* operator, `admin@skillbridge-institute.example`)
showing real charts, real drilldowns, and the corrected search results — not just passing tests.

### Sprint 41 — finish the half-built, then two differentiators (done 2026-10-03, committed and pushed on `sprint-41`)

The audit found the strongest parts of the product (the explainable gap, the course loop) and
several features built on the server and never shown. The market research found nobody else tells a
rejected candidate what they were missing, or lets an employer sponsor the missing standard.
Owner decisions: monetisation and external integrations deferred; Standard size; the learner notice
is **in-app only**, no email.

- **Notices say the right thing.** `Notices.tsx` rendered every notice as "moved your application",
  so a job alert read as a status change. It now switches on `template`. It also passes `useNow()`
  to `relativeTime` — without it next-intl logs an `ENVIRONMENT_FALLBACK` error per notice, which is
  what the Next dev "1 issue" badge was (it predates this sprint).
- **Gig completion.** `completed`/`no_show` are terminal on the server (a finished row cannot go back
  to `hired`), shown on the employer card. Dashboards count `FILLED_STATUSES` rather than `hired`.
- **Two-sided ratings and reputation.** `ReviewControl` serves both directions; the API answers 409
  on a duplicate and offers no way to ask first, so both application payloads carry `reviewed` and
  the control disappears once used. Average and count appear on a poster's job page, the employer
  dashboard and the worker's own dashboard — **never on the candidate card** (ADR-037) — and a
  poster with no ratings is `None`, not 0.0.
- **Enrolled, and the learner is told.** `InterestList`/`ProviderInbox` had hidden `enrolled`
  (a raw message key, no button, a provider could downgrade it). `provider_service.set_status`
  queues an in-app `course_interest_status_changed` notice on a *change* to `contacted`/`enrolled`;
  a repeat tells nobody twice.
- **Certification linking.** The profile form can finally link a certification to a standard, so the
  operator queue is no longer empty by construction. Editing used to send `skill` where the server
  expects `skill_slug` and silently unlinked it; changing the standard now clears `verified_at`.
- **Why not me.** `GET /me/applications/{id}/gap` (404 for anyone else's), computed **at view time**
  through `matching.score_profiles` and `courses_closing_gap` and never recorded, so the panel
  shrinks as the candidate closes the gap. The rejection notice links to `/applications` and **never
  carries the gap in its payload** — the outbox and email can reach a shared address. A closed
  vacancy still resolves (`match_job_by_slug` would refuse it).
- **Hire and train (ADR-048).** `alerts/sponsorship.py`: an employer opens the one-standard-short
  card, sees the courses for that standard, and may offer to sponsor. The `C-XXXXXXXX` reference is a
  handle, not a key — it resolves server-side only inside that vacancy's own near-miss pool, and an
  unknown vacancy, an out-of-pool reference and a not-actually-near candidate are all the same 404.
  `sponsor_intents` is unique on `(job_id, profile_id)`. The offer obeys the alerts' rules (opt-out,
  shared daily cap) and the response is identical whether or not the candidate was notified, so an
  opt-out never leaks. Refused (422) when no course teaches the standard. The candidate gets one
  notice naming the organisation, standard and course, and applies if they choose — the employer
  never learns who they are before that. Erasure covers the new table. Mutation-tested: removing the
  opt-out check or the near-pool filter each fails a test.
- **Hardening bundle** (each with a test that fails on the old code): re-inviting an address whose
  invitation expired no longer 500s; `drain` uses `FOR UPDATE SKIP LOCKED` so two workers cannot
  double-send; candidate dashboard `match_count` no longer caps at 20; the embedding sweeps recompute
  rows whose `embedding_model` differs and skip the role sweep under the hashing provider;
  `programme_by_district` groups by district id, not name; `_scarce_skills` counts only open
  vacancies as demand.
- **Two migrations, not one.** `0041` widens the notification-template CHECK; `0042` creates
  `sponsor_intents` and widens the analytics CHECK. Both hand-written with frozen value lists;
  round-trip down/up and `alembic check` clean.
- **Verified.** `make check` 928 passed; web 346 passed with `tsc` and `eslint` clean; a 31-check
  live script against the running API (demo organisations, throwaway candidates, all erased); in the
  browser: the "See what you were missing" panel and "Train and hire" on exactly the one card that is
  one mandatory standard short. Heaviest route 678 of 684 KB — **6 KB of headroom**.
- **Left for later:** ~~career ladders~~ **(built in Sprint 42, ADR-049)**, a district skill-gap view,
  course credit chips, and an **owner rule** on withdraw-then-reapply (it currently resets the
  employer's decision).

### Sprint 42 — career ladders: where could I move next (done 2026-10-03, committed and pushed on `sprint-41`)

The one differentiator from the market research still unbuilt. ADR-008 and BL-6.3 assumed an inference
graph (`SkillRelation`); it has **zero rows**, and the national data names no prerequisite between two
roles (entry routes carry a *minimum prior level* in 1,882 packs and name a pack in five). So a ladder
is **derived at read time from qualification data, states the evidence for every step, and stores
nothing** — ADR-049. The page is **`/career-paths`**, because `/careers` is the company's own hiring
placeholder, linked from the footer.

- **Three modules each own one question.** `skills.roles_above` (which roles build on one), the one
  scorer through `matching.score_against_roles` (the person's fit; ADR-037, no second scorer), and
  `matching.courses_closing_gap`. A new leaf module `api/modules/careers/` composes them; it owns no
  table, so erasure and export have nothing to cover.
- **What counts as a step.** Higher level by at most 2.0; at least one **specific** shared compulsory
  standard, compared at concept level; the pack is current and has compulsory standards of its own;
  Divyangjan-track packs are left out unless the anchor is one. Same occupation and shared NCO code are
  *corroboration* — shown, tie-breaking, never grounds.
- **A standard compulsory in three or more sectors is generic and is not evidence** (81 of 13,618:
  "Employability Skills" and the like). Without that rule a General Duty Assistant "led" to an Automotive
  technician through one shared employability unit. This was found by looking at real output, not by a
  test: the first version of the rule passed every fixture and read as nonsense on the live corpus.
- **One rule for "which pack is the role".** The representative-pack ordering was embedded in role
  search's SQL; copying it is how the two would drift, so it is `ROLE_REPRESENTATIVE_ORDER`, used by
  both. Proved byte-identical on 699 real queries (3,015 hits) before and after, and a test holds the
  ladder's pick to role search's.
- **The starting role is the person's choice, or a guess trusted only on an exact/alias match of their own
  words** (latest current job title, then preferred roles), flagged `guessed` and shown as one. A prefix,
  a substring or a typo is a guess about a guess, and a ladder from the wrong role is about somebody else.
- **Measured over the whole corpus (4,340 roles with compulsory standards): 38% have a step**; median
  query 57 ms, p95 72 ms. **By sector it is very uneven**: BFSI 0% of 129, Information Technology Sector
  1% of 178, Instrumentation 4%, Electronics 6% of 218, IT-ITeS 8% of 191, Management 12% of 319 — those
  sectors give every pack its own standards, so nothing is shared across levels. The page says "we found
  none … that can mean there is none, or that the data does not link them", not "there is none".
- **A looser rule was measured and deliberately not adopted.** Admitting "same occupation, higher level"
  lifts a 724-role sample from 39% to 60% (IT-ITeS 11% → 65%) but 27% of those steps then share no
  standard at all, and narrowing it by occupation size (≤15/≤30 packs) or by sub-sector (52%) left 16–24%
  of them in. It is a weaker claim, and mixing it with the first would show them as equal. If it is ever
  adopted it must be a **separately labelled weaker tier**. The real fix for the dead sectors is data.
- **Cost:** scoring batches (six statements however many roles); the course lookup is six statements per
  step shown, eight steps at most — a fixed ceiling, with a test.
- **A real bug the first test found:** `same_occupation` is NULL, not false, for a pack with no
  occupation, and Postgres sorts NULLs *first* on `DESC` — so uncorroborated steps ranked **ahead** of
  corroborated ones. Fixed with `coalesce(..., false)`; the Python layer's `bool()` had been hiding it.
- **Verified.** `make check` 972 passed (928 + 44 new across three files); web 356; `tsc`/`eslint`
  clean; `make evaluate` — all 34 golden pairs, 7 orderings and 16 course expectations hold; migration 0043
  round-trips and `alembic check` is clean; the build adds `/[locale]/career-paths` and **no existing
  route grew** (heaviest still `/profile` at 678 of 684 KB, `/matches` 661); live against the real corpus as
  the seeded demo candidate, both locales, in the browser. Each ladder rule has a test where it is the
  *only* reason a row is out, and removing each rule fails exactly its own test.
- **A layout bug found in the browser, not by a test:** `SkillChip` (shared by the match page, the rejection
  panel and now this) was three unwrapped columns, so on a phone a long standard name collapsed to a word
  a line and the code ran off the card. It now wraps (`flex-wrap`, `max-w-full`).
- **Left for later:** the weaker-tier question above; a stored "current role" on the profile (a migration
  and a consent-style act); inference from `SkillRelation` (BL-6.2, still `[LATER]`); pay or demand on a step.

### Sprint 43 — role search you can trust, and two small stories (done 2026-10-04, merged in PR #18)

Career ladders start from `search_roles`, so a wrong search result now starts a wrong ladder. The
investigation that opened this sprint ran the search against the **real corpus**, which the small
fixture corpus never could, and found problems that matter more than the "3.6% alias coverage" figure
the backlog quoted. (That figure was aliases over packs; the real coverage is **43 distinct roles of
3,417, 1.3%**, in 17 of 43 sectors.) Owner decisions: scope = role-search trust plus two small stories;
reapply = block withdrawing a rejection; disability-track packs = demoted unless asked for and never an
alias target; **no curated alias batch** (lay terms are labour-market knowledge and nothing in the repo
contains them).

- **Disability-track packs, one tier lower (ADR-050).** Every one carries a `PWD/` code — 69 roles, no
  exception, 31 of them not named "Divyangjan" — and 57 exist *only* as a disability-track pack. Search now
  subtracts 1.01 from their match score unless the query asks (`divyang`, `pwd`, `disab`) or is exactly the
  title. **The first version put them in last place and was wrong on the real corpus**: `hr executive` has
  one literal match, a disability-track pack, and last place ranked it below "Executive Housekeeper". The
  first version also had no exact-title exemption, so `pressman` typed in full lost to something else. Both
  were found by diffing 726 real queries before and after, not by a fixture.
- **A half-typed alias beats a literal prefix on a tie** (`war` listed Warper above General Duty
  Assistant). **A multi-word query matches a title containing every word** (a new `words` kind, score 1.5).
  Each needed a fixture where that rule alone decides: removing the all-words *admission* clause failed
  nothing until a title was found whose trigram similarity (0.54) is under the 0.6 threshold.
- **Fourteen aliases pointed at a disability-track pack, and the checker could not see it.** Re-pointed two
  roles to their general twins (same code, different name), removed the seven retail keys (no general pack
  exists) and `cook` (the corpus has a role literally named Cook). `alias_problems()` now **fails** on that,
  and on a key that is a role's exact title aliased elsewhere — its first real run found two more
  (`web developer`, `security analyst`). It **reports** ambiguous prefixes without failing. Aliases 124 → 114.
- **BL-12.6.** `withdraw()` refused outside `applied`/`shortlisted` (`WITHDRAWABLE_STATUSES`), `apply()` says
  "not selected" for a rejection, `ApplyPanel` shows the employer's word and no Withdraw button, and a 409
  that arrives after the page was drawn is explained rather than "something went wrong". **Known limit:**
  rows already withdrawn after a rejection cannot be told apart, because the earlier status was overwritten.
  A hired application also cannot be withdrawn here (the message says to contact the employer) — that follows
  the approved plan and is a behaviour change worth a second look.
- **BL-9.2.** `set_verification` queues one email to the organisation **only when the badge flips**,
  before the commit, with a payload of the name and a link — no operator note, no address. Email only,
  because organisation members have no in-app inbox. An owner who signed up by phone alone has no address,
  so that organisation is **not** told (the row is `skipped`); that is stated, not hidden. Migration 0044.
- **Also:** `Notices` had no wording for `sponsor_offer`, so a sponsorship notice read "You have an update."
- **Verified.** `make check` 1,013 passed (972 + 41); web 364 (356 + 8) with `tsc` and `eslint` clean;
  `make evaluate` — all 34 golden pairs, 7 orderings, 16 course expectations hold; `alembic check` clean and
  0044 round-trips; no route grew (heaviest `/profile` 678 of 684 KB). **Mutation-tested**: every ranking
  rule, both checker rules, both withdraw guards and the flip rule each fail exactly their own test when
  removed. **Live** against the running API with a throwaway candidate and organisation: a rejection could
  not be withdrawn or reapplied, and the worker log showed exactly two emails to the throwaway owner
  (verified, revoked) for four operator decisions. Everything created was erased.
- **Role search before/after on 726 queries:** 11 top results changed, all explained — seven are the alias
  tie-break on three-letter prefixes, one is the demotion, three are the alias corrections. No exact-title
  query changed.
- **Left for later:** the curated alias batch; an operator alias screen (the seed deletes the table on every
  run, so edits would vanish — it needs a source-of-truth redesign first); scoring synonym-admitted rows
  (`mfg`, `tech`); BL-9.1; BL-12.7/12.8 (see the backlog).

### Sprint 44 — hand an organisation over in one act, and the race under it (done 2026-10-04, uncommitted)

BL-9.1 was recorded as "needs a locking decision". Making the decision found a fault older than the story.
Owner decisions, all taken as recommended: the person handing over **chooses** to stay as an admin or leave
(default admin); the new owner **is emailed**; the **erasure path is fixed in the same sprint**.

- **The race, reproduced before any fix (ADR-051).** `_refuse_if_last_owner` counted owners in one statement
  and the caller wrote in another. Two sessions run at once — A demotes B while B demotes A, or both leave —
  each saw two owners, each passed, and the owner count went to **0**. Account erasure asks the same question
  through its own grouped count and had the same gap, and authority was checked once at the start of the
  request, so an owner demoted in between still completed an owner-only act.
- **The fix.** `_lock_ownership` takes `SELECT ... FOR NO KEY UPDATE` on the tenant row at the start of
  `set_role`, `remove_member`/`leave`, the new `transfer_ownership` and (through `lock_ownership_of`, in
  ascending id order) `delete_account`. `FOR NO KEY UPDATE` rather than `FOR UPDATE` so an invitation being
  accepted — a membership insert, which takes `FOR KEY SHARE` on the tenant — is never held up.
  `_require_owner_now` then re-reads the caller's membership with `populate_existing` and refuses with 403 if
  they are no longer an owner. **Any new writer of `Membership.role` must take the lock first**; nothing
  enforces that mechanically.
- **The act.** `POST /org/{slug}/transfer-ownership` `{user_id, then: "admin"|"leave"}`. Target must already be
  a member (an invitation cannot carry `owner`; invite as an admin first), not the caller (422), not already an
  owner (409). Promotion and step-down commit together. One `ownership_transferred` event — not also
  `member_role_changed`, which would count one decision twice. The new owner is queued an email
  (`ownership_received`, `recipient_kind="user"`) **before** the commit; payload is the organisation's name and
  a link. A phone-only account is `skipped`, as everywhere. Migration 0045 widens two CHECKs by hand.
- **The UI** is an inline panel in `TeamPanel`, not a dialog (no Radix on this route's first load), with the
  server's own sentence shown on a refusal. **Deviation from the plan:** no typed-name gate. The plan copied it
  from organisation deletion, but that control destroys other people's records and this one does not, the new
  owner can reverse it, and the members endpoint does not even carry the organisation's name.
- **Testing needs committed rows.** The suite's `db` fixture is one rolled-back transaction, which cannot show
  two sessions interleaving, so `tests/test_ownership_race.py` builds its own organisation through the
  sessionmaker, widens the window with a sleep after the count (otherwise it passes by luck on a quiet
  machine) and deletes everything afterwards.
- **Verified.** `make check` 1,033 passed (1,013 + 20); web 371 (364 + 7) with `tsc` and `eslint` clean;
  `make evaluate` holds; `alembic check` clean and 0045 round-trips; no route grew (heaviest `/profile` 678 of
  684 KB). **Mutation-tested**: removing the lock (fails mutual demotion; fails the erasure race when removed
  there), the authority re-check, the already-owner refusal and the self-transfer refusal each fails its own
  test. **Live** with two throwaway organisations (13 of 13): an admin is refused, a sole owner still cannot
  leave, a handover swaps the roles and the old owner can no longer invite an admin, handing back
  with `leave` removes the leaver, exactly two `ownership_transferred` events and no `member_role_changed`, and
  the worker log showed exactly **two** ownership emails (plus the one invitation). Everything created was
  erased through the app's own routes. My first live script died on a script bug (separate `asyncio.run` calls
  sharing one engine across loops) and left two throwaway accounts and two organisations; they were found by
  tag, erased the same way and the database confirmed empty.
- **Not built:** inviting somebody **as** owner, handing over to a non-member, undo, approval by two owners, an
  in-app inbox for organisation members (the email is the only notice).
- **Left for later:** BL-12.7 district skill-gap view; BL-12.8 credit chips (blocked); BL-12.11 PWA device
  check; BL-12.14 synonym-row scoring; BL-12.15 operator alias screen; the curated alias batch; BL-5.3 real
  embeddings; BL-1.3 monetisation.

### Sprint 45 — the same blind spot, on the paths people use most, and abbreviations in role search (done 2026-10-04, uncommitted)

Sprint 44 found a race that had sat in the code for 19 sprints because the suite could not show it. This sprint
looked for the others, and **reproduced every suspicion with two real requests before changing anything**. Owner
decisions, as recommended: the audit plus BL-12.14 (not the district view), and the caps stay advisory.

- **A double-tap on Apply was a 500.** Two requests each find no row and each insert; the unique constraint refuses
  the second and nothing caught it. The data was right and the answer was wrong, on a phone where a retry is
  normal. Same for registering interest and saving a vacancy. **The first version of the test passed** — a
  brand-new candidate's first two requests race to create their *profile*, a different race that hid this one.
  `tests/concurrency.py` now creates the profile first. Lesson recorded in `CLAUDE.md`: a test that passes before the
  fix proves nothing.
- **Withdrawing against a decision was a lost update**, the serious one. `withdraw()` checked the status and then
  wrote; the employer's `set_status` checked "not withdrawn" and then wrote; run together both reported success. A
  withdrawal overwrote an employer's rejection (what BL-12.6 exists to prevent), and an employer's status change
  overwrote a withdrawal — for course interests that left the learner's contact visible on a row they had revoked.
- **Re-applying twice emailed the employer twice**: both requests find the same withdrawn row, so no constraint is
  involved and nothing fails.
- **The fix (ADR-052).** `SELECT ... FOR UPDATE` (`of=` the entity) on the row the check read, then re-read under
  it; where there is no row yet the unique constraint arbitrates, inside a savepoint (`begin_nested`), so the loser
  gets 409 "already applied" — or the winner's row for the idempotent save. **One planned lock was removed:** a
  learner's withdrawal of a course interest is unconditional and always the last word, so its check cannot go stale
  and the race is closed on the provider's side; mutation checking showed no test could fail without it.
- **Caps are not locked** (50 applications a day, 20 pending invitations, 60 skills): they deter abuse rather than
  guard an invariant. Under concurrency one can be exceeded by a few. **Not audited:** slug uniqueness on publish.
- **How the tests work.** Eight tests in `test_concurrency_audit.py`, on committed rows and real requests. The
  deterministic technique is to **hold a row lock from a third session and release it once `pg_stat_activity`
  shows both requests waiting**, so both have passed their check before either may write; the double-submits widen
  the window with a sleep instead. All eight fail on the unfixed code (`assert [201, 201] == [201, 409]`, an
  unhandled `UniqueViolationError`, both withdraw and decide returning 200) and pass four runs out of four.
  One expectation of mine was wrong and was corrected, not the code: *shortlist then withdraw* is a legal order
  where both succeed, so for that status the test asserts the final state instead of a single winner.
- **BL-12.14, and the backlog's premise was partly wrong.** `tech` leading with Technical and Technician is
  correct. The real defect: a synonym only applied to the whole query string, so `mfg technician` led with
  Technician - Mechatronics and `mfg operator` with Loader Operator. Two tiers now sit **below every literal one**:
  1.4 for the query with its abbreviations spelled out found whole in the title, 1.3 for every word met by itself or
  a synonym, in any order (`_term_groups`, a `jsonb` parameter). **A first design put the phrase at 1.9, above
  "all the typed words in any order", and was caught in review against the rule "what was typed outranks what we
  expanded it to" before it shipped** — and the first set of tests did not pin three of the rules until they were
  rebuilt. Seven mutations, each now failing exactly its own test.
- **Measured on 764 real queries** (the 726 plus 38 abbreviation probes): 758 identical, **6 lists changed, 4 at
  the top, every one an improvement** — `mfg technician` → Pharma Manufacturing Technician, `mfg operator` →
  Automotive Additive Manufacturing Operator, `hr manager` now finds Deputy Human Resources Manager, `logistics
  executive` puts Supply Chain Executive above Business Analytics Executive. No exact-title and no single-word query
  moved.
- **Verified.** `make check` 1,055 passed (1,033 + 22); `make evaluate` holds; `make check-role-aliases` passes;
  no web change and the generated client is byte-identical. **Live** against the running API: four simultaneous
  applies gave 201 and three 409s with one row; withdraw fired against rejected, hired and shortlisted gave no
  500 and a coherent final state each time — **honestly, the live race does not fail on the old code every time**
  (natural interleaving is luck), so the deterministic tests are the proof and the live pass is the smoke test.
  Throwaway candidates erased.
- **Left for later:** the district skill-gap view (BL-12.7, needs a minimum cell size and a ranking rather than a
  threshold); slug-uniqueness races; BL-12.15; the curated alias batch; BL-5.3; BL-12.11; BL-1.3.

### Sprint 46 — dependency triage, and the last race the audit had not reached (done 2026-10-04, uncommitted)

Owner decisions, as recommended: dependency triage plus the slug races (not the district view), and the two majors
that cannot work are **held with their reasons recorded** rather than left open as red PRs.

- **The cause was our config, not the packages.** `dependabot.yml` grouped every npm update (`patterns: ["*"]`), so one
  major that cannot work turned the whole weekly PR red — and two such PRs (13 and 2 days old) sat open while the safe
  bumps inside them waited. Probed in a throwaway worktree, merged with current `main`, through every gate: **as sent,
  `npm ci` fails** (`openapi-typescript` declares a TypeScript `^5.x` peer and the bump moves to 7); with TypeScript
  held, install is fine but `tsc` fails (vitest 5's `esbuild.jsx` option is gone), **lint crashes** (ESLint 10 throws
  inside `eslint-config-next`'s React plugin) and the build fails on the same `tsc` error; with **every major held, all
  gates pass**.
- **What was adopted:** the safe subset (react and react-dom 19.3.0, TanStack Query 5.104, next-intl 4.14.9,
  tailwind-merge 3.7, axe-core 4.13, testing-library, `@types/react` 19.3), **vitest 5 and jsdom 30** (371 tests pass,
  `tsc`, lint, build and the 684 KB budget clean, `/profile` still 678), and `@types/node` 20 → 24 to match CI's
  Node 24. **A first draft of the vitest config kept an explicit `oxc.jsx` setting with a comment claiming it would fail
  loudly if a default changed; removing it showed all 371 tests pass without it, so the claim was false and the setting
  was deleted** — the config now says why it has no JSX option.
- **What is held, and why (`dependabot.yml`, BL-13.6):** TypeScript 7 until `openapi-typescript` accepts it; ESLint 10 until
  `eslint-config-next`'s React plugin runs under it. Grouping is now minor and patch only, so a major arrives alone.
- **Not applied, and why:** the three GitHub Actions bumps cannot be exercised locally; each is its own PR, merged one at
  a time and judged by its CI run. **I cannot read PR status from here** (no `gh`), so that check is the owner's.
- **Observed, not acted on:** a full `npm audit` reports a high `braces` advisory reached only through
  `eslint-config-next` (lint toolchain, not shipped); CI audits `--omit=dev` and that reports 0. Newer npm also prints
  `allow-scripts` warnings for `fsevents` and `unrs-resolver`; nothing fails.
- **The slug races.** `unique_slug` and `_unique_tenant_slug` read the slugs taken, pick the first free one and insert
  later. Four tests reproduced it on the unfixed code as unhandled `UniqueViolationError`s on `ix_jobs_slug`,
  `ix_courses_slug` and `ix_tenants_slug` — **500s**, and the likeliest of the check-then-write races for one person to
  hit, because an employer double-tapping "Create vacancy" posts the same title and district milliseconds apart.
- **The fix is `api/core/slugs.py`'s `add_with_unique_slug`**: insert in a savepoint and choose again, so a second vacancy
  with the same title takes the next suffix (`x`, `x-2`…). It lives in `core/` because identity cannot import marketplace.
  A violation counts as a collision **only if the slug is now taken** — any other `IntegrityError` is raised as it was
  rather than retried five times into a misleading "try again". **Organisation creation passes
  `after_collision=_refuse_duplicate_organisation`**, so one person's double-tap is the 409 Sprint 26 intended rather than
  `x` and `x-2`; two *different* people with the same name both succeed with different slugs. This also means
  `_refuse_duplicate_organisation` — itself a check-then-write — is now covered where it mattered.
- **Verified.** `make check` 1,060 passed (1,055 + 5); `make evaluate` holds; the generated client is unchanged. Four
  mutations of the helper each fail a test — one escaped at first (the "only if the slug is taken" guard, which no test
  provoked) and a fifth test was written for it. **Live** against the running API with the demo employer and a
  throwaway candidate: four simultaneous "create vacancy" requests gave four 201s with four different slugs; three
  simultaneous "create organisation" requests by one person gave one 201 and two 409s with exactly one organisation.
  Everything created was erased and the database confirmed empty.
- **Left for later:** BL-13.6 (revisit the held majors); the district skill-gap view (needs a ranking, and is a demo until
  there are more than 42 candidates); BL-12.15; the curated alias batch; BL-5.3; BL-12.11; BL-1.3.

### Sprint 47 — an operator screen for role aliases (done 2026-10-04, uncommitted)

Owner decisions, as recommended: the table is the source of truth with the dict only seeding what is missing; **admin tier
only**; and the screen without the optional worklist.

- **The problem was structural, not a missing form.** `scripts/seed_skills.py` ran `DELETE FROM role_aliases` and rewrote
  it from the dict on every run, so only an engineer could add an alias, every batch needed a commit and a deploy, and
  anything added another way vanished at the next seed. That is why the curated batch — which needs somebody who knows what a
  ward attendant is called in Kanpur — had never started.
- **The model (ADR-054, migration 0046).** `role_aliases` gains `source` (`seed`|`operator`), `retired_at`, `created_at`.
  The seed (`sync_seed_aliases`) inserts what is missing, updates `seed` rows and removes seed rows the dict dropped, and
  **never touches an `operator` row, retired ones included**. An operator *retires* rather than deletes, handing the row to
  themselves, so a dict that still names the key cannot revive it. `role_alias_events` is the append-only audit record; it
  **names** the alias (key and target copied) instead of referencing it, because the seed may delete the row an event
  describes. Role search gained one filter, `retired_at IS NULL`.
- **Validity is the checker's rules from the same function** (`alias_problems`), not a copy: a target that names nothing, a
  disability-track target and a key that is a role's exact title are refusals (422; a taken term is 409); an ambiguous
  prefix is a warning. The target is stored as the corpus spells it. **`make check-role-aliases` now checks the table**,
  which is what an operator's edits live in.
- **API** under `/ops/role-aliases` (list, `check` as a dry run, add, `{id}/retire`, `history`), behind a new admin-only
  `OPS_ALIAS_EDIT`. **The screen** is a panel on `/admin`: the target is *picked from role search, never typed*, the dry run
  runs as they type so a bad alias is heard before the button is pressed, and the server's own sentence is shown on a
  refusal. A support-tier operator gets 403 and a sentence, not a broken panel.
- **Tested as a property, because the seed is the dangerous part.** An operator's row survives a re-seed whether or not
  the dict names it, a retired one is not revived, and replacing the sync with the old delete-and-rewrite fails five tests.
  Eight mutations of the service each fail a test; a ninth case — two operators adding one term at once — is a 201 and a 409
  on committed rows and the test fails without the `IntegrityError` handling (the Sprint 45 harness).
- **One of my test expectations was wrong, not the code:** a one-character term is refused by the *schema* first (FastAPI's
  own 422 body), so the service's own message is tested directly.
- **Verified.** `make check` 1,095 passed (1,060 + 35); web 385 (371 + 14) with `tsc`, `eslint`, build and the 684 KB
  budget clean; `make evaluate` holds; `alembic check` clean and 0046 round-trips; the real dev table synced as a no-op
  (114 rows, all seed). **Live** against the running API as the seeded operator, 16 of 16: the dry-run refusals, add, search
  finding the role *through the alias* at once, a duplicate 409, retire, search no longer finding it, history newest-first, a
  re-seed leaving the retired operator row alone. I deleted my own throwaway alias and its two audit rows from the dev
  database afterwards (an operator cannot, by design) and confirmed 114 aliases, none operator-owned, no events. **Browser**
  at 375px: no overflow, and by luck it showed the refusal — "ayah" is already a starter alias, so the live check said so and
  kept Add disabled.
- **Not built:** editing a target in place (retire, then add — deliberately, so the history says what happened); the
  preferred-role-title worklist (typed searches are not logged, ADR-023, and 42 candidates would show nothing); a read-only
  view for the support tier.
- **Left for later:** the alias batch itself — **coverage is unchanged at 43 of 3,417 until somebody uses the screen**;
  BL-13.6 (revisit TypeScript 7 and ESLint 10); the district skill-gap view; BL-5.3; BL-12.11; BL-1.3.

### Sprint 48 — what erasure deletes, the export shows (done 2026-10-04, uncommitted)

Owner decisions, as recommended: **a review whose author erases their account stays, author blanked**; notices **are** in the
export; and the privacy work plus the maintenance item (not the district view).

- **The scan.** Every foreign key into `users`, `candidate_profiles` and `tenants` is `CASCADE` or `SET NULL`: erasure cannot be
  blocked by a stray constraint and leaves no row behind. The gap was the other half — read against `export_account`, four things
  held about a person were erased and **never shown**: **job alerts** (Sprint 27), **ratings** (37), **sponsorship offers** (41)
  and the **notices** addressed to them. "We delete it but cannot show it" is the awkward half to be missing.
- **The export** now carries `job_alerts`, `sponsorship_offers`, `ratings_received`, `ratings_given` and `notices` (small helpers
  beside `export_account`; an empty account exports empty lists). **Nobody else is named**: a received rating shows the rating, the
  comment, the vacancy and the organisation that gave it, never `author_user_id`; an offer shows the organisation, vacancy and
  standard, never who made it; a rating the person *gave* describes the other party only by role ("a worker", "the
  organisation"), so an employer's export does not hand them a worker's name; a rating about an organisation is the
  organisation's, and goes only to its author. The `exportBody` line the Account page shows was updated in en/hi/ms.
- **The guard** (`tests/test_privacy_coverage.py`, ADR-055) walks the SQLAlchemy metadata for every table with a foreign key into a
  person, plus `notifications` **by name** (it has no foreign key — the row names a recipient and holds no address — so no schema
  walk finds it). Each must be in `EXPORTED` (mapped to a real key of the document) or `EXEMPT` with a written reason; the three
  exemptions are operators' audit trails. It asserts it **found** tables first, fails on a stale entry, and a second test feeds it
  a table that does not exist. **Honest limit: it sees foreign keys only**, so the next `notifications`-shaped table must be
  added to `NON_FK_PERSONAL` by whoever writes it.
- **The two halves are held to each other**: a test exports a candidate with one of everything, erases the account, and asserts every
  record the export showed is gone.
- **Mutation-checked, and every one fails its own test**: dropping each of the five keys, leaking an author id, naming who made an
  offer, widening received ratings to the organisation's, emptying ratings given, and un-listing a table from the guard. One
  mutation's pattern did not match after ruff reformatted the line and was re-run by hand.
- **Maintenance.** `@types/node` majors are ignored in `dependabot.yml` with the reason (it follows CI's Node 24, ADR-053), so the
  24→26 PR stops reopening. **The Python lock PR was probed in a throwaway worktree** merged with `main`: three bumps (fastapi
  0.141.1→0.142.2, pymongo 4.18.1→4.18.2, ruff 0.16.8→0.16.9), lint and format clean, `mypy` clean, **1,095 backend tests pass** —
  safe to merge. **My first probe installed without `--extra dev`** (the flag CI uses), so ruff and pytest were missing and every
  step failed with "No such file"; I read the log rather than the exit codes, found it, and re-ran correctly.
- **Verified.** `make check` 1,106 passed (1,095 + 11); web 385 with `tsc` and lint clean; `make evaluate` holds. **Live** against
  the running API with a throwaway candidate and organisation, 14 of 14: all five keys present, no employer id, address, author or
  `offered_by` anywhere in the text, the employer's own export showing the rating they wrote "about a worker" and not the
  candidate's phone or id, erasure leaving no record the export had shown. Everything erased and the database confirmed empty.
- **Not done:** a retention limit on sent notifications (they accumulate while the account lives, hold vacancy and organisation
  names and no address, and are erased with it); the district skill-gap view.
- **Left for later:** the alias batch itself; BL-13.6; BL-12.7; BL-5.3; BL-12.11; BL-1.3.

### Sprint 49 — matching you can trust at volume (done 2026-10-05, uncommitted)

Owner decisions, as recommended: **scope A–E** (harness, retrieval, district view, notification retention, authorization matrix);
**a separate `iism_scale` database**; **K as a setting, default 500**; **minimum cell size 5**.

- **The finding.** Every number this project quotes comes from 42 candidates and 151 vacancies, so the retrieval stage had never run
  against a catalogue larger than its own cap. `match_jobs` cut by `Job.id` and `_candidates_for_jobs` by the UUID's text, *before*
  ranking; the scorer then ordered an arbitrary 500. Measured against **exhaustive truth** on 50,042 candidates / 5,148 vacancies:
  **2.9 of 20** of a candidate's true top vacancies and **1.2 of 20** of an employer's true top candidates were returned (best-missed
  regret mean 9.6 / 3.0 points). The code's own comment had said the cap would bite once the catalogue grew. A pool of 47,109 sharers
  also **crashes past asyncpg's 32,767 bind parameters**, and the load-everything-into-Python path took 16 s.
- **The harness** (`make seed-scale`, `make benchmark`, `make drop-scale`). `iism_scale` is created from a copy of the dev database;
  synthetic rows are **deterministic** (ids and every draw are hashes of an index — two runs gave an identical checksum), skewed
  (`--skew`, default 3; the commonest standard held by 46,025 candidates), and **noisy on purpose**: evidence source, level floor and
  experience floor are drawn at random, because the first version (all `self_declared`, no level floors) showed perfect recall at
  K = 50 for a reason that had nothing to do with the bound being good. **Both scripts refuse any database not ending `_scale`**,
  and a test runs them against `iism`, `iism_test`, `iism_scale_backup` and `scale` to prove it.
- **The fix** (`matching/retrieval.py`, ADR-056). Keep the K highest **upper bounds** on the score: coverage and the mandatory count
  from the database, level / experience / evidence taken as full marks, the cap applied exactly as `score_match` applies it. It is
  a retrieval ranking and **never a score** — not returned, stored or shown. The employer side is one window query per vacancy
  (`row_number() ... <= K`); loads of held skills and profiles are chunked at 5,000; scarce skills count holders only for the standards
  tied with the last that can make the list.
- **Measured, before → after (K = 500).** Candidate overlap 2.9 → **20 / 20**; employer overlap 1.2 → **20 / 20**; employer shortlist
  p50/p95 921/1,148 → **462/569 ms**; scarce skills 495/470 → **119/108 ms**; `match_jobs` p95 185 → 186 ms (unchanged). K sweep:
  K = 150 gives 20/20 on both sides at **273 ms p95**; K = 50 gives 20 and 17.0; K = 20 gives 18.2 and 12.5. **`make evaluate` output
  is bit-identical** (diffed against `main`'s). **The default misses the 300 ms employer target I set; K = 150 meets it** — the owner's call,
  and the synthetic skew is steeper than the real corpus will be.
- **`EXPLAIN ANALYZE` found a second cost no test would**: the first window query let the planner build every candidate's held keys
  across the table (a scan of all 890,778 rows, ~350 ms). Driving the join *from the vacancy's standards* through
  `candidate_skills.skill_id`'s index took retrieval from ~300 ms to 18–96 ms.
- **A test caught an imprecise claim of mine**: I had written `bound >= score / 100`; the scorer *rounds* (`round(raw * 100)`), so
  `score / 100` can exceed the unrounded bound by up to 0.005. The claim, the docstring and the assertion now say what is true
  (`score - 0.5 <= 100 * bound`). A second test asserts the bound is **tight** when nothing else varies, because a bare "never below"
  passes an over-count (a candidate holding two rows of one concept was being counted twice, hidden by the mandatory cap).
- **District skill-gap view** (BL-12.7, ADR-057). `GET /ops/districts`, `GET /ops/districts/{id}/skill-gap` (`OPS_PROGRAMME_READ`) and
  a panel on `/admin`. Every standard an open vacancy in the district requires, **ranked by shortfall — no "scarce" threshold**.
  **A supply of one to four residents is never shown** (`MIN_CELL_SIZE = 5`, a constant — a privacy floor an env var can lower is not
  a floor); the shortfall beside it is computed from the hidden maximum (4) and flagged a minimum, and **rows are ranked on what is
  shown**, so the order leaks nothing the figures do not. Zero is shown (an absence describes nobody). The panel computes nothing.
  Live on the dev data: Pune 16 vacancies, 7 residents, "Employability Skills (60 Hours)" demand 4, supply 0. **Honest limit:
  `/ops/programmes/{name}/districts` still shows exact per-district counts, including cells under five** — the same class of disclosure,
  recorded and not changed.
- **Notification retention** (ADR-058). A worker cron (03:15 India time) deletes delivered email and **read** in-app notices after
  `NOTIFICATION_RETENTION_DAYS` (90, floor 7) and an **unread** notice after twice that; **a `pending` row is never deleted**. Nothing
  else reads old notifications (the alert and sponsorship caps count other tables). No index serves the in-app delete — a nightly scan.
- **Authorization matrix** (ADR-059, `tests/test_authorization_matrix.py`). Built from the OpenAPI schema, so a new route is covered the
  day it exists: **anonymous** gets 401 from every route not in `PUBLIC_ROUTES` (each with a reason; stale or 401-answering entries fail);
  **a stranger to an organisation** — a candidate with none, and the owner of a *different* one — gets the same 404, status and body,
  for a real slug as for none, on every `/org/{slug}/...` route; **the back office** is 404 byte-identical to an unrouted path for a
  non-operator, and 403 for a support operator exactly where `TIER_PERMISSIONS["support"]` lacks the route's permission — **read off the
  route** (`require_operator`'s dependency now carries `.permission`); **a user's token opens no `/partners` route**. Written against the
  current code it **found nothing wrong**; two entries of my first `PUBLIC_ROUTES` were corrected by running it. **It guards the doors,
  not whose row a permitted caller reaches** — that needs a real resource per route and stays with each module's tests.
- **Mutation-checked, and every one fails its own test**: retrieval (cap dropped from the bound, evidence headroom removed, ranking
  ignoring the bound on each side, no DISTINCT per requirement row, tie-break dropped, held loads not chunked, scarce contenders cut
  to `limit`), skill gap (floor inclusive, shortfall from the true supply, closed vacancies counted, supply not limited to the district,
  no per-vacancy de-dup, resident total not suppressed, zero hidden), retention (pending deleted, unread kept 1×, unread deleted
  regardless of age, task ignoring the setting, skipped kept), the matrix (a guard removed, 403 for 404, a non-operator told 403, the tier
  check removed) and both harness guards. **Three survivors, all mine, all fixed or explained**: two tests that were weaker than I thought
  (a mandatory cap masking a double count; one lucky row order passing a tie test) were strengthened and re-run; one mutant
  ("a non-member's 404 body differs") is **equivalent** — "no such organisation" and "not a member" share one branch, so changing its text
  changes both identically; the 403 mutant proves the status check bites.
- **A script bug that nearly cost the baseline**: my background benchmark script called `git stash`, and in a `nohup` environment `git`
  resolved to an x86 binary ("Bad CPU type"), so the "old code" run silently used the **new** code and printed 20/20. I noticed because
  the numbers were too good, and took the true baseline from a clean worktree of `main` with `PYTHONPATH` set (checked that `api` imported
  from the worktree).
- **Verified.** `make check` **1,162 passed** (1,106 + 56) with ruff, format and `mypy` clean; web **389** with `tsc` and lint clean;
  `npm run build && npm run budget` passes (`/admin` 662 KB of 684). **Live** against the running API on the real dev database:
  an operator reads `/ops/districts` and a district's gap (anonymous 401), the demo employer's overview and a demo candidate's matches
  render with no `bound` in any payload, and the panel renders in the browser in **English and Hindi** (no missing keys; "5 से कम …"
  note). The scale database is left in place (`make drop-scale` removes it); **the dev database was never touched**.
- **Not done:** `/ops/programmes/{name}/districts` adopting the small-count rule; the true (uncapped) pool size on the employer
  overview (`pool`/`ready`/`nearly` are counts over the K retrieved, as they always were); an index for the in-app retention delete.
- **Left for later:** the alias batch itself; BL-13.6; BL-5.3; BL-12.11; BL-1.3.

### Sprint 50 — scale the rest (done 2026-10-05, uncommitted)

Owner decisions: **keep K = 500**, and **"scale the rest"** as the theme.

- **The method.** Sprint 49's harness, extended with deterministic opt-in extras (`--skill-less`, `--enrolled`, `--applicants`,
  `--notifications`; the default dataset is byte-identical, so Sprint 49's numbers still compare) and benchmark sections for each path
  that tolerate old code, so **the same file measured `main` (from a clean worktree, `PYTHONPATH` set) and the branch**. A read-only audit
  of the code produced the list; every item below was then measured, not assumed.
- **Programme report (ADR-060).** It ran `match_jobs` once per enrolled candidate: **133 ms each, 22 minutes for 10,000**, and an
  `IN (every id)` that fails past 32,767. `matching/batch.py::profiles_with_serious_match` scores only the pairs whose retrieval bound can reach
  60 (`bound >= 0.595`), best first, in rounds, up to K — **the same answer as the loop**, which `tests/test_matching_batch.py` keeps as its
  oracle on three random marketplaces. 50 enrolled: 6.7 s → 0.15 s; 10,000: **17.6 s**. Getting there took three corrections found with
  `EXPLAIN ANALYZE`: the first pair query built 3.2 million pairs per 1,000 candidates (5.2 s, spilling to disk), so it was **anchored** on each
  vacancy's rarest mandatory standard (285 thousand pairs, 0.8 s; a test holds both routes to identical output); the planner then joined in the
  wrong order until the intermediate was forced with a **`MATERIALIZED` CTE**; and **JIT** was adding ~600 ms a chunk (37 s → 18 s with it off, now
  `DB_JIT=false`, tested through the engine).
- **Employer overview.** `job_pools` scored every sharer of every vacancy and loaded each as a full profile to read three integers. `ready` and
  `nearly` are *defined* by the mandatory-missing count the SQL already computes, so `retrieval.pool_counts` does it with one aggregate:
  **20 s → 2.5 s unloaded** for the heaviest harness employer (54 vacancies, 1.39 million sharing pairs), and the counts are now **true totals**
  (before: 27,000, because it counted the K retrieved). A test compares them with scoring every sharer, on three random worlds.
  `candidates_total` is an `EXISTS` per profile.
- **Embedding sweeps.** `LIMIT 100` with no `ORDER BY`: a row with no text keeps `embedding IS NULL` and was picked first on every tick, so
  once a batch's worth existed nothing behind them was ever embedded (profiles are created lazily, so skill-less ones are ordinary). Now ordered
  by `embedding_computed_at ASC NULLS FIRST`, the unembeddable row is **stamped** and goes to the back, the batch's skill ids are one query, and the
  batch is 250. Tests: 7 unembeddable rows ahead of one embeddable in a batch of 5; a row looked at long ago goes before one looked at recently.
- **Notification drain** (migration 0047). In-app rows are never moved off `pending`, so the `(status, created_at)` index walked all of them: **267-311 ms
  a tick at 500,000 → 71-120 ms** with a partial index on `(created_at) WHERE status='pending' AND channel='email'`. Plus `(job_id, status)` on
  applications. `alembic check` clean; down/up round trip run on the scale database.
- **Inbox.** A status change re-ran the whole inbox to return one row (3.5 s at 5,000 applicants); it now scores that one applicant (a spy test asserts
  it is given exactly one id). Profiles load column-only (`lazyload("*")`) on the inbox, the shortlist and `candidate_facts`; `score_profiles` is chunked
  (a 40,000-id test). **`tests/test_role_scoring.py`'s "six statements" bound became seven**, deliberately and with the reason in the test.
- **Programme-by-district** hides counts of one to four (`skill_gap.suppress`, "Unknown" included) and ranks on what is shown; the bars sum to *at most*
  the enrolled total and the panel says so. This closes ADR-057's recorded follow-up.
- **Alert sweep:** 10 vacancies per five minutes drained 120 an hour, so more than ~2,900 new vacancies a day never drained; now 30.
- **Measured under load, so read the ratios.** The machine ran at load average 6-12 (Chrome, a VM) and single numbers moved 2-4x, including untouched
  paths; old and new were **interleaved three times**: programme report 8.5/13.6/15.9 s → 0.24/0.31/0.24 s; overview 36/60/50 s → 5.9/7.9/5.6 s;
  inbox 8.0/15.8/11.0 s → 2.7/3.3/3.1 s. **Recall is unchanged at 20 of 20 on both sides; `make evaluate` is bit-identical.**
- **Mutation-checked, and every one fails its own test**: the batch (threshold off by one, retrieval limit ignored, no carry between rounds, strict `>`),
  the anchored route (anchor on any standard, no-mandatory vacancies dropped, anchored below the cap), pool counts (ready `<= 1`, nearly `== 2`, pool of the
  ready only, zero-share vacancy omitted, total counting empty profiles), the sweeps (no `ORDER BY`, not stamped, nulls last, newest first), the district rule
  (hidden count sent, ranked on the true count), the inbox (not column-only, whole-inbox reload, unchunked facts, whole-profile `candidate_facts`) and the JIT
  setting. **Survivors, all equivalent or fixed**: "anchor chosen as the most popular" (any anchor is correct; the choice is only for speed), and three tests of
  mine that were weaker than I thought (a statement count that `db.get` satisfied because the profile was already in the session; an ordering test passing by
  heap order; a status-change test that could not tell one applicant from thirty) were strengthened and re-run.
- **A measurement that fooled me.** The first "after" benchmark of the drain read 6-10 ms and the first interleaved comparison showed no change: the
  benchmark's own 200 pending email rows are *consumed* by the first run, so later runs measured an empty queue. The controlled before/after (267 → 81 ms,
  with the plan showing `ix_notifications_pending_email`) was taken on a freshly seeded database; re-seed before comparing the drain.
- **Verified.** `make check` **1,209 passed** (1,162 + 47) with ruff, format and `mypy` clean; web **390** with `tsc` and lint clean;
  `npm run build && npm run budget` passes (`/admin` 662 of 684 KB); `make evaluate` bit-identical; `alembic check` clean and 0047 down/up on the scale
  database. **Live** against the running API on the real dev database: the employer overview's pool/ready/nearly are **identical to the pre-sprint values**
  for all five Apollo Care vacancies, the demo candidate's matches are unchanged (8; 88/60/45/45), the programme report and its district view answer (the
  eight districts all read "fewer than 5"), and **the batch and the old loop agree on all 42 dev profiles (15 serious each)**. The dev programme's 20 enrolled
  candidates hold no standard, which is why `matched` is 0. **Migration 0047 was deliberately left unapplied to the dev database that sprint; it and 0048 were applied on 2026-10-06.**
  **One web test, `ApplyPanel.decided`, flaked in two of four full runs** while the machine's load average was 20-33 (Docker Desktop and Chrome, not this work);
  it passes alone and on a rerun, and nothing here touches it. The backend suite took 8.5 minutes under the same load, against 105 seconds when quiet.
- **Not done:** public `q` search was **not measured** and has no trigram index; the erasure notice loop (one ORM object per applicant); a `closes_at`
  index; `corpus_stats` stays uncached on purpose. The overview still joins one row per (vacancy, sharer) pair, so an employer with hundreds of
  vacancies will feel it. 10,000 enrolled is still 17.6 s as a request.
- **Left for later:** the alias batch itself; BL-13.6; BL-5.3; BL-12.11; BL-1.3. **Restart `make worker`** for the larger embedding batch and sweep size.

### Sprint 50.5 — show the work done on the homepage (done 2026-10-05, committed `1681de7`, merged in PR #29)

Owner decisions: show **job seekers, employers and training providers, applications and hires, and reach**; **always show the true count**, however small.

- **Why.** The band showed what the platform *holds* and nothing about people or activity, which is the wrong way round for a sales conversation. The owner asked for a small
  intermediate sprint; "always the true count" makes the *definitions* the work.
- **The figures (ADR-061)**, all in one `SELECT` of scalar subqueries (one statement; 17 ms on the dev database, 56 ms at 50,000 profiles; still uncached on purpose):
  **job seekers** = a profile with a declared standard (`marketplace.skilled_profile()`, now the one definition, also used by the employer console), leading because profiles are
  created by a visit; "signed up" (every profile) underneath; **employers** and **providers** by `tenant_type`, personal workspaces excluded, with "hiring now" and "with a published
  course" underneath; **applications** = every one made, withdrawn included; **hires** = `hired`/`completed` (a `no_show` is not a hire); **districts with an open vacancy** =
  distinct districts over `open_job()`, a count of places, so ADR-057's small-cell rule is not engaged. The old master-list figure is relabelled "states and districts in our location data".
- **Honesty.** `demo` is true for anything but production **and for any `*_scale` database**, and the band says "These figures come from a demonstration database, not from real use."
  On the dev database: 22 job seekers (42 signed up), 102 employers (97 hiring now), 60 providers, 18 applications, 1 hire, 21 districts. A true zero shows `0`.
- **Web.** Two rows, people first. The digit-grouping rule moved to `lib/format.ts` (two copies of it were how adjacent numbers ended up grouped differently). `StatsBand` lost its
  10-minute `staleTime`; applying, withdrawing and adding/removing a standard now invalidate the public counts (each test fails when the call is removed).
- **Tests, each failing without its rule.** Backend: a personal workspace is not an employer, an empty profile is signed up but not a job seeker, a withdrawn application still counts, a
  no-show is not a hire, a closed or draft vacancy makes nobody "hiring" and no district "covered", a draft course makes no provider "with a course", the `_scale` flag, the one-statement
  count. Web: `StatsBand` had **no test**; now both rows, the underneath lines only when different, a zero shown, Indian grouping, the demo note only when flagged, skeletons never zeros.
  Mutation-checked (ten backend predicates, seven band rules, two invalidations): every one fails its own test. **One survivor was my test being weak** (a closed vacancy had no district,
  so a "districts" figure counting it could not be seen) and was strengthened.
- **Verified.** All nine figures equal an **independent SQL count** on the dev database; `/en` and `/hi` rendered at 360x640 and at desktop (the Hindi hero button's bottom is at 492 of 640
  px, no horizontal overflow, the demo note visible); **`make check` 1,233 passed** (1,209 + 24) with ruff, format and `mypy` clean; web **402** tests, `tsc` and lint clean, `npm run build && npm run budget` passes. **Not done live:** applying as a demo candidate to watch
  the figure move, because that would leave a permanent `withdrawn` row in the dev data; the invalidation is covered by tests instead.
- **Not done:** caching (the owner-settled rule stands), per-district people figures, a "verified organisations" figure, merging `/marketplace/counts` into `/stats`, translating `ms`.

### Sprint 51: bulk upload of vacancies and courses (done 2026-10-05, ADR-063, migration 0048; merged in PR #29, 2026-10-06)

- **What exists:** `api/modules/marketplace/bulk.py` (the engine, ~1,100 lines), `bulk_routes.py` (template, check, apply, publish for both kinds under `/org/{slug}/jobs|courses/bulk/*`),
  `web/src/components/employer/BulkUpload.tsx` with a route each (`/employer/[org]/jobs/upload`, `/employer/[org]/courses/upload`) reached by an "Upload a spreadsheet" button beside
  "New vacancy"/"New course", and `scripts/fixtures/sample_vacancies.csv` / `sample_courses.csv` (real NOS codes and role titles from the dev corpus; a test pins their columns).
- **Rules that must not be broken:** bulk goes through `create_job`/`create_course` and never writes a row itself; check writes nothing and apply re-validates; `job_role` is exact
  title or alias only; mandatory defaults to no; explicitly listed standards win over a role's expansion; the cap counts every creation path and is the same in check and apply; the
  bulk router is included **before** `publishing_router`; only the two upload paths take the 2 MiB body.
- **Tests:** `tests/test_bulk_upload.py` (77), `BulkUpload.test.tsx` (12), a limits case in `constraints.test.ts`. Mutation-checked: fuzzy role matching, mandatory default, role
  importance, the 50-standard cap, the skip key widened across organisations, the verified cap, the cap window (both directions), the PwD warning, the body limit on every route and the
  route order each fail a test; so do six screen guards (acknowledge before apply, a confirmation before publish, a JSON-encoded body, the size check, the signed-out branch, the
  server's own words). **Run mutation checks with `PYTHONDONTWRITEBYTECODE=1`**: a stale `.pyc` from a mutated `api/main.py` made five tests 404 and made the earlier results meaningless.
- **Measured live on the scale database as the seeded demo employer and provider** (never the owner's number): the sample files check, apply, re-upload (all skipped, naming the
  matched reference), publish, and a mixed file with two bad rows created one and returned the two to fix as CSV. A 200-row check is 0.06 s; a 200-row apply is 2.4 s (vacancies) and
  2.6 s (courses). The rows were deleted afterwards. `iism_scale` is migrated to 0048; `iism_mig` was dropped; a `CREATE DATABASE ... TEMPLATE iism` attempt crashed the Postgres
  container once (it recovered, `iism` was intact), so a live pass used `iism_scale` instead.
- **Not built (stories 14.8-14.12):** update by `external_ref`, XLSX, partner/ATS push (needs a `ServiceAccount`-to-tenant binding), an upload history, async above 200 rows. Malay
  strings for the new screen are English, like the rest of that locale.

### Sprint 51 follow-up: the homepage grid (2026-10-06, committed `a2243ae`, merged in PR #29)

The owner reported the "Who is here" numbers misaligned and asked for three across. Both sections of `StatsBand` hold six tiles, and `lg:grid-cols-4` made each a row of four and a
row of two. Now **three columns from `sm` up, two on a phone** (6-digit Indian-grouped figures such as 2,38,370 do not fit three across at 360px), and the **"States and districts in
our location data" tile is gone** (with `stats.coverage` in en/hi/ms; the API still returns `states` and `districts`). `StatsBand.test.tsx` swaps the old coverage test for one that
asserts the tile is absent and each `<dl>` has six children, `sm:grid-cols-3` and no `grid-cols-4`. Measured in the browser at 1280px: 3 columns by 2 rows in both sections.

**Environment, 2026-10-06:** the API and web dev server had both stopped and the worker was a stale Oct 4 process; all three were restarted from a session (`make api`, `make worker`,
`make web`, logs in `/tmp/iism-logs/`) and `make migrate` applied 0047 and 0048. `/health/deep` reported Postgres, Redis and the worker up. The cause of the stop was not found.

### Sprint 52: journeys in a real browser (done 2026-10-08, ADR-062, migration 0049; merged in PR #30, `63ba8a0`)

- **What exists.** `web/e2e/` (six specs, `support/{test,identities}.ts`, `global-setup.ts`), `web/playwright.config.ts`, `scripts/seed_e2e.py`, `make seed-e2e` / `make e2e` / `make drop-e2e`, and a third CI
  job `e2e` (`.github/workflows/ci.yml`). The stack under test is the **production build** (`npm run build:e2e` into `.next-e2e`, so it never overwrites the `.next` a running `next dev` serves) with the
  real API on **:8100 / :3100** (never 8000/3000) against its own database **`iism_e2e`** and Redis db 1. `@playwright/test` is pinned exactly; axe was already a dependency and is injected from `node_modules`.
- **Rules that must not be broken.** `scripts/seed_e2e.py` **refuses any database not ending `_e2e`**: the importer rewrites the standards it owns, and on `iism` that would replace the real corpus with seven
  invented rows (checked: it refuses). Every page goes through `checkPage` (no console error, no failed request, no 4xx/5xx from our origins, **no `securitypolicyviolation`** because report-only never blocks,
  axe **with contrast ON in light and dark**, transitions frozen first because axe samples a colour mid-fade). **Findings change the product; they are never allow-listed.** `globalSetup` deletes leftover vacancies
  and courses each run, because `/matches` shows a top twenty and identical earlier vacancies crowd a new one off it (that was the "flaky" candidate test).
- **Journeys:** candidate (phone sign-up with consent first, "ward boy" -> General Duty Assistant via the alias table, nothing pre-ticked, matches with a named gap, apply, employer sees the contact, withdraw takes
  it back and the row stays), employer, provider (learner chooses to be contacted), operator (`grant_staff.py` is the only way in; refusal byte-identical to an unrouted path; a reason is required), Hindi at 360x640,
  bulk upload (drafts invisible, confirmed publish, re-upload creates nothing). **Deviation from the plan:** the bulk CSV is written per test with unique titles, not a committed fixture.
- **Five real defects it found, each fixed:** `--muted` 4.33:1 on the hero's tinted surface (now `#586980`); **every signed-out page load asked `/auth/me` with no token** and took a 401 plus a console error
  (`useMemberships` now answers 401 locally when no token is stored; unit test); skill-code labels dimmed by `opacity-70` to 3.97:1 / 4.17:1 (`GapPanel`); the homepage figures' sub-lines were `<p>` inside a `<dl>`,
  invalid HTML axe fails once a secondary figure exists (`StatsBand`, now `<dd>`; unit test); and **Sprint 51's upload screen did nothing when the same file was chosen twice** (the file input is cleared after reading).
- **Each check was proved able to fail** by breaking the product on purpose (a `console.error`, an image the CSP disallows, a 2:1 text colour): console, failed-request, CSP and contrast each fired, then reverted.
  **Ten consecutive full runs (two repeats each) were clean** after fixing two test-side flakes: asserting before the server had acted, and the accumulating database. **Not covered:** padding and spacing (a `Card` with no
  `CardBody` passes every one of these checks), visual regression, other browsers, real devices.
- **B, done:** `notifications.enqueue_many` (batched multi-row INSERTs; the erasure path uses it instead of one ORM object per applicant) and **migration 0049**, `ix_jobs_closing` partial index
  (`closes_at IS NOT NULL AND closed_at IS NULL`) for the hourly `close_expired_jobs` sweep, declared on the model so `alembic check` is clean (round-tripped up/down/up; `EXPLAIN` uses it). `tests/test_notification_bulk.py` (4).
- **C, settled by evidence, not by an install:** `eslint-plugin-react`'s latest (7.37.5, already installed) still peers ESLint `^9.7`, and `openapi-typescript` 7.13.0 still peers TypeScript `^5.x`; both holds stand
  (dated note in ADR-053 and `dependabot.yml`).
- **Open, and not fixed because the owner declined the prompt:** `npm audit --omit=dev --audit-level=high` reports **two high advisories in the production tree, `sharp` <0.35.5 and `source-map-js` <1.2.2**. They predate
  this sprint (the same two with this sprint's package files stashed) and will turn the existing `web` CI job red on any pull request. `npm audit fix --dry-run` shows four patch bumps in `package-lock.json` only.
- **Local gotchas.** After editing web code, **rebuild (`npm run build:e2e`) and kill any `next start -p 3100`**: Playwright reuses a running server locally and will test stale code. The Playwright browser cache is
  575 MB in `~/Library/Caches/ms-playwright`; the machine's disk was at 93%.

### Sprint 53: every page, an invariant, and the update half of bulk upload (done 2026-10-09, ADR-064, no migration; merged in PR #35, `6993241`)

Owner decisions: run `npm audit fix` first; widen the browser net first; bulk-upload update is the cut line (it was not cut).

- **Stage 0, done.** `npm audit fix` moved 28 lock entries (the `sharp` family 0.35.4 to 0.35.5 with libvips 1.3.3 to 1.3.4, and `source-map-js` 1.2.1 to 1.2.2; nothing added or removed): the production
  audit (`npm audit --omit=dev --audit-level=high`, what CI runs) now exits 0. A full `npm audit` still reports 5 high in the lint toolchain (`eslint-config-next`'s `braces`), known since ADR-053, not shipped.
  **Dependabot triage (tested, not merged; the owner merges and closes):** the newest `python` group (fastapi 0.142.2, pymongo 4.18.2, ruff 0.16.10, mypy 2.4.0) passes ruff, mypy and all 1,315 tests of that
  day; the newest `web` group (`react-dialog` 1.2.0, `react-progress` 1.1.17, `axe-core` 4.14.0, `jsdom` 30.1.2) passes `tsc`, lint, unit tests, the build and every browser test **but takes `/profile`
  from 678 to 680 KB of the 684 KB budget, leaving 4 KB**. Stale duplicates to close: `python-5113e460e3`, `web-0caa1ab034`, `web-d4d48f29cf`, one of `setup-node-6` / `setup-node-7`; `@types/node` 26
  stays closed (ADR-053). The Actions bumps (`checkout` 7, `setup-uv` 7, `setup-node`, `cache` 6, `upload-artifact` 6) can only be judged by CI, one at a time. *(Written 2026-10-09 when there was no
  `gh` token; every one of these was then merged and judged by CI, and the `e2e` duration is known: see "CI facts" below.)*
- **Stage 1, done: `web/e2e/sweep.spec.ts`** visits ~45 routes in `/en` and `/hi` (signed out; a seeker with something on every list; an employer; a provider; an operator; detail pages for a real vacancy,
  course and standard; a real 404; `/status` asserted absent in a production build) through the same `checkPage`: **81 tests, ~30 s with 3 workers**. It found **two defect classes**, fixed at their cause:
  inline links in running text told apart by colour alone (1.54:1; now underlined: `SignUpForm`, `SignInForm`, `signup/page`, `AccountPanel`, `Notices`) and two `/admin` `<select>`s with no accessible
  name (`aria-label`, unit tests). `checkPage` gained a **flush-border check** (a box with a border on all four sides whose text starts under 6px inside it; `allowConsole` for a deliberate 404). **Proved able
  to fail:** zeroing `CardBody`'s padding failed all six journeys, naming each box and its text; on the real app it finds nothing.
- **Stage 1b, done: a published listing keeps its standards (ADR-064).** `update_job` / `update_course` accepted `skills: []` on a **published** listing, which stayed live and unmatchable.
  `listings.refuse_emptying_a_published` (one shared helper) now 422s it before any field changes; a draft may still be saved with none. `tests/test_published_keeps_standards.py` (7); the two
  "cannot be edited down" tests fail without the guard.
- **Stage 2, done: bulk upload updates by reference.** `bulk/check` and `bulk/apply` take `existing=skip|update` (default `skip`; **a required argument inside `bulk.run`**, because a default there was a
  mutation that survived). Only an `external_ref` match may update (a title match stays a skip); it goes through `update_job` / `update_course`; **the file is the truth only for the columns it carries** (an
  absent column is left alone, a blank cell in a present column clears the field); an identical row is a skip ("unchanged"); status, slug and the daily cap are untouched; the check mirrors the live-listing
  guard. New row status `update`, response fields `updates`, `updating_live`, `updated`, event payload `updated`. UI: an opt-in checkbox, a re-check when it is toggled, an "Update" badge, a live-listing
  acknowledgement before the button enables, "Create N drafts and update M". 15 backend tests (8 rules mutation-checked, the route default included) and 5 component tests (3 UI guards mutation-checked).
  Measured on `iism_scale`: check 0.13 s, applying 200 updates 5.9 s, an unchanged re-upload 0.06 s (creation read 6.5 s the same session against 2.4 s in Sprint 51; the machine was busy, so both are upper bounds).
- **Browser suite is now 88 tests** (81 sweep + 7 journeys): the new journey is the provider's courses upload (template, role expansion, drafts, confirmed publish, re-upload, update by reference), and the
  bulk journey gained the update step. Each new check and rule above was proved by breaking the product on purpose; three consecutive full runs were clean (~54 s each).
- **Gotchas learned.** Do **not** run `prettier --write` on an existing file: this repo is not at Prettier's default width and it reformatted unrelated lines in `GapPanel.tsx` (reverted); only on files you created.
  `psql -c "a; b"` is one transaction, so an error in `b` rolls back `a` (a delete of 200 test rows silently did not happen). After editing web code, rebuild with `npm run build:e2e` and kill any
  `next start -p 3100` before a browser run. **Git credentials:** never put a token in the remote URL (it overrides the keychain, and a typo there once printed it in a tool output); store it with
  `read -s "T?Token: "` then `git credential-osxkeychain store` (zsh: the prompt goes inside the quotes, `read -p` is bash); a push that touches `.github/workflows/` needs the token's **`workflow`** scope;
  a fine-grained token needs Contents and Workflows read-write on `iism`.

### Sprint 54: pages that do not jump, and a policy that blocks (done 2026-10-12, ADR-065, no migration; merged in PR #38)

Owner decisions: the recommended sprint was SEO and share previews plus layout stability; **the owner took only the stability and CSP halves** ("let SEO, deployment and monetisation be taken up later").

- **What was measured first** (a throwaway Playwright script outside the repo; production build, 360x640, Slow 4G, 4x slower CPU, median of three): first and largest paint 650 to 750 ms on the homepage, jobs, a
  vacancy, skills and sign-in; 340 to 350 KB over the wire (484 KB in Hindi: the Devanagari face). **Speed is fine**, and the 680 of 684 KB "budget" is an *uncompressed* ceiling, so its 4 KB of headroom
  is not a real constraint. **Layout shift was the defect:** `/jobs` 0.205, `/skills` 0.167, both from the footer alone; the signed-in screens up to 0.645.
- **The fix is one rule, not per-list heights.** `globals.css`: `body:has([data-loading]) footer { visibility: hidden }`; every `Skeleton` carries `data-loading`. `visibility`, not `display`, so the footer
  keeps its box. Three components returned `null` while loading (`SeekerOnly`, `ProfileEditor`, `DeleteOrganisation`) and now return a `Skeleton`; `AccountPanel` reserves the consent line that arrives late;
  `CandidateDashboard`'s placeholder was 64 px for a ~400 px card (now `h-96`); `StatsBand` holds the room for the sub-line under its first three tiles (the existing Hindi 360x640 journey
  failed the new check at 0.111 until it did: the figures arrive late and a tile may grow a line); `JobBrowser`, `CourseBrowser` and `SkillBrowser` show a `ListSkeleton` and no "No jobs" count while pending.
- **The check.** `web/e2e/support/test.ts`: a `layout-shift` observer scoring the worst session window (shifts within 500 ms of input excluded), a 0.1 ceiling, the moved elements named in the failure;
  GET requests to the API are held 250 ms (so the loading phase is always visible, whatever the machine), and `checkPage` waits for the network to go idle first. **The first version passed the very
  pages that jump** (it looked before the list arrived): that is the lesson, recorded in ADR-065. `web/e2e/sweep.spec.ts` gained an "on a phone" group (the public routes, the three detail pages, the seeker's
  seven pages, an employer's and a provider's workspace) because on a 1280x720 window the footer is never in view while a list loads.
- **CSP enforced** (`web/next.config.ts`): `Content-Security-Policy` in a production build, report-only under `next dev`. Two sweep assertions: the response carries the enforcing header and no report-only
  twin, and an injected `<script src="https://...">` is blocked (`script-src-elem ... (enforce)`). `'unsafe-inline'` for scripts remains (ADR-062, Sprint 20).
- **Proved able to fail:** removing the footer rule failed 21 browser tests (50 shift reports); restoring the report-only header failed the CSP test; deleting `data-loading` from `Skeleton` failed 4 unit tests
  and changing the rule to `display: none` failed the guard test. Unit tests: `ui/skeleton.test.tsx` (the attribute, `ListSkeleton`, and the stylesheet rule pinned from both ends) and
  `ListBrowsers.test.tsx`. All 119 browser tests (three consecutive clean runs, ~2 min each) and 435 unit tests pass.
- **Gotchas learned (also in CLAUDE.md):** a `next start` left on :3100 is **reused by Playwright and serves the old build**, and the process is called `next-server`, so `pkill -f "next start"` matches
  nothing: kill by port. The first two measurement runs this sprint tested stale code for that reason. A running `next dev` can also break `next build`'s type-check (a stub `.next/dev/types/routes.d.ts`
  collides with `.next-e2e/types`): the owner's dev server was up on :3000 mid-sprint and `.next/dev/types` was moved aside (to the scratchpad) for the build; it regenerates on the next compile.
- **Deferred by the owner (2026-10-12): SEO, deployment, monetisation.** The SEO findings, kept for when it is picked up: no `robots.txt`, no sitemap, no `JobPosting` structured data, and **no per-page metadata
  at all** (one `generateMetadata` in the locale layout, so every vacancy, course and standard has the same title and description, and a link shared on WhatsApp previews as the site tagline). Plan sketched: unique
  title/description/canonical/`hreflang` for jobs, courses, roles and organisations; `JobPosting` JSON-LD on open vacancies only (the fields exist, including salary and `closes_at`), a closed one `noindex`; a sitemap
  of open vacancies and published courses split under 50,000 URLs; `noindex` and a `robots.txt` disallow for private routes; the 21,303 standards pages **not** in the sitemap until duplicate names
  (1,778 names shared by 4,838 standards) are measured; a `NEXT_PUBLIC_SITE_URL` setting that omits canonicals rather than emitting `localhost`; a share button (Web Share, else `wa.me`). Needs a live site for
  Google's Rich Results Test. **Deployment is the real gate to traffic**, and monetisation waits for traffic (ADR-047).

### Sprint 55: the code review's fixes (2026-10-12, no migration; merged in PRs #39 and #40)

Findings 1 to 4 of the `/code-review` of Sprints 51-54 (PR #39): 20 new backend tests; every new test fails against the old code (19 of the 20; the 20th is a guard).
- **A number that is not a number** (`bulk._int`, `_float`): `nan`, `inf`, `-inf` and `1e999` raised ValueError/OverflowError and turned the whole upload into a 500. pandas writes a missing number as `nan`.
  Now a row error naming the column; the rest of the file applies.
- **A refused update was still saved** (`publishing.update_job`, `course_publishing.update_course`, `bulk.run`): the updaters set fields on the persistent row, then resolved the place/standards, so a refusal
  left it dirty and the next commit in the loop (or `record()`) saved it. Root fix: resolve and validate first, then change. Safety net: a refused row is rolled back in the apply loop.
- **A lost race was a 500** (`bulk.run`): `db.rollback()` after an `IntegrityError` expired the `Tenant`, and the next `tenant.id` was a MissingGreenlet. `run` reads the id once. Tested with committed
  rows (`tests/test_bulk_apply_rollback.py`), because the suite's `db` fixture would roll back its own set-up.
- **Check and apply disagreed about gigs** (`_plan_job`, `_plans`, `_merge_updates`): a gig with a state and no district passed the check and failed at apply; and an update row whose file carries no place
  columns was refused even when the listing it changes has a district. The "no place at all" problem is now decided once the row's kind is known (a new gig needs it from the file, an update is checked on the
  merged payload with the same `resolve_location` question `update_job` asks).
- **The other six findings of the same review, fixed the same day** (1,365 backend tests, 436 web; each new backend test fails on the old code except two guards):
  1. *Stale district* (`_merge_updates`): a file that carries `state` but not `district` cleared nothing, leaving a new state over the old district (a contradiction that resolves to no district). The district now
     goes with the state it belonged to (compared normalised, so a respelling keeps it) and the review lists "district" among the changes. A gig losing its district that way is refused by the check.
  2. *Bulk update gated by the create permission* (`bulk_routes._create_or_update`): `existing=update` also needs `JOB_UPDATE` / `COURSE_UPDATE`, as a dependency (a guard in the handler is one that is eventually
     forgotten). Tested by removing the update permission from `owner`; today only admin and owner hold either, so behaviour is unchanged.
  3. *Superscript digit* (`_parse_tokens`): `isdigit()` is true for a superscript two and `int()` cannot read it (a 500); ASCII digits only.
  4. *Duplicate React keys* (`BulkUpload`): the server says each sentence once (`_once`) and the key includes the index.
  5. *`visit()` waited on `.animate-pulse`*: it waits on `[data-loading]`, the product's own contract.
  6. *The phone group copied the desktop lists*: `checkPublic`, `checkDetailPages` and `SEEKER_ROUTES` are shared.
  Also: the gig "no place" rule is one field (`gig_place_problem`), decided in `_plans` for *new* rows only.
- **Gotcha: `make gen-api` reads whatever is on :8000, and the dev API had not reloaded since Oct 6** (it served a schema without `existing` and the regenerated client **deleted 42 lines of Sprint 53's
  types**; reverted). Restart `make api` and `make worker` after pulling; or generate from a fresh app (`app.openapi()` to a file, then `openapi-typescript`) and diff before committing.

### CI facts (read with `gh` on 2026-10-12; the repo is private, so nothing here is visible without a token)

- **Three jobs, ~3.5 minutes wall clock** (they run in parallel): Web (lint, types, build) 59 s to 1m40s, API (audit, lint, types, tests) 3m22s to 3m29s, **E2E (real-browser journeys) 2m52s to 3m43s**.
  The "split the journeys if the e2e job passes ~8 minutes" plan is **not needed**; revisit it only if the job approaches that.
- **Dependabot is finished.** Every wanted bump was merged one at a time on 2026-10-09 and each run judged by CI (python group #28, web group #34, `upload-artifact` 6 #32, `cache` 6 #33, `checkout` 7 #3,
  `setup-uv` 7 #2, `setup-node` 7 #4); stale duplicates were closed and their branches deleted. The first merges produced several `cancelled` runs: that is the workflow's concurrency setting superseding
  an older run with a newer push, **not a failure**. Dependabot's bumps predate the e2e job, so it was left on `checkout@v4`, `setup-uv@v5`, `setup-node@v4` (Node 20 deprecation warnings) until PR #36
  moved them to v7. **Every workflow file is now on `checkout@v7`, `setup-uv@v7`, `setup-node@v7`, `cache@v6`, `upload-artifact@v6`.** A new job added to `ci.yml` must use those, or dependabot never sees it.
- **The one red run on `main`** (the PR #35 merge, 2026-10-09 07:28 UTC) was the API job's **"Audit dependencies" step**: `pymongo 4.18.1` had three CVEs fixed in 4.18.2. Not our code: **the audit is
  time-dependent, so an advisory published after the lock was written reddens the next push with no change on our side.** The python group (#28) took `pymongo` to 4.18.2. There is no nightly job by
  decision, so the policy is: when the audit goes red, bump the named package first, before anything else, and read the "Found N known vulnerabilities" table in `gh run view <id> --log-failed`.
- **`ubuntu-latest` migrates to Ubuntu 26 on 2026-10-19** (a run annotation says so). The first CI run after that date is the one to read carefully: Playwright's system dependencies and the pinned
  Postgres/Redis service images are what could differ.
- **Local gate on `main`, 2026-10-12** (after the merges, before PR #36 which touches only `ci.yml`): `make check` 1,337 passed with ruff and mypy clean (ruff 0.16.10); `npm ci` and the production audit 0
  vulnerabilities; `tsc`, `eslint` clean; 428 unit tests; build and budget fine (`/profile` 680 of 684 KB, the accepted 4 KB of headroom); `make e2e` 88 passed in 45 s.
- **How to look**: `~/bin/gh run list --repo hegdekattehnew/iism --branch main`, `gh run view <id>`, `gh run view <id> --log-failed`, `gh run watch <id> --exit-status`, `gh pr checks <n> --repo ...`.
  CI runs on pull requests and `main` only, so a branch needs a PR before it has a run. See §6 for the `gh` and git quirks on this Mac.

### Sprint 56: never locked out (done 2026-10-13, ADR-066, no migration, merged as PR #42)

Owner: "go, start Sprint 56". BL-14.1 and BL-14.2 of the roadmap.

- **Reading the code corrected the roadmap's premise.** Credentials *could* be linked (`/me/credentials/...` and a profile-page `CredentialsSection`, which only added the missing one), but linking **silently overwrote** a held
  credential (no notice, no session ended: a stolen session could swap the number and keep the account), nothing could remove one, there was no cooldown between two code requests (only a 5-per-15-minutes budget), and the
  sign-up form could not ask again at all. And an organisation's resend must **not** call `/auth/org/register` again (it re-queues a pending organisation of the same name and the duplicate-name refusal fails the person at verification).
- **Cooldown (BL-14.1).** `core/security.py` `enforce_otp_rate_limit`: `SET NX EX` (`otp_resend_cooldown_seconds`, 30; **0 in `tests/conftest.py`**, 4 in the e2e API so a journey can see it and wait it out), checked before and not spent
  against the budget. A 429 carries `Retry-After`; `OtpRequestResponse.resend_after_seconds` (inherited by the organisation response) feeds the forms. `useCountdown` is a deadline, not a tick counter. 10 tests (`tests/test_otp_cooldown.py`).
- **Credentials (BL-14.2).** `confirm_link` is add-only (409 "replace it instead", before the code is spent). `replace_credential` / `unlink_credential` in `identity/service.py` (`POST /me/credentials/{phone,email}/replace`,
  `DELETE /me/credentials/{phone,email}`): the new identifier is proved, never the old; the user row is locked (`SELECT ... FOR UPDATE`) before "is another **verified** way in left?"; every refresh token is revoked and a fresh pair is
  returned (`CredentialChangedOut`); a notice goes **inline, best effort, email only** to an address captured before the change (the outbox resolves the recipient at send time, which after a replacement is the new address).
  17 tests (`tests/test_credentials.py`) and a committed-row race test (`tests/test_credential_race.py`, fails with an `IntegrityError` without the lock). Mutation-checked: no revocation, add overwriting, no "another way in" check, the
  notice to the wrong address (a first version of that test passed anyway: it looked at the *last* notice), and the missing lock.
- **Screen.** `CredentialsSection` rewritten (add / change / remove, countdown, nudge for a phone-only person, a placeholder while loading, the new tokens stored after a change or remove) and mounted on `/account` as well as the profile
  (an organisation-only account has no profile page). Loaded lazily on the profile (`next/dynamic`): the section took `/profile` to 683 of 684 KB; lazily it is **681**. 10 component tests (3 mutation-checked: forgetting the new tokens after a
  change, after a removal, and offering removal when the other credential is unverified), `SignUpForm.resend.test.tsx` (4) and `SignInForm.test.tsx` (3). The test harness's `world.account` now carries phone, email and their verified times.
- **Browser (`web/e2e/credentials.spec.ts`, journey 8).** A code asked for again after the wait; add an email, change the phone (the other device's refresh token is refused, this page stays signed in), remove the email. **A first version
  of the journey passed for the wrong reason**: the row already showed the new number inside the "we sent a code to ..." sentence, so it asserted before the request had finished; it now waits for the form to be gone.
- **Gotcha.** `make gen-api` against the dev API gave a wrong client again before it was restarted; the client is generated from a fresh `app.openapi()` (the diff is only the new endpoints and `resend_after_seconds`).
- **Not done (and why):** an analytics event (a hand-written CHECK migration); an SMS notice (DLT); proof of the old identifier; operator-assisted recovery for someone who lost every credential (an identity-proofing policy).
  **Recycled phone numbers** are a risk this does not close, stated in the ADR.

### Sprint 57: a way to complain (done 2026-10-13, ADR-067, migration 0050, merged as PR #43)

Owner: "go, start Sprint 57". BL-14.3 of the roadmap.

- **What was there.** `/grievance` was static legal text that **promised** an acknowledgement within 24 hours and a resolution within 15 days and told people to write to an officer who does not exist yet
  (`GRIEVANCE_OFFICER` in `web/src/lib/legal.ts` still says "to be appointed"); `/contact` was a `PlaceholderPage`. No form, no table, no queue. **Appointing the officer is the owner's**; this is the engineering half.
- **Module.** `api/modules/grievances/` (models, schemas, service, routes with three routers, `tasks.py`), migration 0050 (the table, its CHECKs, two indexes, and `grievance_update` added by hand to the notification
  template CHECK with a frozen list). Wired in `api/main.py` (three routers), `api/worker.py` (daily purge cron, 22:00 UTC), the privacy export (`grievances_raised`, without the operator's note) and erasure.
- **Rules, each in one place.** `_may_send` (a stranger needs `reply_to`; a `data_request` is a 401 for a stranger). `submit`: honeypot (`website` filled -> a fake reference, nothing stored), then `_may_send`, then two
  `core.security.enforce_budget` calls (per `client_ip`, per account or reply address; `grievance_submissions_per_hour`, 5, **0 in `tests/conftest.py` and in the e2e API**), then the insert with the reference drawn again
  in a savepoint on a collision. **No relay**: only a signed-in sender is acknowledged, inline, at their verified email; a stranger's address is shown to the operator and never written to. `_overdue` reads the two
  deadlines from settings; a contact message is never overdue. `close` is final and acknowledges an open message; `_for_decision` takes the row lock. The log carries the reference and kind, never the body.
- **Operators.** `OPS_GRIEVANCE_READ` / `OPS_GRIEVANCE_HANDLE` in the support **and** admin tiers. The queue masks the account (`mask_phone`, `mask_email`) and shows the message and reply address as given.
- **Web.** `MessageForm` (one form behind `ContactForm` and `GrievanceForm`: kind chooser, counter, reply-to only when signed out, honeypot out of sight and the tab order, a 429 counts down from `Retry-After`, a signed-out
  data request is told to sign in with no form to fill), the signed-in sender's own list with status badges, `ops/GrievanceQueue` on `/admin`, `Notices` words `grievance_update`, `LegalPage` takes children (the
  form sits under the legal text), legal copy no longer says "write to the officer" (en/hi/ms). New namespaces `contactPage`, `messageForm`, `grievanceQueue` in all three message files.
- **Measured.** 34 backend tests (`tests/test_grievances.py`) mutation-checked: 10 service rules each fail a test when broken. **Two budget mutants and the retention-age mutant survived the first version** (the two
  budgets masked each other; the "recent" row was closed at the transaction's own `now()`); the tests were rewritten until each failed alone. One mutant is equivalent and documented (purging an open row: the CHECK keeps
  `resolved_at` null there). 12 + 10 + 1 web tests, a constraints guard that pins the form limits against the server's source, and **browser journey 10** (`web/e2e/grievance.spec.ts`): a stranger and a signed-in person each
  write in, the operator sees both with the account masked and the honeypot's message absent, acknowledges and resolves with a note, the sender sees "Resolved" and never the note.
- **The journey found a real defect.** The queue's default filter was "waiting" (status `open`), so an **acknowledged** message, still owed a resolution within 15 days, left the default view the moment the operator pressed
  the first button. The default is now everything, ordered by what is owed. Also: a second browser page in a journey needs `watch(page, E2E.API)` or `checkPage` refuses it.
- **Gotchas.** `make check` lint caught two 100-column lines in guard-test dictionaries. The first-load budget is unchanged (`/admin` 670, `/profile` 681 of 684). `web/openapi.json` is gitignored; regenerate the client from
  a fresh `app.openapi()` (`ENVIRONMENT=development .venv/bin/python -c "..."`, then `npx openapi-typescript`).
- **Not done (and why):** the dashboard's open and overdue counts (cut line), an SMS notice (DLT), a reply template, threading an operator's reply into the product. **Owner-side:** appoint the officer and fill
  `GRIEVANCE_OFFICER`; provide the mailbox the operator replies from; `make migrate` (0049 and 0050) on the dev database.

### Sprint 58: courses you can attend (done 2026-10-13, ADR-068, migration 0051, merged as PR #44)

Owner: "go, start Sprint 58". BL-14.5 and BL-14.6 of the roadmap.

- **What was there.** `courses_closing_gap` ranked by how much of a gap a course closes, then title. A course had no place, start date or seat count, so a faraway, started or full course was recommended like the one next
  door; four screens each hand-rolled the same list item with a title and hours.
- **Data.** Migration 0051 adds six nullable columns to `courses` (free-text place, the two resolved ids, `starts_on`, `seats` with a `>= 1` CHECK). Nothing backfilled. `course_publishing` resolves the place with
  `resolve_location` **before changing anything**; `CourseIn`/`CourseOut`/`CourseDetail` carry the fields, `started` is a `computed_field` from `core/clock.today_ist()` (a new one-function module), and `seats_left` is
  `marketplace.service.seats_left_for` over `interests.enrolled_counts` (chunked by 5,000, only `enrolled` counts, floored at zero). The detail route and the provider's own routes fill it.
- **Attendability.** `matching/attendance.py` is pure (`assess`, `rank_key`, `AttendContext`); `matching.attend_context(db, profile_id, budget)` builds the context from `candidate_facts`. `courses_closing_gap(...,
  attend=None)` keeps the old order; with it the key is `(not closes_mandatory, not attendable, reach rank, -mandatory, -closes, title)`. Passed by `match_detail`, `careers.career_ladder` and `application_gap`; **not**
  by the two employer-facing sponsorship callers. `budget_inr` (`0..10,000,000`) is a query parameter on `/me/matches/{slug}`, `/me/careers`, `/me/applications/{id}/gap`. `CourseSuggestionOut` gains place, start,
  seats left, `reach`, `started`, `full`, `within_budget`, `attendable`, `language`.
- **Bulk upload.** `COURSE_COLUMNS` += `state`, `district`, `starts_on` (`_day`, ISO only), `seats`; `_plan_course` warns on an unrecognised district and on an offline or hybrid course with no place; the places are
  resolved for courses too; the "new state clears the old district" rule is generalised from jobs; the template and `scripts/fixtures/sample_courses.csv` carry the columns. **Five existing expectations moved from `ok`
  to `warning`** (every offline course in an old fixture now names no place), and the courses-upload journey's CSV now carries a place.
- **Web.** `SuggestedCourses` (and `CourseBudgetControl`) replace the lists in `MatchBrowser`, `GapPanel`, `CareerLadder` and `SponsorPanel` (`forPerson={false}` there: no claim about nobody); `lib/course-budget.ts`
  keeps the budget in `localStorage` through `useSyncExternalStore` (guarded, works when storage refuses); editor fields, the course page (where, next intake, places) and the browse card. Dates are parsed and
  formatted in UTC so a start date is the same day everywhere. `matchesPage.closesGap` and `hours` became dead and were removed.
- **Seed and golden set.** `seed_marketplace.course_intake(slug)` gives each seeded course a place (four cities by position; online has none), a start offset **relative to the day the seed runs** and seats (two are
  full through a seeded enrolled learner). `GOLDEN_COURSE_PAIRS` gains `attendable:`, `not_attendable:`, `reach:` and `attendable_first` labels, evaluated by `make evaluate` (**all 34 pairs, 7 orderings and 25 course
  expectations hold**; breaking the attendable tier fails it) and **derived independently from the seed's own tables** in `tests/test_golden_set.py`.
- **Measured.** 32 pure and real-row tests (`tests/test_attendance.py`), 19 for the data (`tests/test_course_place.py`), 11 for bulk upload; mutation-checked: 11 service/ranking rules and 4 bulk rules each fail a
  test when broken (one mutant, `unknown` ranked last, is equivalent because elsewhere is never attendable). Web: 11 + 2 component tests, and journey 11 (`web/e2e/attend.spec.ts`): three courses teach the one standard a
  Bengaluru candidate lacks (their district, another district of the state, another state) and are listed in that order with place, start, fee and seats; a Rs 5,000 budget moves the dearer local one down and removes nothing.
- **Gotchas.** A first `sed` with `\n` in a replacement silently skipped the rest of a `&&` chain. `ruff format` re-wraps long tuples in the golden table, so comments there are re-wrapped by hand. A dev server on
  :3000 does not need stopping for `NEXT_DIST_DIR=.next-e2e npm run budget` (it reads the e2e build's stats).
- **Not done (and why):** a place filter on course browse, distance or travel time (district and state only), a waiting list, language in the ranking, the budget on the profile (deliberately a per-request parameter).

### Sprint 59: a marketplace you can trust (done 2026-10-13, ADR-069, migration 0052, merged as PR #45)

Owner: "go, start Sprint 59". BL-14.4 of the roadmap.

- **What was there.** The only moderation lever was the owner unpublishing their own listing. `status == "published"` is compared in ~34 places, so a takedown that sets `status="draft"` is excluded everywhere for free;
  only `publishing.set_published`, `course_publishing.set_published` (and so `bulk.publish_many`) and `reopen_job` can bring a listing back.
- **Data (migration 0052).** `listing_reports` (once per reporter per listing, `target_id` **no FK**, `reporter_id` CASCADE, a fixed reason list, `detail <= 1000`, `open|dismissed|actioned` with a `handled_at` CHECK);
  `taken_down_at`/`takedown_reason` on `jobs` and `courses` (set together, a CHECK each); three closed sets widened by hand with frozen lists: `CLOSE_REASONS` += `taken_down`, four analytics events, two templates
  (`listing_removed`, `listing_restored`, email to the organisation). Test databases are built by running the migrations, so 0052 is exercised on every run; the downgrade was run on `iism_e2e`.
- **Takedown (marketplace).** `marketplace/takedown.py`: `take_down` (row lock, 409 if already down, draft + stamp, close the vacancy with `taken_down` if open and tell its live applicants through
  `_tell_live_applicants`, email the organisation the reason) and `restore` (clears the stamp and **only the takedown's own closure**, leaves a draft); `refuse_while_taken_down` is called by the three writers.
  `JobCloseIn` still cannot claim `taken_down`.
- **Moderation (leaf).** `api/modules/moderation/`: `submit_report` (published only, 404 for a draft; 409 for a member of the organisation; a savepoint insert so the unique constraint arbitrates; `enforce_budget`,
  `REPORT_SUBMISSIONS_PER_DAY` 10, **0 in `tests/conftest.py`**), `queue` (grouped by listing, most reporters then oldest, reporters masked, `view=open|taken_down`), `dismiss`, `takedown` (closes the reports and
  removes the listing in one transaction) and `restore`, each recording an event after the commit; `purge_expired` (closed past `REPORT_RETENTION_DAYS`, **and orphans by `NOT EXISTS`**; cron 22:30 UTC),
  `export_for_user` (`listing_reports_made`) and `erase_for_user`. Permissions `OPS_REPORT_READ` and `OPS_REPORT_HANDLE` in both tiers, `OPS_LISTING_TAKEDOWN` admin only.
- **Web.** `ReportListing` (a disclosure, not the dialog; signed out it says to sign in) on the job and course pages; `ReportQueue` on `/admin` (a support operator is not offered the takedown; the form says the
  reason is emailed to the organisation); a "Removed" badge and banner in both workspaces with publish and reopen hidden and edit kept; `JobRef.removed` (a computed field, `taken_down_at` excluded) makes
  `ApplicationList` show "Removed by our team" with no link. `world.staffTier` was added to the test harness.
- **Measured.** 37 backend tests (`tests/test_takedown.py`, `tests/test_listing_reports.py`, helpers in `tests/moderation_support.py`); 13 mutants each fail a test (the three publish guards, the closure, a restore that
  clears any closure, a listing that stays published, self-report, both tier mistakes, the retention age, purging an open report, the queue order and an unmasked reporter). Web: 5 mutants killed; 24 new
  component tests. Journey 12 (`web/e2e/moderation.spec.ts`): reporter, support operator, admin, waiting applicant and owner on five pages, every one through `checkPage`.
- **Gotchas.** `db.rollback()` in a test rolls back the suite's whole outer transaction, set-up included (see the new convention). Two selects on `/admin` were both labelled "Show"; the report queue's is "Listings"
  (a second select with the same label made Playwright's `getByLabel` ambiguous). Editing a source file mid-`make check` makes the subprocess import tests fail: wait for it.
- **Not done (and why):** an appeals queue, telling the reporter the outcome, notifying learners who registered interest in a removed course, and taking a listing down from its public page. **Owner-side:** `make
  migrate` (0052) on the dev database, then restart `make api` and `make worker` (the new cron and routes).

### Sprint 60: hiring that finishes (done 2026-10-13, ADR-070, migration 0053, **uncommitted** on `sprint-60`)

Owner: "plan and start Sprint 60". BL-14.7, BL-14.8 and BL-14.9 of the roadmap.

- **What was there.** `Application.message` is the *candidate's* covering note. `set_status` is the one writer of a status. `_applicant()` (the rule that contact and the covering note vanish on withdrawal) sat in a route
  module. The outbox keeps no free text that may hold a phone number. `GET /me/notifications` returned the newest 50, read ones included, from a function called `unread_for`. `bulk.errors_csv` echoed uploaded cells.
- **Data (0053).** `applications.status_message` (CHECK <= 500) and `status_message_at`, `employer_notes` (CHECK <= 2000) and `employer_notes_at`; analytics `applicants_exported` and template
  `application_status_message` widened by hand with frozen lists.
- **Message.** `StatusIn.message` (stripped, <= 500); `set_status(message=...)`: replace when given, clear when `changed` and none given, keep otherwise; the payload gets `has_message`, never the words; template
  chosen by whether there is one. `ApplicationOut` gains `status_message` and `status_message_at`, never notes (`tests/test_status_messages.py` walks every `/me/*` response model for `notes`/`employer_notes`).
- **Notes and CSV.** `PUT .../notes` (`NotesIn`, blank clears; kept on withdrawal; deleted with the application; in `privacy.export` as `employer_notes` and `employer_message`). `applications/serialisers.py`:
  `applicant_out` (moved from the route) and `applicants_csv` (columns `reference, name, phone, email, status, score, coverage_percent, missing_mandatory, applied_on, candidate_note, your_message_to_them,
  your_private_note`); `export_applicants` records the event; `core.text.csv_safe` is applied to every cell and to `bulk.errors_csv`.
- **Notifications.** `list_for(limit, before, before_id)` with a `(created_at, id)` tuple cursor, `unread_count`, `mark_read` (idempotent, `coalesce`), the routes `GET /me/notifications?limit&before&before_id`,
  `GET /me/notifications/unread-count`, `POST /me/notifications/{id}/read` (404 for another person's).
- **Web.** `EmployerInbox` (a draft message per applicant sent with the status button pressed, "You told them", `ApplicantNotes`, "Download as spreadsheet" through the new `lib/download.ts`); `ApplicationList`
  shows "A message from {organisation}"; `lib/notice-text.ts` (the one switch that words a notice) used by `Notices` and the new `NotificationsPage`; `lib/unread-count.ts` (the header's one `useQuery`) kept apart
  from `lib/notifications.ts` (infinite query and mutations); the header's `UpdatesLink`; `/notifications` in the sweep. `world.staffTier` already existed in the harness.
- **Measured.** 50 backend tests (`tests/test_status_messages.py`, `test_applicant_export.py`, `test_notifications_page.py`); 11 mutants each fail a test and one is equivalent (an extra `notes=` kwarg Pydantic
  ignores; the structural test guards it). Web: 25 new component tests and a hook test; 5 mutants killed. Journey 13 (`web/e2e/hiring.spec.ts`): an employer messages and annotates one applicant, downloads the
  spreadsheet (a withdrawn applicant blank, `=HYPERLINK` neutralised), and the candidate reads the message, sees "Updates 1 unread", reads it on `/notifications` and finds the note only in their export.
- **The browser run found three things.** An `aria-label` on the Updates link failed label-in-name (WCAG 2.5.3); an unread panel above the application list shifted it by 0.110 on a phone (moved below); and the
  header's import graph took `/profile` over its budget by a kilobyte (the count hook was split from the page's hooks; headroom is now 1 KB). The page's own signed-out test also caught an infinite query that
  fired for a signed-out visitor.
- **Gotchas.** A mutation harness that backs files up by `basename` collides when two files share one (`notifications/service.py` and `privacy/service.py`): it overwrote a file with another; the harness now
  restores each file from a copy of its own contents (`/tmp/mutrun.py`, in the transcript). zsh does not word-split an unquoted `$FILES`; use a python loop.
- **Not done (and why):** a thread, notes visible to the candidate, a bulk status change, an email digest, a count for the employer. **Owner-side:** `make migrate` (0053) on the dev database, then restart
  `make api` and `make worker`.

### Sprint 61: a pilot with an agency (done 2026-10-14, ADR-071, migration 0054, merged as PR #50)

Owner: "plan and start Sprint 61". BL-14.10, the last story of the roadmap.

- **What was there.** `scripts/bulk_enrol_candidates.py` (Sprint 33) was the only way to enrol an agency's file: an engineer with database credentials, any eight digits as a "phone", `int()` that raised on a spreadsheet's `nan`, a name that could exceed what the profile editor allows, a number repeated in one file unnoticed, every row in one transaction, and the consent it stamped vouched for by nobody.
- **Engine.** `api/modules/operations/enrolment.py`, a sibling of `marketplace/bulk.py` reusing its file reading: `parse_file` was split into a kind-free `parse_records(text, columns=, required=, max_rows=)` (it calls it; `tests/test_bulk_upload.py`, 129 tests, is the guard) and `int_cell` exports the whole-number rule. `run(db, text, programme=, apply=, attested=, actor=, file_name=)`; `_decide` is the one rule per row for the check and the apply; outcomes `new | tag | already | error`.
- **Data (0054).** `enrolment_batches` (programme, file name, `actor_user_id` SET NULL, `attested_notice_version`, `attested_at`, four counts) and `enrolment_batch_members` (profile id PK -> `candidate_profiles` CASCADE, batch, outcome `created|tagged`); analytics event `enrolment_applied` widened by hand with a frozen list. **The join table is on the operations side because a column on the profile would need `marketplace` to import `operations`.** `identity.provision_candidate` is now exported from `identity/__init__`.
- **Routes.** `/ops/enrolment/{template,check,apply,batches}`; `OPS_ENROL` is in `OPERATOR_PERMISSIONS` and the admin tier only; `_BULK_UPLOAD_PATH` in `core/middleware.py` carries the 2 MB allowance for `check` and `apply` (a test fails without the path). `apply` without `attest=true` is a 422 before anything is read.
- **Privacy.** `enrolment_batches` is excused in `tests/test_privacy_coverage.py` (an operator's audit trail); `enrolment_batch_members` is exported as `agency_enrolment` (programme, when, `account_created_for_you`, notice version attested, never the operator).
- **Web.** `EnrolmentUpload.tsx` (+ `lib/enrolment.ts`) mounted last on `/admin`: programme (with the known ones suggested), file, check, a rows list (problems first, 100 shown, masked phones, first names), the failed-rows download, the attestation, enrol, and the recent batches below. Absent for a support operator. Messages in en, hi (ms is English, as the other back-office panels). `/admin` first-load 680 of 684 KB.
- **Measured.** `tests/test_enrolment_upload.py` (26) and `tests/test_bulk_enrolment.py` (9, the script's original six ported and three added); 19 engine breakages each fail a test, 7 of 8 screen breakages do (the unguarded one is clearing the file input, which jsdom cannot model). A 1,000-row check takes 0.08 s and an apply 4.2 s (about 4 ms a row), so the cap stays at 1,000. Journey 14 (`web/e2e/enrolment.spec.ts`): an admin checks a file (nothing written, no number whole), attests, enrols, re-runs it (creates nobody), the enrolled person signs in by code and finds the profile and the export line, and a support operator never sees the panel; `/admin` is swept with a batch in its list.
- **Gotchas.** The Dependabot bump to Playwright 1.64 needs its own Chromium build: `npx playwright install chromium` (99 MB) before `make e2e` (CI does it itself). `web/AGENTS.md` is rewritten by Next's tooling on install and build; do not commit that change. `mask_email` keeps the local part's length (`op********@example.org`).
- **Not done (and why):** an agency login, a consent receipt from the person, an SMS to say they were enrolled (no SMS yet), a programme table (the name stays free text), undoing a batch, upload history beyond the latest 50. **Consent is asserted, not verified**, and the page says so. **Owner-side:** `make migrate` (0054) on the dev database after it merges, then restart `make api` and `make worker`.

### Sprint 62: M1 of the mobile app, foundations (done 2026-10-14, ADR-072, no migration; first half merged as PR #51, completion on `mobile-bootstrap`)

Owner: asked whether to branch and rebaseline to ship on both stores; chose a **native rewrite (Expo / React Native)**, candidate-only for v1, deployment and mobile launch together; then "start M1". The owner first **declined the toolchain download**, so M1 was written and only partly verified (said plainly in the ADR, the README and `CLAUDE.md`); later **allowed it**, and the second half below compiled and tested the whole app.

- **Answer to the branch question.** No fork, no rebaseline, no long-lived branch: `mobile/` beside `web/` and `api/`, short `mobile-N` branches merged to `main`, a `mobile-vX.Y.Z` tag per store release.
- **Verified (first half, before the install).** `AppVersionMiddleware` (30 tests; 5 breakages each fail one); `api/core/contract.py` (27 tests including the real API against the committed snapshot; 10 rules, 10 breakages each fail one); `make gen-api-mobile` reproduces the web's schema with a zero-line diff; the messages, colours, privacy-notice version, the declared packages and "what the app calls = the contract surface" are held by `tests/test_mobile_foundations.py` (12 tests); `mobile/src/core` passed strict `tsc` and 39 tests under the web's toolchain.
- **Completed (second half, after the owner allowed the install).** Expo SDK 57 (React Native 0.86.3, React 19.2.3, TypeScript 6): `create-expo-app` skeleton, `npx expo install` for the SDK-matched set, `package.json` and `package-lock.json` committed. **The whole app compiled with one type error** (`/auth/me` has no documented error body, so its failure branch narrows to `never`; fixed the way the web's `useOperatorDashboard` does). `eslint` clean (and proved able to fail). Metro bundles Android (3 MB Hermes) and iOS (2.8 MB). **53 Jest tests** under `jest-expo`: the 39 core tests unchanged, `src/test/sign-in.test.tsx` (9: the number gate, the code request, the cooldown, verify, consent sent only when ticked, 428 stores nothing, a wrong code, Retry-After, Hindi) and `src/test/home.test.tsx` (5: signed out asks the API nothing, a job seeker, an organisation account is told to use the website, both held, the language switch). `.github/workflows/ci.yml` gained a `mobile` job; `make mobile-check` runs the same.
- **Not verified, and no automated check stands in for it.** A run on an emulator or phone; **Hermes' `Intl` for Hindi plurals and dates** (the install has `hermesc`, the compiler, but no VM to run a script); TalkBack and VoiceOver; low-end performance.
- **Setup surprises (all in `mobile/README.md`).** SDK 57's optional peers disagree (`react-native-worklets`), so `mobile/.npmrc` sets `legacy-peer-deps=true`; `expo-doctor` passes, npm's strict resolver does not. `@react-native/jest-preset` must equal `react-native`'s version (`expo install` picked 0.87.1 for RN 0.86.3 and Jest failed to find `react-native/setup-env`). `use-intl` is ESM-only (`transformIgnorePatterns`). RNTL 14 is async and needs `test-renderer`. No `babel.config.js`. A test under `app/` would be a route. `../../app` resolves to `app.json`. A `jest.mock` factory runs before the test file's own `const`s. TanStack Query's GC timer keeps Jest alive (`gcTime: Infinity` in the harness).
- **Audit, open.** `npm audit --omit=dev` reports 24 advisories (14 high, 10 moderate), every high one in Metro / the Expo CLI / their dependencies (build tooling), plus one moderate that ships (`decode-uri-component` via `expo-router`). Fix is the next SDK; CI fails on `critical` only.
- **Deviation from the plan.** NativeWind was left out of M1 (a plain token hook and `StyleSheet`): its build configuration is the part most likely to be wrong unrun, and the tokens are identical either way.
- **Gotchas.** `mobile/` core tests must not use jest- or vitest-only mocking (they use hand-rolled fakes and globals) so they run under both. `Response` refuses a body on a 204: a fake network must build `new Response(null, ...)`. `/auth/logout` and `/auth/logout-all` are terminal-401 paths, so a test of the refresh must use another route (`GET /me/profile`). `use-intl` Hindi plurals on Hermes are unchecked.
- **Open before any launch:** real SMS (DLT, BL-12.9), a store-reviewer login (BL-15.8), deployment, the Apple and Google accounts and the real bundle id (`in.iism.app` is a placeholder), push (BL-15.6).

### Sprint 73: the hiring side's design pass (done 2026-10-17, ADR-083, no migration; branch `workspace-pass`, uncommitted)

Owner: "Plan and close the next sprint" after Sprint 72. **One question asked and answered**: which direction; the owner chose the employer and provider workspace pass (the recommended option) over the real embedding model, encrypting the sensitive columns, and candidate depth.

- **Read the premises first.** Three research agents (read-only) found: the funnel already scales to its first step; **UI-26 was mis-stated** (nothing in the API generates a description; bulk upload stores NULL for a blank cell; the generic text is 129 job and 129 course literals in `scripts/seed_sector_expansion.py`); `OrganisationReview` showed verify/revoke to the support tier. The recorded budget headroom was stale: **`npm run budget` reads `.next`, not `.next-e2e`**; use `NEXT_DIST_DIR=.next-e2e` after `npm run build:e2e`.
- **`/admin`** (`web/src/components/ops/`): `admin-sections.ts` (one list of ids), `AdminNav.tsx` (sticky row of anchors, wraps from `sm`), `CollapsiblePanel.tsx` (a `<details>`, mounts on first open, opens on `#id`), `AdminPanels.tsx` (the four `next/dynamic` panels), `OperatorDashboard.tsx` (same shape while loading; scarce skills behind a fixed-height row). Daily queues stay open; the order is now overview, verification, grievances, reports, then the reference panels.
- **Rows**: `web/src/components/RowActions.tsx`; `EmployerWorkspace.tsx` and `ProviderWorkspace.tsx` use it. Status badges in journeys are matched `exact: true`.
- **Charts**: a pool legend line (`employerWorkspace.dashboard.poolLegend`), the funnel's count in `font-semibold`.
- **Descriptions**: `is_template_description` + `_forget_description_translation` in the expansion seed; `bulk._description_notes` (a note for the file, never a warning per row); `descriptionHint` in `JobEditor` and `CourseEditor`.
- **Support tier**: `OrganisationReview` gates verify/revoke on `staff_tier === "admin"` (`ops.verifyAdminOnly`).
- **Small targets**: the verification queue's organisation link and the grievance and report filters are 44 px.
- **Ledger**: `scripts/build_ui_review.py` FIXED gains UI-14, 15, 16, 26 (UI-26 as "the finding was mis-stated"); `docs/design/screens/measurements.sprint73.json` and four `sprint73.*.jpg` pictures; `tests/test_ui_review.py` has the Sprint 73 test.
- **e2e**: a new `admin-nav.spec.ts` (a folded panel costs no request until opened; the nav and a pasted address open one; support is offered no enrolment), `grantStaff` in `e2e/support/identities.ts`, the sweep opens folded panels before `checkPage` and visits `/admin` on a phone, `enrolment.spec.ts` clicks the summary first.
- **Measured** (`/tmp/capture73.sh` style: production build, a second API on :8100 against the demo DB, `web/scripts/capture-review.mjs`; baseline is the repo's `measurements.json`): `/admin` 40.2 to 27.9 screens (phone), 31.2 to 24.8 (desktop), small targets 181 to 0 and 236 to 0; employer-home 52 to 0, provider-home 69 to 0; `/admin` first-load 698,039 to 686,248 B.
- **Mutation checks**: 26 (`/tmp/iism-mut/run73.py`, not committed); two first passed for the wrong reason (a guard test that already failed; a count that included the function's own definition).
- **Gotchas**: a layout shift can come from the *page above* a late element; a sticky nav under the sticky header needs `top-16`; the shell is zsh (an unquoted `$var` is not split); `python3` here cannot read a non-ASCII script file, use `.venv/bin/python`; the benchmark/capture scripts bake `NEXT_PUBLIC_API_BASE_URL` at build time, so a build for :8100 cannot be served against :8000.
- **Open and the owner's**: refusing to publish with no description (a new 422 on a released operation); UI-25's type scale (moves the phone's tokens); `make seed` to refresh the demonstration descriptions; a native reader for the Hindi nav, "More", legend and hints; counsel on the DPDP slice (Sprint 72); brand and artwork, the five-person check, delivery, the release list. **Not done and not claimed**: user research, a device, the two long queues becoming short.

### Sprint 72: a DPDP readiness slice (done 2026-10-17, ADR-082, migration 0056; merged as PR #63)

Owner: "Plan the next sprint" after Sprint 71. **One question asked and answered**: which direction; the owner chose the DPDP slice (the recommended option) over the employer/provider workspace pass, the real embedding model, and candidate depth. The substantive obligations are enforceable from **13 May 2027**.

- **The survey** (read-only, code and docs) found most mechanics built and five gaps: a **wrong notice**, withdrawal = deletion, no re-consent when the notice changes, an unchecked 18+ promise, no breach procedure. Out of scope on purpose: encryption of date of birth, salary and notes (its own sprint and a key decision), a nominee record, dormant-account erasure, the named grievance officer, a lawyer's review.
- **Withdrawal** (`api/modules/identity/consent.py`; `privacy/` routes `GET`/`POST /me/account/consent`, `POST .../consent/withdraw`). The stamp is committed first, then `applications.withdraw_all_live` and `interests.withdraw_all_live` take back what is live. Effects at one point each: `marketplace.paused_profile()` (retrieval's `candidate_pair_facts` and `skilled_profile()`), `identity.require_not_paused` (apply, register), `analytics._paused`, the push sweep. The retrieval filter is an **uncorrelated `IN` over `ix_users_consent_withdrawn`** (a partial index, in `MANUALLY_MANAGED_INDEXES`).
- **Re-consent**: `UserOut.consent_current` / `consent_withdrawn` (computed, additive); `ConsentBanner` (web, **fixed to the window**, "Not now" per session), the Me tab's `Notice` and `ConsentCard` (phone). **The version was bumped to `2026-10-17`** (api config, `web/src/lib/legal.ts`, `mobile/src/core/sign-in.ts`; e2e now imports the web's).
- **Notice**: rewritten in en, hi, ms; `tests/test_notice_covers_inventory.py` (COVERED / EXCUSED per column). `docs/release/privacy-and-data-safety.md` has a Consent section; `docs/release/incident-response.md` is new and tested.
- **Age**: `MINIMUM_AGE = 18`, `years_between`, a validator on `CandidateProfileUpdateFull.date_of_birth`; the consent sentence now says "I am 18 or over".
- **Found and fixed**: `ensure_profile` raced (two first requests, one 500 with no CORS header, shown as "Could not load your matches"); `tests/test_concurrency_audit.py::TestFirstVisit` widens the gap through `_profile_of`. A test that commits rows (`matches_viewed`) must delete them: erasure only anonymises an event, and `test_matching` counts them globally.
- **Benchmark** (`make benchmark`-style run on `iism_scale`, interleaved with a clean worktree of `main`; the scale DB had to be migrated 0048 to 0056 first): see ADR-082. A baseline worktree is removed afterwards (`git worktree remove --force`).
- **Mutation checks**: 35 (`/tmp/iism-mut/run72.py`, not committed); the survivors were a decorative `FOR UPDATE` (removed) and a runbook test that let `## Containment` pass for `## Contain` (tightened).
- **Gotchas**: `make e2e` needs the ports free (kill 3100 and 8100 by port) and rebuilds; a layout shift can be caused by something *above* a late element, so log the `layout-shift` sources with a `PerformanceObserver` before guessing; the shell is zsh, so an unquoted `$pair` is not split; `python3` here cannot read a non-ASCII script file with no encoding line, use `.venv/bin/python`.
- **Open and the owner's**: **counsel on pause-vs-erase, the 18+ position, the breach timings and the whole notice**; the appointed grievance officer; a native reader for the Hindi (the notice, the consent card); a market reviewer for the role aliases; brand and artwork; the five-person check; delivery (real OTP); the release list. **Not done and not claimed**: certification, encryption at rest, nominee, dormant-account erasure, a device.

### Sprint 71: role search you can trust (done 2026-10-16, ADR-081, no migration; merged as PR #62)

Owner: "Plan and close the next sprint" after Sprint 70. **One question asked and answered**: which of four directions; the owner chose *role search you can trust* (BL-12.12 coverage) over the employer and operator screens, the phone's Me and profile, and a DPDP audit.

- **The finding that framed it.** 41 of 3,417 roles had an alias (114 rows), nobody had measured how often a person's word reached a sensible role, and the alias module's claim that "waiter" and "mason" had no general pack was wrong (*Food and Beverage Service Assistant*, *Brick Mason*).
- **The measurement.** `tests/fixtures/role_titles.json` (146 titles: 118 English, 12 romanised Hindi, 16 Devanagari; 4 `none_ok`; 41 `hold`), labels chosen by meaning from a listing of the corpus (an exact name or an `accept_like` pattern), widened once after the first baseline and before any alias, and said so in the file. `scripts/evaluate_role_search.py` (`make evaluate-roles`, needs the national import; refuses a database with under 1,000 roles; hold-out per-title lines hidden without `--show-hold`). `tests/test_role_titles.py` (15) holds the fixture's shape and tests `judge` and `summarise` without a corpus.
- **The batch.** `ROLE_ALIASES` 114 to 307 forms onto 88 roles in sector groups; the header says it is engineering's unreviewed draft. `make check-role-aliases` failed three forms that equalled an exact role title aliased elsewhere and one that made "cab" ambiguous; they are out. Left out on purpose: helper, mechanic, machine operator, nurse, loader, packer, bouncer, anganwadi worker, housemaid, maid, accountant, turner, lathe operator.
- **The numbers** (top-1 / top-3 over titles with an answer): all 65.5 / 66.9 to 81.7 / 83.1; tuning 76.5 / 77.5 to 99.0 / 100; **hold-out 37.5 / 40.0 before and after**; English 70.2 to 83.3; romanised Hindi 50.0 to 66.7; Devanagari 43.8 to 81.2; `none_ok` 3 of 4 not led astray, before and after. The hold-out was seen once, in a run that printed its titles; nothing was fitted to it and the printing is off by default now.
- **No ranking change.** After the batch the tuning misses were two missing aliases (added) and "accountant" (a corpus gap; a whole-word rule risks the Sprint 43 and 45 invariants for one word).
- **The reviewer's copy.** `scripts/build_role_alias_review.py` writes `docs/IISM-Role-Aliases-for-Review.xlsx` from the dict alone (summary sheet says UNREVIEWED; one row per form; empty keep / change / retire and note columns); `tests/test_role_alias_review.py` fails when it is stale. Decisions are applied on `/admin`, never by editing the file.
- **Verification.** `make check` (ruff, format, mypy, 1,860 backend tests, 19 new), `make check-contract` (51), `make evaluate` (34 pairs, 7 orderings, 25 course expectations hold), 17 mutants (all killed; the three alias ones only after syncing the table).
- **Gotchas found.** `make check-role-aliases` reads the `role_aliases` table, so a change to the dict is invisible to it until `sync_seed_aliases(db, ROLE_ALIASES)` runs (`scripts/seed_skills.py` does it; so does a one-off call). The dev database was synced with the batch.
- **Open and the owner's**: **a market reviewer for the batch** (the workbook is theirs); more Hindi and Hinglish forms from a native speaker (the hold-out says what an unseen word gets: under half reach a right role); the corpus has no general accountant, housemaid or waiter-like roles for some jobs; unchanged: brand and artwork, the usability check BL-16.4, delivery, DPDP by 13 May 2027, the release list. **Stated limits**: the title set is the engineer's idea of how people speak, not usage (logging real searches would breach ADR-023); no device; no Hindi keyboard tried.

### Sprint 70: a candidate's first minute (done 2026-10-16, ADR-080, no migration; merged as PR #61)

Owner: "Plan and close the next sprint" after Sprint 69. **One question asked and answered**: how much of the homepage's proof content leaves it; the owner chose *move only the framework band* (the live people figures and the browse counts, both asked for earlier, stay).

- **The shared rule.** `matchSummary` (`web/src/lib/match-summary.ts`, `mobile/src/core/match-summary.ts`) over `tests/fixtures/match_summary_cases.json` (12 cases; a Python test in `tests/test_first_minute.py` fails if either side stops reading it). It reuses `presentRequirements`, so duplicates count once, a standard held under any code is held and generic entries are not counted. **A mutant on the fixture survived once in Sprint 69 (the stronger duplicate first); the same trap was avoided here by a case for it.**
- **Backend.** `match_jobs_with_total` in `api/modules/matching/service.py`; `MatchPage.total`; the route returns it. `match_jobs` keeps its signature (golden set, alert sweep). `tests/test_first_minute.py`: a page of 2 over 3 matches says 3, and equals the dashboard's `match_count`.
- **Web.** `Hero` (chips from `lib/example-jobs.ts`, links under the chooser), `stats-shared.tsx` (`useCorpusStats`, `StatGrid`), `StatsBand` (people only) and `FrameworkBand` (About), `Audiences` deleted with its message namespace, `HowItWorks` compact, `MatchBrowser` (sentence, one action, `<details>`, five at a time from the best fifty), `MatchesStrip`. Journeys updated (`candidate`, `attend`, `hindi-phone`: one `dl`, chips inside 360 px and 44 px tall).
- **Phone.** `MatchSentence` and `GapDetails` in `src/ui/match.tsx`, `Button expanded`, `src/core/home.ts` (`hasNews`, `NEWS_DAYS = 14`), `src/ui/SignedInHome.tsx`, `app/(tabs)/index.tsx`.
- **Verification.** All suites, `make mobile-check` (bundle 3,496,401 of 3,800,000), the first-load budget (`/matches` 666 KB), 30 mutants via `/tmp`-style scripts (not committed), the review's capture scripts on a production build and the phone through its browser build (`capture-app.mjs` timed out partway through its tour after the screens needed; the signed-in home and matches were captured).
- **Gotchas found.** A mocked test that answers every route with one shape crashes the new home (`items[0]` of a profile): give each route its own shape. `toHaveAccessibilityState` is not a matcher here: use `toBeExpanded`/`toBeCollapsed`. A script that edits a file, asserts, and is followed by `;` runs its next steps after a failed assertion: chain with `&&` or check the exit code (it installed an unchanged copy of the backlog once, harmlessly).
- **Open and the owner's**: unchanged (brand and artwork UI-03/18/20/23/24/27, the usability check BL-16.4, delivery, DPDP by 13 May 2027, role aliases, the release list). **New**: a native reader for the Hindi copy (hero, how it works, the sentences, the home) before launch. **Stated limits**: expert judgement, no device, the sentence omits generic standards the score counts, no apply on the phone home, homepage 6.0 not 5. **Backlog v1.31**: BL-16.2 done.

### Sprint 69: scannable jobs (done 2026-10-16, ADR-079, no migration; merged as PR #60)

Owner: "Plan and close the next sprint" after Sprint 68; the plan was the review's recommended first build (UI-04 to 11, 17), approved as written. Two owner decisions were left at their defaults and say so: **monthly pay wording** ("about ₹18,300-25,000 a month", the yearly beneath on the vacancy) and **NSQF leaves the job cards** (it stays on the vacancy and the standards pages).

- **Pay.** `payLine` (`web/src/lib/pay.ts`, `mobile/src/core/pay.ts`) turns the annual figure into a month for the four salaried types, to the nearest ₹100, one end alone is "from", a maximum alone says nothing, a gig keeps its posted figure, a figure that rounds to ₹0 a month stays annual. **Both are run over `tests/fixtures/pay_cases.json`**; `presentRequirements` likewise over `requirements_cases.json`. `tests/test_scannable_listing.py` fails when either side stops reading its file.
- **Cards.** `web/src/components/JobCard.tsx` and `mobile/src/ui/JobCard.tsx` (jobs list and search, both); text helpers are `web/src/lib/job-text.ts` (not in the client component: a server page calls them) and `lib/count.ts` (`formatCount` split out of `format.ts` for the same reason).
- **Lists.** `JobBrowser`/`CourseBrowser` are `useInfiniteQuery` (24, `total`, "Show more (n left)", a retry that keeps the rows). `GET /jobs/states` (public, additive, declared before `/{slug}`) is the state filter. `web/src/lib/paged-counts.test.ts` is the source guard.
- **Vacancy page.** Pay (monthly, yearly beneath), a trust box, the apply bar (`data-testid="apply-bar"`; `empty:hidden` so an account that cannot apply gets none), standards through `presentRequirements`, the slug line removed (the course page lost it too). The phone: `Screen footer`, `ApplyPanel compact` and `useApplyVisible`.
- **Floors.** `type-floor.test.ts` (12 px, 35 literals replaced, `--text-2xs` 12 px); `buttonVariants` sm/md/icon at 44; header, language select, context switcher and footer links at 44; `smallTargets()` in `web/e2e/support/test.ts` fails the sweep for a header or footer control under 44 px.
- **Operator.** `unverified_organisations`/`unverified_certifications` return `(rows, total)` with `offset`; routes return `OrganisationQueue`/`CertificationQueue`; the web queue is infinite and says "Showing n of N". The dashboard tile and the queue share the predicate (a test says one number).
- **Verification.** Backend, web and phone suites, `make mobile-check` (bundle 3,488,767 of 3,800,000), the full browser suite (the new sticky-bar test first failed because it expected the bar visible *through the footer*: the page was right, the test was wrong), first-load budget (`/admin` 682 of 684), 37 mutants, the review's capture script on a production build for the before/after table, and the real pages read as pictures.
- **Gotchas found.** A `"use client"` file's exports cannot be called by a server component; `Date.now()` in a render fails the app's `react-hooks/purity` lint (read once in state); a sticky-bottom bar rests where its container ends, so a browser test must scroll within the content; `ruff format` on only the files you touched.
- **Open and the owner's**: unchanged (brand and artwork, release list, delivery, DPDP by 13 May 2027, role aliases, the five-person usability check BL-16.4). **Stated limits**: expert judgement, no device, paging past 200 tested with a constructed catalogue, no posted date, the match screen keeps its apply buttons in the page, a course page has no trust strip. **Backlog v1.30**: BL-16.1 done.

### Sprint 68: a whole-product UI review (done 2026-10-15; no migration, no ADR; merged as PR #59)

Owner: asked what in the backlog needed priority and for research if none did; the research (DPDP Rules phase three on **13 May 2027**, real OTP delivery as the gate to a first sign-in because both the SMS and the email providers are console-only, a WhatsApp channel as the faster alternative to DLT, a "never pay to apply" notice, competitors' voice and WhatsApp entry) is summarised in the conversation; shown four Sprint 68 options, the owner **stopped that planning and asked for UI**, then chose **a whole-product design review**.

- **Evidence.** `web/scripts/capture-review.mjs` signs in as seeded demonstration people (candidate `+919000000006`, the Apollo recruiter, an NSDC provider admin, the Apollo operator) on a **production build** (`npm run build:e2e`, second API on :8100 against the demo database) and takes 52 pictures (375x812 light, plus dark, Hindi and desktop for chosen pages), capped at 2,400 px and measured: page height in screens, tap targets under 44 px, text under 12 px, images, SVGs. `capture-app.mjs` does ten phone screens through the Expo web build. **Two runs gave identical numbers on all 52** once it waited for the network to rest.
- **Findings.** `scripts/build_ui_review.py` holds the 29 as data and builds `docs/design/ui-review.md` and the workbook with `scripts/xlsx_min.py` (the ADR register's writer, extracted); `tests/test_ui_review.py` (5 tests) keeps them honest.
- **Fix made.** `mobile/app/match/[slug].tsx` showed the course-budget field and "No course on the platform covers this gap yet" on a match with nothing missing (Sprint 67's defect, seen in the capture); now shown only when something is missing, with a test that fails without it.
- **Backlog v1.29**: Epic B16 (BL-16.0 done; BL-16.1 scannable jobs, BL-16.2 a candidate's first minute, BL-16.3 brand and icons (owner), BL-16.4 a five-person usability check).
- **Open and the owner's**: brand identity and launcher art; monthly pay and plain words on seeker screens; whether to run the usability check; and everything from the release, delivery, DPDP and role-alias lists. **`docs/design/review/` is a superseded first-run set of the captures (14 MB, not committed); delete it** (the real set is `docs/design/screens/`).
- **Not verified.** Anything with real users, a real device, TalkBack, or real data.

### Sprint 67: M6 of the mobile app, candidate parity (done 2026-10-15, ADR-078, no migration, no endpoint; branch `mobile-6`, uncommitted)

Owner: "plan the new sprint as per your recommendations" after being offered four themes; the recommended one was parity. Decisions stated as defaults and not questioned: **dates as a month and a year with no picker package**, **date of birth and gender stay web-only**, **the budget is remembered on the device and cleared at sign-out**.

- **History sections.** `core/profile-sections.ts` is the table (fields, limits, defaults, the rules that span fields: end not before start, expiry not before issue), `ui/SectionForm.tsx` the one form, `app/profile/[section].tsx` the one screen (list, add, edit, remove with a question, the server's own sentence on a refusal, 401 to `SessionExpired`). The path segment is checked against the table. `useAddEntry`/`useUpdateEntry`/`useRemoveEntry` put the answer in the profile cache and refresh matches, every open match and careers.
- **An edit sends the whole entry.** The server reads an absent field as "clear it": `nsqf_level` (not shown on the phone) travels back, no `skill_slug` is ever sent (so the link is left alone), and an unchanged month and year send back the **exact** date the entry had.
- **Guard.** `tests/test_mobile_section_limits.py` reads the field literals and compares each with `schemas.*In.model_json_schema()`: lengths (and that a required text field is `min_length=1`), required, the year range, the four enumerations, the defaults, and that the routed collections are the edited ones. The web's `constraints.test.ts` for the phone.
- **Preferences** (`core/profile.ts`): salary range (whole rupees, top not below bottom), notice period, work type, relocation, alerts; a separate form beside the basics (its Save has a distinct spoken name, because two "Save" buttons on one screen are ambiguous to a reader).
- **Why not me, careers, budget.** `/gap/[id]` from a **rejected** application only; `/careers` with the role search, a guessed starting role flagged as a guess, each step's basis, what it would take, courses and entry route; `ui/BudgetField.tsx` on the match, the gap and careers. The budget store is `core/course-budget.ts` (storage injected), wired in `runtime.ts`, restored at launch, cleared by `forgetPersistedCache`.
- **Keys.** `meKeys.match(slug, budget)`, `meKeys.matchesOf(slug)`, `gap`, `careers`; the budget is **last** so a prefix reaches every variant. A mutant that put it third survived until the prefix was tested by name.
- **Contract.** Five operations added to `surface.txt` (`make snapshot-contract`); the 46 old entries are byte-identical (checked by loading both snapshots).
- **Housekeeping.** ADR-019, 032, 033 and 037 now say what superseded them; `scripts/build_adr_register.py` (stdlib only, committed) rebuilds `docs/adr/IISM-ADR-Register.xlsx`; `tests/test_adr_register.py` fails when the register misses an ADR or the four headers regress.
- **Verified.** `make check` (1,818), `make mobile-check` (600, bundle 3,480,098 of 3,800,000 bytes), `make check-contract` (51), 27 mutation checks, and the real screens in a browser (375x812, second API on :8101) as `+919000000006`, English and Hindi: sections list with plural counts, an add and a remove of a throwaway role, an edit form with dates, why-not-me (the one rejected application was **set by a direct update and restored to `applied`**; the golden candidates were not signed in as), `?budget_inr=3000` on the wire and the "Over your budget" labels, career paths, and `iism.course-budget` gone from storage after sign-out.
- **Not verified.** A device, TalkBack and VoiceOver, Hermes, the new screens at 200% font, a Hindi layout on a real phone.
- **Gotchas.** A Jest test that renders one screen twice leaves overlapping `act` scopes that fail the tests after it. A killed mutation run can leave a mutated file behind: **check `git diff` after killing one** (this sprint's left `me-keys.ts` mutated, caught by its own test).

### Sprint 66: M5 of the mobile app, store readiness (done 2026-10-15, ADR-077, no migration; branch `mobile-5`, uncommitted)

Owner: "plan and close the next sprint". Decisions asked and answered: **build everything buildable without accounts** and **update the four patch-drifted Expo packages** (`npx expo install --fix`; exactly four moved, `expo-doctor` went 20/21 to 21/21).

- **Release configuration fails closed.** `core/release.ts` (`configProblems`, pure) is consulted by `config.ts` (`CONFIG_PROBLEMS`, `release: !__DEV__`) and the root layout renders `screens/Misconfigured.tsx` instead of the router when a release build has no HTTPS origin or a local one; a source guard holds the chain (the first mutation run showed nothing tested the layout). `STORE_URL` is per platform (`EXPO_PUBLIC_STORE_URL_ANDROID/_IOS`).
- **`eas.json` and `app.json`.** `preview` (APK, staging origins) and `production` (app bundle, auto-increment, remote version source), origins and store links in per-profile `env`, `submit.production` placeholders; `app.json` has the one Android permission (`POST_NOTIFICATIONS`) plus blocked dev-merged ones, `ios.config.usesNonExemptEncryption: false`, the `expo-splash-screen` plugin and `faceIDPermission: false` on secure-store. **Verified by `expo prebuild --no-install` into a scratch copy**: the release manifest holds `INTERNET`, `POST_NOTIFICATIONS`, `VIBRATE`; cleartext only in the debug manifest; ATS is not relaxed. Each dependency ships its own iOS privacy manifest, so no app-level `privacyManifests` was written (check Xcode's Privacy Report on the first archive). **No `development` profile**: it needs `expo-dev-client`, a download nobody asked for.
- **`scripts/check_release_config.py`** (`make check-release`, `PROFILE=production` is the gate; stdlib only, run in the `mobile` CI job for `preview`). Defects fail every profile; **open owner decisions fail `production` only**. **It found that the icons, adaptive icons and splash are the Expo template's** (by SHA-256) and says so. 13 open items today.
- **Size ceiling** (`mobile/budget.json`, `scripts/check_mobile_budget.py`): Android Hermes bundle 3,427,300 bytes (ceiling 3.8 MB), assets 512,654 (650 KB); iOS bundle 3.2 MB. No launch time (needs a device).
- **Accessibility** (`mobile/ACCESSIBILITY.md`, `src/test/a11y.test.tsx`, guards in `tests/test_mobile_foundations.py`): chips from 40 to 48 dp, the sign-in privacy link given a 48 dp target, text capped at `MAX_FONT_SCALE = 2`, `Notice` one focusable item, the checkbox tick hidden from the reader. Everything a screen reader or a real screen must confirm is a checklist for a person with a phone.
- **`docs/release/`**: `store-listing.md` (English and Hindi, limits and forbidden claims tested), `privacy-and-data-safety.md` (one row per export section, Apple labels and Play Data Safety draft, tested against `test_privacy_coverage`'s `EXPORTED`), `review-notes.md` (no secrets), `release-runbook.md` (the owner's decisions, the reviewer-login switch-on/off and code rotation, contract re-record at each store release, closed test, rollback, go/no-go).
- **Verified.** `make check` (1,798), `make mobile-check` (499 plus the budget), iOS bundle, `expo-doctor` 21/21, `make check-contract` (46, unchanged). **27 mutation checks, all killed**: five survived the first run (two real test gaps: no test of a placeholder origin or store link, and the layout guard matched a log line instead of the render; three were badly written mutants). The release web export was run in a browser: a build with no origins shows the misconfigured screen (console: `api-missing, web-missing`), one with HTTPS origins shows the app.
- **Found by running, and fixed or recorded.** A local `expo export` reused Metro's transform cache and kept the old `EXPO_PUBLIC_*` values (a configured build still said `api-missing`): **`--clear`** (runbook). `expo-splash-screen` was in SDK 57's bundled modules but not installed: the template shipped a splash image and nothing to show it.
- **Not done, not claimed.** An EAS build, a submission, a run on a device or emulator, TalkBack/VoiceOver, 200% font on a real screen, Hermes `Intl` for Hindi, low-end timing, real push. The privacy answers and the listing are **drafts for the owner and a lawyer** against each console's current form.
- **Open (all the owner's).** See "Next sprint" in §0. `origin/mobile-3` may still exist remotely (delete it).

### Sprint 65: M4 of the mobile app, updates, push, links, account and reviewers (done 2026-10-15, ADR-075 and ADR-076, migration 0055, merged as PR #55)

Owner: "how many sprints are left for the mobile code? plan and close the next sprint". **Two are left** (M4 and M5); M5 is blocked on the owner, not on code. Owner decisions asked and answered: **reviewer login = named phones with a fixed code behind an explicit production switch; push = everything except real delivery.**

- **Backend.** `device_tokens` (+ `POST /me/devices`, `POST /me/devices/unregister`); `notifications.pushed_at` and the worker's `_sweep_push` (fixed words from `templates.PUSH_TEXT`, nothing from the payload, a dead token deleted, a retry up to `MAX_ATTEMPTS`, 24-hour window, batch 500); `api/adapters/push` (port, console provider that refuses production); export lists phones **without the token**; erasure takes them. Reviewer login: `REVIEWER_LOGIN_ENABLED`/`REVIEWER_PHONES`/`REVIEWER_CODE` with startup validation, a branch in `request_otp`, the demonstration-account refusal at verification, `scripts/create_reviewer.py`.
- **Mobile.** Core: `links` (the one table of what a link may open), `notices` (the website's switch ported), `push`, `account`, `grievance`, `report`; hooks in `lib/me-queries.ts`; screens `notices`, `account`, `contact`, `invite/[token]`, `+native-intent`; `ReportPanel` on vacancy and course pages; `src/push.ts` (the only file that touches `expo-notifications`, installed this sprint); sign-out goes through `endSession` (phone off the push list first, bounded to 3 s). 13 operations added to the surface (46 in all).
- **Verified.** `make check` (1,758), `make mobile-check` (473), iOS bundle, `make check-contract` (earlier 33 unchanged). **53 mutation checks** (backend and mobile), 52 killed; the survivor (a protocol-relative link) is **equivalent**, the table's own anchors refuse it. Against the **real worker and dev database**: a phone registered over HTTP, three notices queued, three pushes logged with fixed words and only a path as data. **Reviewer login** end to end on a second API with the echo **off**: the account made by the script, sign-in on the fixed code, a stranger refused, a second script run wrote nothing. **Browser run** (two seeded candidates, Hindi and English): updates, mark all read, open a notice to its vacancy, report, account, the delete preview (cancelled), contact with the status list, an invitation link.
- **Found only by running or by a test, and fixed at the cause.** (1) The first push design (a companion row at queue time) failed an existing statement-count test: **queuing must run no query**, so the worker decides, with a stamp. (2) A **tab badge hangs off an icon this bar hides**, so the unread number was drawn nowhere: it is in the label now. (3) The unread count was **never refreshed** (the tab is mounted all session): a 60-second poll plus a refetch when the app returns to the front (`AppState` wired to TanStack's `focusManager`). (4) `toBeDisabled` **also passes for anything inside a `Card`** (a plain Card is a disabled `Pressable`), so two "cannot confirm" tests could not fail: they read the button's own state now. (5) The web's contact intro points at a grievance page that does not exist on a phone: a phone-only sentence. (6) A third sign-in button on a signed-out vacancy page (the report panel's) was noise: it is a line of text. (7) `jest` mutations hold a five-minute timer each: the harness gives them an infinite `gcTime` (already noted for queries).
- **Not verified.** A real notification, the share sheet on a real device (the web run shows only its failure path), `expo-notifications` beyond compiling and bundling, Hermes, TalkBack and VoiceOver, low-end performance. Registration is a quiet no-op without an **EAS project id**. Export sizes measured: 9 to 18 KB for the seeded candidates, far below an intent's limit. `expo-doctor` 20 of 21 (five Expo packages one patch behind).
- **Open before any launch.** The app name and bundle id (`in.iism.app` placeholder), the Apple and Google accounts, an EAS project, deployment and a domain (for App Links), real SMS (DLT, BL-12.9), a **push vendor** and its credentials, **rotating `REVIEWER_CODE` and turning the switch off between store submissions** (a procedure for the runbook).
- **Gotchas.** Never write through golden phones `+919000000001`-`005`; a reload signs the `react-native-web` run out (no secure store on the web); a page-level `git checkout main -- .` from a subdirectory restores that whole subtree (one was run by mistake with nothing to lose: do not); `jest-expo` replaces `Request` with Expo's own, which rejects a body, so a test of anything that POSTs spies on `api.POST` rather than `fetch`.

### Sprint 64: M3 of the mobile app, the candidate's own side (done 2026-10-15, ADR-074, no migration; PR #54, merged)

Owner: "plan and close the next sprint"; read as plan, build, verify, write the records, stop before the commit.

- **Built.** Tabs are now Home, Jobs, Courses, **Matches**, **Me** (Standards left the bar, `href: null`, still reached from Home and the search). `SeekerGate` is the one answer for "who may see this": signed out gets the way in and **no request**, an expired session says so, an organisation-only account is told this is the job seeker's app. Screens: `(tabs)/matches`, `match/[slug]`, `(tabs)/me`, `applications`, `saved`, `interests`, `profile`; panels: `ApplyPanel` (vacancy page and match), `InterestPanel` (course page), `RolePicker`, `SuggestedCourses`.
- **Core** (`mobile/src/core`, no RN import): `me.ts` (every read and write), `applying.ts` (what may be withdrawn, one table of failures by status), `role-picker.ts`, `profile.ts` (limits mirrored on the inputs; education levels a record keyed by the schema's union), `suggestions.ts`, `matches.ts`, `me-keys.ts`, `format.formatInstantDate` (the day in India, no `Intl`), `sign-out-watch.forgetEverything`.
- **Contract.** Sixteen operations added (33 in all). `make snapshot-contract` only added; the earlier 17 are byte-for-byte equal.
- **Verified.** `make mobile-check` (329 tests), the iOS bundle by hand, `make check` (1,689), `make check-contract`. **43 mutation checks, each failing a check**; four survived first (a key the keys test did not list, an equivalent role-picker mutant, a guard mutant too weak, and **no test that adding a skill refreshes the matches**) and each was closed. Browser run at 375x812 against a second API on :8101 as seeded candidates `9000000001` (read and applied, then undone) and `9000000012` (a skill added and removed): matches, a match with real courses, apply through the confirmation, withdraw, applications, the role picker, Hindi plurals ("2 अनिवार्य मानक अनुपस्थित"), sign-out then the other candidate with nothing of the first left.
- **Found only by running it.** (1) A pressable card containing a Withdraw button is a button in a button (web warning; a screen reader would not reach the inner one): cards with actions are now plain with a "View the job" button, and a test per list asserts it. (2) The held-skills list repeated every name in a button label and was far too tall: a compact row with "Remove" whose accessible name is "Remove: name" (`Button` gained `accessibilityLabel`, which must contain the visible label). (3) A capped match showed a bare "Required": now "1 mandatory standard missing". (4) A reload signs the browser run out: `expo-secure-store` has no web backend.
- **The plan was wrong about one thing.** It said the in-memory cache was not cleared at sign-out; M2 already did it in an inline callback, untested. It is now `forgetEverything`, tested against the real token store.
- **Not on the phone, by decision.** The course budget, reporting that a course was opened (so click-through is web-only until M4), history sections of the profile, "why not me", career paths.
- **Not verified.** A native run, Hermes, TalkBack and VoiceOver, low-end performance. `expo-doctor` is 20 of 21: five Expo packages are one patch behind (`npx expo install --fix` is the owner's call; no package changed this sprint).
- **Open before any launch (unchanged):** the app name and bundle id (`in.iism.app` placeholder), the Apple and Google accounts, deployment, real SMS (DLT, BL-12.9), a store-reviewer login (BL-15.8), push (BL-15.6).
- **Gotchas.** Never write through golden phones `+919000000001`-`005` (`make evaluate` asserts on them); a test harness must give *mutations* `gcTime: Infinity` or Jest never exits; `renderHook` is async in RNTL 14; `jest` prints its summary to stderr (a harness that captures only stdout sees nothing); `python3` on the PATH is the wrong CPU for `nohup`, use `.venv/bin/python`.

### Sprint 63: M2 of the mobile app, browse on the phone (done 2026-10-14, ADR-073, no migration; branch `mobile-2`, uncommitted)

Owner: "plan and close the next sprint"; read as plan, build, verify, write the records, stop before the commit. No device exists on this machine (no Xcode, no Android SDK), so the screens were also **run in a browser through `react-native-web`**.

- **Built.** Tabs Home, Jobs, Courses, Standards; detail screens `job/[slug]`, `course/[slug]`, `skill/[slug]`; `search` (vacancies, then roles, then standards). Lists page 20 at a time (`useInfiniteQuery`), show a skeleton until the first answer (never "no results" first), keep the rows on screen when a later page fails, and say what the server said on a first-page failure with a Retry. Details put mandatory standards first and offer a "sign in to see how well you match" card (no apply: M3). The language is remembered (`iism.locale`).
- **Portable core** (`mobile/src/core`, no RN import, Node tests): `format` (Indian digit grouping, a date from `YYYY-MM-DD`; no `Intl`), `labels` (ports of the web's experience, salary, fee, place, intake and seats phrasing), `public` (the reads), `persist` (the allow-list), `plural-polyfill`, `sign-out-watch`.
- **Offline.** `PersistQueryClientProvider` with AsyncStorage; a query is kept only if keyed `["public", ...]` and it has data; 24 hours; wiped on the signed-in to signed-out transition.
- **Contract.** Ten read operations added to `mobile/contract/surface.txt` and the snapshot (17 in all).
- **Verified.** `make mobile-check` (strict `tsc`, `eslint`, 171 Jest tests, an Android bundle), the iOS bundle by hand (both reach Hermes bytecode), `expo-doctor` 21/21, `make check-contract`, `make check` (1,687). 28 mutation checks, each failing a test; one exposed a real defect (a fee of zero was not "free"). Three Python guards fail when broken. Browser run at 375x812 against a second API on :8101 (CORS needs `WEB_BASE_URL`): Home, Jobs with Indian grouping, Courses in Hindi with plurals, details, search, the error state, offline reading.
- **Found only by running it.** (1) A failed refetch while offline replaced the persisted list with nothing (the keep rule required `status === "success"`). (2) Every signed-out cold start wiped the cache (the token store reports `false` while loading). (3) A require cycle `ui/index` and `ui/list` (a Python guard now fails on any cycle). A stale Metro bundle hid fix (1) until Expo was restarted with `--clear`.
- **Not verified.** A native run; Hermes' own `Intl` and rendering; TalkBack and VoiceOver; scrolling on a low-end device. `npm audit --omit=dev`: 24 advisories, unchanged (build tooling). A console warning, "update to VirtualizedList not wrapped in act", appears in the jobs tests; it is noise, not a failure.
- **Owner's five-minute check.** `mobile/README.md`, "Run it": Expo Go on a phone against `http://<LAN address>:8000`.
- **Open before any launch (unchanged):** the app name and bundle id (`in.iism.app` placeholder), the Apple and Google accounts, deployment, real SMS (DLT, BL-12.9), a store-reviewer login (BL-15.8), push (BL-15.6).

### The mobile app, Sprints 62 to 66 (planned 2026-10-14; mirrors backlog v1.22 Epic B15)

| Sprint | Theme | Backlog | Migration |
|---|---|---|---|
| 62 | **M1 Foundations** — done, partly verified | BL-15.1, BL-15.7 | none |
| 63 | **M2 Browse** — done 2026-10-14 (browser-run, not native): home, search, jobs, courses, skills (public reads), language switch, public-data cache only | BL-15.2 | none |
| 64 | **M3 Profile, matches, applying** — done 2026-10-15 (browser-run, not native) | BL-15.3 | none |
| 65 | **M4 Alerts and account** — done 2026-10-15 (push without real delivery; browser-run, not native): push (backend + app), notifications, deep links, export, delete, grievance, report a listing; the reviewer login | BL-15.4, BL-15.6, BL-15.8 | 0055 `device_tokens` |
| 68 | **UI review** — done 2026-10-15 (Epic B16): findings, design-system plan, capture scripts; no screens built | BL-16.0 | none |
| 67 | **M6 Candidate parity** — done 2026-10-15 (browser-run, not native): history sections, why-not-me, career paths, the course budget | BL-15.9, BL-15.10, BL-15.11 | none |
| 66 | **M5 Store readiness and release** — done on the code side 2026-10-15 (no device, no EAS build, no submission): fail-closed release config, `eas.json`, `check-release`, size ceiling, accessibility guards, `docs/release/`. **The owner's accounts, bundle id, artwork, EAS project, deployment and push vendor remain** | BL-15.5 | none |

**Scope (owner, 2026-10-14): candidate-only for v1.** Employers, providers and operators stay on the web; a phone signed in as one is told to use the website. About 16 screens.

**Parity list (what the phone has that the web has).** Built on both: OTP sign-in and sign-up; browsing vacancies, courses and standards, their details and the search (Sprint 63; the phone has no filters beyond type, mode and kind, and no `/skills/{slug}` qualification or requirement bands). Sprint 65: updates with the new count, the account (export, delete), contact and the status of what was sent, reporting a listing, links by `iism://`. Sprint 64: matches with the gap and courses, apply/withdraw/save, course interest, applications and the employer's message, the profile basics and the role picker. Sprint 67: the profile's six history sections, salary, notice, work type, relocation and alerts, "why not me", career paths, the course budget. **Web only today: date of birth and gender, linking a certificate to a standard** (and everything for organisations and operators). Update this table in the sprint that adds a screen; a feature reaches the phone only after it is on the API.

**Store requirements to meet** (as understood on 2026-10-14; re-check at submission): in-app account deletion (exists: `DELETE /me/account`), a privacy-policy URL (the web's `/privacy`), a report mechanism for user content (exists), App Privacy labels and the Play Data Safety form, a demo/reviewer login, a working login for review, Apple minimum-functionality (the reason for the native build), a 14-day closed test for a new personal Play account (an organisation account avoids it).

**Owner decisions still open.** The app name and bundle id; who holds the Apple and Google accounts and whether they are individual or organisation; un-deferring deployment and SMS (DLT); the additive-only API policy (ADR-072, adopted in M1's code, awaiting the owner's explicit nod); the reviewer-login mechanism (an allowlisted number with a fixed code needs its own ADR because `otp_expose_in_response` must never be on in production).

### Roadmap: Sprints 56 to 61 (MVP: ready for the first real users), planned 2026-10-13

*Mirrors backlog v1.15 (Epic B14, section 4.4) and the plan file. Every sprint is code-only: no external account, no deployment, no billing.*

**How it was chosen.** Read: all 65 ADRs, the PRD/BRD/FRS/Product-Definition/Scope-Reconciliation documents, backlog v1.14, the code (every gap below was grepped). The documents never say "MVP"; the PRD and FRS
call v1 complete, and it is: all 25 user stories and every FRS "shall" are built. So the MVP question became *what would a first real user trip over?* A planning agent then pressure-tested the order against the
code: trust moved ahead of courses, report/takedown was split from contact/grievance, and alert preferences and a partner write API were dropped.

| Gap (verified) | Why it matters |
|---|---|
| Sign-up has no "send a new code" (only `SignInForm.tsx`); no server resend cooldown | A one-time code is the only way in; a lost SMS is a lost user |
| Credentials can be linked, never unlinked or replaced | A lost number locks the account out |
| `Course` has no location, intake date or seats; recommendations rank by mandatory-gap closure only | An offline course in another state is recommended like one next door |
| No way to report a vacancy or course; no operator takedown | Fake vacancies are the main trust risk |
| `/contact` is a `PlaceholderPage`; `/grievance` is static text | The DPDP Act expects a working grievance route |
| An employer can change a status but cannot say when or where | The hiring loop stops one step short |
| No notification page or unread badge (notices only inside `/applications`) | A candidate may never see a status change |
| Agency enrolment is a CLI an engineer must run | The agency actor cannot pilot |

| Sprint | Theme | Backlog | Migration | Size |
|---|---|---|---|---|
| 56 | **Never locked out** — **done 2026-10-13** | BL-14.1 resend + cooldown; BL-14.2 replace/remove a credential | none | M |
| 57 | **A way to complain** — **done 2026-10-13** | BL-14.3 `/contact` and `/grievance` forms, operator queue, retention | 0050 `grievances` | S-M |
| 58 | **Courses you can attend** — **done 2026-10-13** | BL-14.5 course place + next intake + seats; BL-14.6 attendable-and-affordable ranking | 0051 `courses` columns | M |
| 59 | **A marketplace you can trust** — **done 2026-10-13** | BL-14.4 report a listing; operator takedown | 0052 `listing_reports`, takedown columns, CHECK, template | L |
| 60 | **Hiring that finishes** — **done 2026-10-13** | BL-14.7 status message; BL-14.8 notes + CSV export; BL-14.9 notification page | 0053 `applications` columns | M |
| 61 | **A pilot with an agency** — **done 2026-10-14** | BL-14.10 operator enrolment upload | 0054 `enrolment_batches` | M |

**Per-sprint notes (reuse, and watch for).**
- **56.** Cooldown in `core/security.py` `enforce_otp_rate_limit` (`SET NX EX`, a 429 with `retry_after`) so all four callers get it; the cooldown is 0 in `tests/conftest.py`. `replace_credential` / `unlink_credential` beside
  `confirm_link` / `request_link_code` in `identity/service.py`: unlink refused for the only credential, replace needs a code to the new identifier and a live session, both revoke refresh tokens;
  `ck_users_has_identifier` already guards "at least one"; `IntegrityError` on the unique index is a 409. `SignUpForm.tsx` gets the resend control with a countdown. The ADR must say that phone codes reach a real
  phone only once DLT exists (so recovery works first by email; add a "backup email" nudge) and that a recycled number lets its new holder in.
- **57.** `grievances` (reference, kind contact/grievance/data_request, body, optional `user_id` FK SET NULL, status). A user FK makes it a person table: add it to `EXPORTED` in `tests/test_privacy_coverage.py`; a
  reply address is stored by value and purged on a schedule like `notifications.purge_expired`. New `OPS_GRIEVANCE_*` permissions (update `TIER_PERMISSIONS` and `tests/test_authorization_matrix.py`). Anonymous write:
  the write limiter, a length cap and a honeypot field.
- **58.** `state_id`, `district_id`, `starts_on`, `seats` on `courses`, resolved with `geography.resolve_location` in `course_publishing.py`; extend `bulk.py` (`COURSE_COLUMNS`, `_plan_course`, `_merge_updates`).
  **Seats are derived** from enrolled `CourseInterest` rows, never a counter. Ranking: an optional attend context on `courses_closing_gap` (`matching/service.py`); sort = covers-mandatory, then attendable, then
  closes-count, so a nearby course never outranks one that unblocks a mandatory standard; a past `starts_on` is not attendable. Extend `CourseSuggestionOut.from_suggestion` (shared with `careers/service.py` and
  `applications/service.py`). Budget is a query parameter (a profile column would need export/erasure treatment). **Do not touch `scoring.py` (ADR-037).** Golden-set expectations derived from inputs.
- **59.** `listing_reports` (`target_type`, `target_id` with no FK, title snapshot, reason, reporter FK SET NULL, unique per reporter and target). **No third `Job.status`** (fourteen places compare
  `status == "published"`): takedown sets `status="draft"` and stamps `taken_down_at` / `takedown_reason`; `publishing.publish_job`, `course_publishing` and `bulk.publish_many` refuse while stamped; a taken-down
  vacancy also closes with a reason so applicants hear through `vacancy_closed`. Hand-written CHECK migrations for events `listing_reported` / `listing_taken_down` and the `listing_removed` template (the 0041 / 0044
  pattern). `record()` after the commit, in the service (`tests/test_route_delegation.py`). Takedown is admin tier, dismiss is support tier.
- **60.** `applications.status_message`, `status_message_at` (candidate-visible), `employer_notes` (private). Free text in the outbox: cap it and decide once how it sits with "the outbox holds no phone number" (an
  interview contact may contain one; notices are kept 90 days). Message in the privacy export; notes included or excused with the reason written down. CSV export through the **same serialiser as the applicant list**
  (a second construction site would break `candidate_card()`'s guarantee), obeying `contact_is_visible`, neutralising leading `= + - @` (check `bulk.errors_csv`), recording `applicants_exported`. Notification page:
  unread badge, `/notifications`, mark-one-read, paging past 50 (`web/src/components/Notices.tsx` already renders `GET /me/notifications`).
- **61.** Move the engine out of `scripts/bulk_enrol_candidates.py` into `api/modules/operations/enrolment.py` (the script becomes a thin caller): a **sibling** of `bulk.py` (ADR-026; `bulk.run` is hard-wired to a tenant
  and the jobs/courses `Kind`) reusing `parse_file`, `decode`, `template_csv`, `errors_csv`, `_int`. Calls `identity.provision_candidate` and `geography.resolve_location` through public interfaces
  (`tests/test_module_boundaries.py`). `OPS_ENROL`, admin tier only; the operator attests that the privacy notice was read out and the batch records who attested; phones masked in reports (`redaction.py`).

**Cut lines.** 56 keeps resend + cooldown and defers replace/remove; 59 ships report + takedown and defers the notice template; 60 ships the message and defers export; 61 can wait for a real agency.

**Considered and not scheduled.** Alert preferences beyond on/off (the job alert is the only unsolicited message); a partner write API / ATS push (BL-12.18; no partner has asked, and it needs signed outbound webhooks
and a key-to-tenant binding); XLSX upload, upload history and async above 200 rows (BL-12.18, on demand).

**Gated, with the unblocker.** CV upload and résumé extraction (BL-4.1, BL-4.2): needs the ADR-023 encryption path (BL-13.2) first; build them together, only when an employer segment asks (the PRD persona is phone-only,
and Sprint 23 found a CV fills experience and education, which no scorer reads). Real embedding model (BL-5.3): a ~470 MB download and a hosting decision; if wanted, a measured shadow evaluation against the golden set
before `match_weight_semantic` goes above 0. SMS alerts (BL-12.9): DLT registration. Hindi standards corpus (BL-12.10): translation credentials. Observability (BL-13.1): needs a deployed instance. Course credit chips
(BL-12.8): no course links to a qualification. Needs a person, not code: BL-12.11 (confirm the PWA on one phone) and BL-12.12 (a labour-market reviewer for role aliases: 43 of 3,417 roles).

**Owner decisions this roadmap needs (none block Sprint 56).** Confirm the order (trust before courses is the recommendation); CV upload with the encryption path: build or hold; real embedding model: shadow-evaluate or
hold; someone for the alias review and the five-minute PWA check.

### Also queued, do not lose

- **Watch the first CI run after 2026-10-19** (Ubuntu 26, above) and the next audit result.
- **Restart `make api` and `make worker`, and run `make migrate`** (0049 is owed; the dev API and worker have run since Oct 6 and serve old code).
- **Bulk upload later stories** are one backlog item, **BL-12.18** (XLSX, partner/ATS push, upload history, async above 200 rows); earlier notes called them "14.9 to 14.12", which are not backlog ids.
- **Not covered by the browser checks:** visual regression, other browsers, real devices, and padding that is present but wrong. Screenshot comparison stays rejected as a larger, noisier dependency.
- The rest of "Also outstanding" below, and the owner-held items under "Known gaps".

**Housekeeping the owner must do or confirm:** `make migrate` on the dev database (0049). All earlier GitHub tokens were deleted by the owner on 2026-10-09; the one in use now is `gh`'s own login (§6).
**Standing owner decisions:** K stays 500; monetisation (`BL-1.3`) and real external integrations stay deferred; never sign in as `+919880663641`; commit and push
only when asked.

**Known gaps, unscheduled:** the overview still joins one row per (vacancy, sharer) pair; 10,000 enrolled is a 17.6 s request; `corpus_stats` stays uncached on
purpose. Public `q` search was **measured fine** (under 30 ms at 5,000 vacancies). Blocked or owner-held: course credit chips, the alias batch (43 of 3,417 roles),
BL-5.3 real embeddings, BL-12.10 Hindi corpus, BL-12.11 PWA on a real phone, SMS alerts (DLT), BL-1.3.

### Also outstanding, in rough order

- ~~**Grow the golden set.**~~ **Done 2026-09-23 (Sprint 29)**: 34 pairs, 7 orderings and 16 course
  expectations, including the first labelled data course recommendation has ever had. The
  monetisation ADR can now cite one of ADR-025's three metrics honestly; the other two still need
  users rather than code.
- **SMS, which is what job alerts actually need.** Sprint 27 shipped in-app plus email; 39 of 40
  candidates are phone-only, so most alerts land only when somebody opens the site. This is
  blocked on DLT registration, not on design.
- ~~**`is_verified` still has no writer.**~~ **Closed 2026-09-23 (Sprint 28)**: `users.is_staff`, `/ops/*` and `make grant-staff`. See the Sprint 28 entry above.

### The three pillars, and where each actually stands

*Assessed 2026-09-22 against the tree, not from memory. The owner's stated goal is a marketplace
that sells courses, connects jobs, and carries gig work.*

- **Job connect — built, end to end**, and ahead of the other two. Publish → NSQF-scored match →
  apply → employer inbox → contact disclosed. What remains is Sprint 26's lifecycle and reach.
- **Selling courses — listed and demanded, never sold.** `Course.fee_inr` exists and renders, and
  **nothing downstream reads it as money**: `api/adapters/payments/` (Sprint 34, ADR-043) is a
  protocol and a console implementation with no caller, deliberately — no order, entitlement,
  enrolment, refund, payout or invoice table in any of 38 migrations. **ADR-025 still forbids
  writing billing code** until a successor ADR cites precision@5 on the golden set (34 pairs,
  citable since Sprint 29), candidate-to-course click-through and provider-reported enrolment
  conversion. Sprint 38 (ADR-047) closed the *structural* half of the remaining gap — `make
  monetisation-metrics` now answers both, reading `analytics_events` and a new provider-reported
  `"enrolled"` status on `CourseInterest` — but not the *volume* half: verified live, both metrics
  read real but small on this dev/demo database (`1/5` click-through, `3/15` enrolment conversion),
  because a handful of seeded actors generated them, not real product usage. **`BL-1.3` is still not
  authorised** — ADR-047 says explicitly that closing the volume gap needs either real traffic or an
  explicit owner override, and takes no position on which. Note also that Sprint 24's "interest, not
  enrolment" reasoning **inverts** the moment money moves through the platform: if we take the
  payment, we are the system of record for the enrolment.
- **Gig work — built in Sprint 37 (ADR-046), reusing `Job`/`Application`.** The
  September 2026 assessment above (and ADR-045's original design) argued gig work needed its own
  module because it was a genuinely different market; the owner's direct instruction — "a gig work
  can also be considered as a temporary job assignment" — rejected that premise before BL-8.2 was
  built. `employment_type="gig"` plus a real `closes_at`/`positions`/`district_id` on the existing
  `Job` gives matching, ranking and auto-close everything they need, with zero changes to
  `matching/service.py` or `scoring.py` — verified live, not just in pytest (§11, Sprint 37).
  `Application` carries the completion event (`completed`/`no_show`, reachable only from `hired`)
  and a full two-sided `application_reviews` table is the reputation layer, foundation-only (a
  writer, no reader yet, the `SkillRelation` shape). An employer can post a gig and a candidate
  can find, apply to and track one in the interface. **Sprint 41 built the rest of the interface**:
  the employer's completed / no-show controls, both sides' rating form, and the reputation figures
  (a poster's on the job page and employer dashboard, a worker's on their own dashboard — never on the
  de-identified candidate card). What is genuinely still missing is any payment/payout, which ADR-045 §5
  and ADR-025/ADR-043's billing gate both still forbid.

**Nothing built so far has to be undone for any of it**, which is the important finding. The
expensive assets — 21,303 NSQF standards with role search, one pure deterministic scorer, one
identity many roles, two working consent-and-revocation disclosure loops, geography to
sub-district — are exactly what all three pillars need.

Suggested order, re-revised 2026-09-29: the management-facing actor-breadth MVP (Sprint 33), the
monetisation ADR with a **payment adapter port only** (Sprint 34), Epic B3's verified evidence
(Sprint 35), BL-5.1/5.2 plus BL-6.1's foundation (Sprint 36), BL-7.3 plus Epic B8's gig work
(Sprint 37), and closing ADR-025's structural gate (Sprint 38, ADR-047) are all behind us now —
see each one's entry in §11. `BL-1.2` (the payment port) has in fact been done since Sprint 34; the
backlog document's tag was simply stale and is corrected as of this sprint. **`BL-1.3` (the billing
module itself) remains genuinely not started**, and is not a free next pick: it needs either real
traction numbers or an explicit owner override of the volume gap ADR-047 names, the same kind of
call already made once for Epic B8 over ADR-045. Course checkout, résumé ingestion, the rest of
Epic B6, and gig work's own frontend controls (§11's Sprint 37 and 38 entries name both gaps)
remain queued behind whichever the owner picks.

### Then, in rough order of value

- ~~**Grow the golden set.**~~ **Done 2026-09-23 (Sprint 29).** 34 pairs against 20 vacancies, plus
  orderings and course expectations. Still short of the 50–100 the original plan named, and the
  remaining gap is labelling effort rather than machinery.
- ~~**`is_verified` has no writer.**~~ **Closed 2026-09-23 (Sprint 28).** The API half is done —
  `users.is_staff`, `/ops/*`, `make grant-staff`, ADR-042. **The `/admin` pages are Sprint 29**;
  until they land an operator uses `/docs` or `curl`, which is fine for a handful of internal
  people and is why the UI was the half that could be cut.
- **CV upload and LLM extraction.** Deferred in Sprint 23 after establishing that it fills
  experiences and education, which no scorer reads, and needs multipart, object storage, a documents
  table, PDF/DOCX extraction, AES-256-GCM with KMS (ADR-023) and an `LLMProvider` adapter (ADR-031)
  before one skill reaches a profile. Revisit once role-led suggestion shows what gap remains.
- ~~**Semantic similarity**~~ **Closed 2026-09-27 (Sprint 36).** The mechanism exists end to end
  (`api/adapters/embeddings/`, the two embedding columns, the worker sweep, the additive bounded
  term in `score_match`) and is off by default (`match_weight_semantic=0.0`) — turning it up is a
  deliberate, separately-measured re-tune, not yet done, and the embedding provider itself is a
  placeholder (feature hashing, not the ADR-013/031 sentence-transformers model — see Sprint 36's
  entry). Still the answer if role search ever proves too weak; the plumbing no longer needs to
  be built first.
- **Hindi for the corpus.** The interface is fully bilingual; the *corpus* is not. Say that plainly
  in any demo. ~$5 for the navigable surface, blocked on credentials rather than design.
- **Confirm the PWA installs on a real device.** Manifest, icons and worker are in place and tested
  for correctness, but the in-app browser pane will not register a worker, so nothing has proved
  Chrome offers "Install". One phone, five minutes — until then say "installable" with the caveat.
- **A learner-facing notice when a provider marks "contacted"**. Found in Sprint 24 and
  deliberately not built. *(Its sibling — notifying applicants when an organisation deletes itself
  — was closed on 2026-09-23 along with the organisation-deletion route.)*
- ~~**Ownership transfer as one act.**~~ **Done 2026-10-04 (Sprint 44)**: `POST /org/{slug}/transfer-ownership`,
  and the race that made the old two-step unsafe is closed. See the Sprint 44 entry.
- **`CLAUDE.md` cites ADR-026 for the siblings-not-generalisations rule.** ADR-026 is *Supply
  Acquisition Strategy*; that rule has no ADR and lives only in `CLAUDE.md`. Either write it as one
  or stop citing a number for it.
- Still unbuilt and ADR'd: career paths (ADR-008, and the NCO codes now exist) -- the graph it would
  traverse now has its foundation table (`SkillRelation`, Sprint 36, BL-6.1) but no edges, no
  inference and no route yet (BL-6.2/6.3) -- observability (ADR-019), the ADR-023 encryption path,
  caching as caching (ADR-020).

### Measured in Sprint 27 (performance and security)

- **The lifecycle predicate costs nothing.** A/B of the same queries with and without
  `closed_at IS NULL`, 200 iterations each: browse `+0.001ms`, homepage count `-0.001ms`, matching
  retrieval `-0.001ms`. The homepage count uses an index-only scan on the new
  `ix_jobs_status_closed`. All five new query shapes plan sub-millisecond.
- **Do not compare raw throughput against §12a without checking the box.** A re-run measured
  `/skills?limit=24` at 72 rps against §12a's 350 — but `/skills` is **untouched** by Sprint 27
  and degraded 4.9×, while `/jobs`, which the sprint *did* change, degraded only 2×. Docker
  Desktop was at 56% CPU, Spotlight at 34%, load 3.38 on 8 cores, and the API was running with
  `--reload`. The database is ~0.1ms of a ~126ms request, which is §12a's own conclusion intact:
  **the bottleneck is Python CPU, not the database.**
- **Security spot-checks all held**: the new close/reopen endpoints answer 401 anonymous and
  **404 (never 403)** to a non-member; the public job payload still carries no `contact_email`;
  the rate limiter still returns 429 under a burst; nothing in `api/` reads the `ssc` collection;
  and the alert sweep logs four integers and no identity. 103 security-focused tests pass.

### Left behind by Sprint 26, worth knowing

- **The first-load budget has 16 KB of headroom** (668 KB against 684). Radix Dialog took ~33 KB
  and `next/dynamic` made it *worse* rather than better, because the header mounts the dialog on
  every route anyway. **The next component added to the header will breach it**, and the answer
  then is either a hand-rolled portal (~2 KB, but a focus trap is genuinely hard) or raising the
  budget deliberately with a reason.
- **Fonts cost 47 KB on an English page and 166 KB on a Hindi one**, measured against a production
  build. That is the price of Hindi rendering the same on every platform; it is worth it, and it
  should be said out loud rather than discovered.
- **`is_verified` had no writer until Sprint 28**, so anybody may create an organisation under any
  name and nothing vouched for it. The duplicate guard added this sprint is per account, not
  global — two accounts may still both
  create "Apollo Care", which is correct (two employers may share a name) and is *not* a substitute
  for verification.

### In flight, not on the branch

*Nothing. The geography fix that sat here for five sprints landed in Sprint 28, rewritten against
current code rather than carried from the stale worktree — see the Sprint 28 entry above. The
`claude/angry-jackson-46292c` worktree and branch are deleted.*

## 12a. Measured performance (re-audited 2026-09-05, after the corpus landed)

Single uvicorn worker, load generator on the same box, so **treat throughput as a floor**.
The database was **485 MB** when this was measured; it is **557 MB** as of 2026-09-09, across
21,355 skills and ~614,000 content rows. The timings below were not re-run.

| Endpoint | c=10 rps | c=50 rps | p50 | p99 (c=50) |
|---|---|---|---|---|
| `GET /skills?limit=24` | 350 | 313 | 19 ms | 589 ms |
| `GET /skills/{slug}/requirements` | 235 | 230 | 34 ms | 895 ms |
| `GET /skills/search?q=` | 154 | 183 | 57 ms | 648 ms |
| `GET /jobs` | 135 | 149 | 66 ms | 1,159 ms |

**The 2026-09-02 conclusion still holds: the bottleneck is Python CPU, not the database.**
Throughput is flat across concurrency while p99 climbs an order of magnitude — the signature of a
saturated single process, not a slow query. Serving 614k content rows did not move the numbers,
because every hot path is index-backed:

- `/skills` first page uses `ix_skills_qp_count` with an incremental sort.
- Content fetch is two index scans (`ix_performance_elements_skill_id`, then
  `ix_performance_criteria_element_id`) — 7.5 ms for a 128-criterion standard.
- FTS still uses the GIN index at 21k rows; the trigram fallback uses `ix_skills_name_en_trgm`.

**One new weakness the corpus exposed.** Deep offset paging degrades badly: `offset 21000`
seq-scans and fully sorts all 21,355 rows (70 ms against 7 ms for the first page). Fine while
people browse the first pages, wrong if anything ever walks the catalogue. Keyset pagination on
`(qp_count, name_en)` is the fix when that matters.

**Still not ready for 1000 concurrent users.** Outstanding, in order:

1. **No caching.** Redis serves only OTP, refresh tokens and the ARQ broker — ADR-020 is
   unimplemented. The taxonomy is near-static and the bulk of the database is read-only
   reference data.
2. **Single uvicorn process.** Multiple workers is the cheapest win available.
3. **Connection pool maths.** 15 connections per process against `max_connections=100` caps you at
   ~6 processes; PgBouncer before that.
4. **Deep offset paging**, as above.

Fixed since the last audit: the four missing filter indexes, and the browsers that fetched
`limit=200` and filtered client-side — `/skills` now pages server-side.

## 12b. Security posture (audited 2026-09-02)

**Fixed in this pass:**
- `POST /tasks/ping` was unauthenticated and enqueued work — 25 anonymous
  requests queued 26 jobs. The demo router is now mounted only when
  `settings.is_local`, so the path does not exist in production.
- The console notification provider logged the OTP **and** the full phone
  number. It now logs `notification dispatched to +9198*****999 (63 chars)`.
- Added composite indexes on the columns every listing filters by.

**Closed in Sprint 20 (2026-09-11):** rate limiting on every class of request
(auth, write, read — per account when signed in, per IP otherwise, fails open);
security headers on the API and the web app (the web CSP is **enforced in a production build** (report-only in `next dev`) and
still allows inline scripts — see `CLAUDE.md`); DPDP consent, export and erasure;
a 256 KB request body cap; `/docs` and `/openapi.json` local-only; CORS without
credentials.

**Still open:**
1. `/health/deep` is public and returns raw exception strings.
2. The web CSP is not yet enforced, and enforcing it strictly needs nonces, which
   need dynamic rendering.

**Verified safe, so do not re-litigate:** SQL injection is not possible — the
raw search query is fully parameterised and `x'; DROP TABLE skills; --` left
the table intact. Cross-user isolation is correct and tested. No tokens reach
the logs. CORS is restricted to one origin.

## 12. Open risks — state these honestly, do not soften

- ~~The work exists in one place.~~ **Re-closed 2026-09-09** — and it had quietly re-opened:
  this line said "Closed 2026-09-07" while Sprints 11–14 sat unpushed. See §10. MongoDB,
  which it named as unbacked, gained encrypted dumps and a passed restore drill in Sprint 20 — but
  **the dumps are still on this laptop**, so a lost laptop loses both copies. Off-machine storage
  has not been scheduled; it was assigned to Sprint 21 and that sprint closed the application loop
  instead.

- Two-sided cold start is unsolved; hybrid supply is a bet, not a solution.
- No revenue model, and free may become the permanent default by inertia.
- Multi-sector dilutes GTM focus — a knowing trade, reversible by narrowing GTM only.
- Recommendation quality is **measured, and not continuously**. Sprint 29 took the set from five
  pairs to **34 pairs, 7 orderings and 16 course expectations**, which is enough to defend a
  weighting — the five never were. Two things still qualify every claim. `make evaluate` **cannot
  run in CI** (it needs the 21,303-standard corpus, which is not in the repository), so the number
  is produced by hand rather than on every change. ~~And **precision has no negative class**~~
  **Closed in Sprint 33.** `course_dismissed` gives `course_recommended`/`course_opened` a negative
  signal for the first time -- "shown and ignored" and "shown and rejected" are no longer the same
  rows. What remains is volume: near-zero real dismissals exist yet to measure against.
- ~~Self-declared skills are unreliable until assessment integration lands. Three of the four
  `SKILL_SOURCES` have no writer at all.~~ **Two of three closed in Sprint 35.**
  `api/adapters/assessment/` plus a webhook writes `assessed`; an operator-verified certification
  path writes `certified`. Neither has *volume* yet -- no real assessment partnership is signed, and
  the certification-verification queue depends on candidates adding certifications with a
  `skill_slug`, which is not a step the profile wizard currently prompts for -- so
  `EVIDENCE_WEIGHT_SHARE` is no longer *structurally* a constant, but it may still be one in practice
  until either happens. `inferred` remains unwritten anywhere; that is BL-4.1/4.2's résumé-ingestion
  territory, deliberately still separate.
- Employer-side supply is the weakest link in Indian vocational markets.
- ~~Two vocabularies coexist.~~ **Closed in Sprint 9.** The 52 curated skills are retired and
  every link points at a National Occupational Standard. What replaced it is a smaller, honest
  debt: the curated→NOS map is hand-authored, so some anchors are judgement calls. The uncertain
  ones are marked in `scripts/legacy_skill_map.py`.
- **The national taxonomy is English-only.** The carried aliases (298 rows as of 2026-09-09) are
  the only Hindi reaching it, covering a few dozen standards out of 21,355. Sprint 23's role search
  narrows the practical damage — a learner types "ward boy" or "ड्राइवर" and the alias map bridges
  to the English role name — but the standards, course titles and role names a provider publishes
  are still English on a Hindi page. Say this plainly.
- ~~4,784 imported skills are unreachable by sector navigation.~~ **Resolved in Sprint 8** — every
  standard states its own sector, so the hierarchy no longer depends on the qualification side.
  They still belong to no current qualification, which is a fact about the corpus, not a defect.
- **7,459 of 21,263 current standards publish no performance criteria at all.** Gap analysis will
  simply have nothing to say about a third of the taxonomy, and no amount of importing fixes it.
- **The source's own arithmetic does not always add up.** In 422 of 23,903 comparable elements the
  criteria marks do not sum to the element total (e.g. 8+6+6=20 against a stated 23). Reproduced
  faithfully rather than corrected — silently "fixing" a national standard would be worse.
- **Only 45 of 21,303 titles are section-numbered course fragments** ("10.1. Case Studies") but
  they are indistinguishable from real units in the schema. Prominence ordering hides them; it
  does not fix them.
- **A quarter of the corpus shares a name.** 1,778 standard names are borne by 4,838 rows, and some
  twins are near-identical reissues differing only by code and level. Sprint 24's search cards name
  the qualification, body and code and flag lookalikes; nothing can make two identically-named
  standards meaningfully distinguishable when the source itself does not distinguish them.
- ~~**Three district names exist in two states each** (Pratapgarh, Hamirpur, Bilaspur) and resolve
  arbitrarily.~~ **Closed 2026-09-23 (Sprint 28).** `PlaceIndex` constrains an ambiguous name to its
  written state and resolves it to nothing when there is no state to choose by. Verified against the
  imported corpus: exactly three names are ambiguous, and zero live rows held a district outside
  their resolved state.

## 13. What it would take to run this for a real customer

Written down on 2026-09-09, re-checked 2026-09-22, so the answer exists before it is asked in a
meeting. **Nothing here
is a defect** — every item is a deliberate stage-appropriate choice, and each one is load-bearing
for a demo precisely because it is absent. But a live pilot needs all of it, and the first three
are hard blockers rather than gaps.

**Blockers — a deployed instance today would let nobody in.**

1. **No SMS provider and no email provider.** `ConsoleNotificationProvider` and
   `ConsoleEmailProvider` both *raise* when `ENVIRONMENT == "production"`, by design (ADR-017):
   a no-op provider would look exactly like working authentication that nobody can complete.
   There is no password anywhere in the product (ADR-038), so an OTP that cannot be delivered is
   an account that cannot be entered. Needs a DLT-registered SMS vendor — DLT applies to SMS and
   not to email, which is why `EmailProvider` is its own port — behind the existing adapters.
2. **No Dockerfile and no deploy target.** `infra/` holds a single `docker-compose.yml` for local
   Postgres, Redis and Mongo. There is no application image, no Terraform (ADR-028 defers it), and
   CI runs lint, typecheck, tests and the web build with nothing to ship them to.
3. ~~MongoDB is backed up by nothing.~~ **Closed in Sprint 20**: encrypted dumps of both
   databases and a passed restore drill (§10a). **What remains is off-machine storage** — the dumps
   are still on this laptop, so a lost laptop loses both copies. Not yet scheduled.

Also closed in Sprint 20, and would have been blockers: consent, export and erasure (DPDP Act
2023), privacy notice / terms / grievance pages — **still drafts pending legal review, and the
grievance officer is not yet named** — rate limiting, and security headers.

**Required before real candidate data, not before a pilot instance.**

4. **The ADR-023 encryption path does not exist.** No `encrypt` anywhere in `api/`. Aadhaar,
   resumes and assessment results are all named by that ADR and none are collected yet, which is
   the only reason this is not already a breach waiting to happen. It must land *before* the first
   feature that collects any of them, not alongside it.
5. **ADR-019 observability is unbuilt.** No OpenTelemetry, no Prometheus, no Grafana; structlog
   and `/health/deep` are the whole story. Adequate for one laptop, not for diagnosing a customer's
   report.
6. ~~**`is_verified` has no writer.**~~ **Closed 2026-09-23 (Sprint 28).** `users.is_staff`,
   `/ops/*` and `make grant-staff` (ADR-042). It is still absent from `OrganisationIn` — no request
   shape can set it, and none can set `is_staff` either. The `/admin` pages landed in Sprint 29. What remains
   for a pilot is a notification when a badge changes, **so a revocation is currently silent**.
7. ~~**No teammate invitations.**~~ **Closed in Sprint 25.** Invitations, roles, the last-owner
   guard and the escalation rule all ship, and the sole-owner data loss this line described is
   refused with a 409 that is now reachable. `admin` and `member` are live roles.

**Would embarrass in a pilot, cheap to fix.**

8. ~~Five of six rich-profile collections are empty.~~ **Closed in Sprint 21** — the seed now
   writes work histories, education, languages, certifications and preferences (21/20/40/20/21/20
   rows as of 2026-09-22).
9. ~~The golden set is five pairs.~~ **34 pairs, 7 orderings and 16 course expectations as of
   Sprint 29.** What remains is that `make evaluate` cannot run in CI — it needs the 21,303-standard
   corpus, which is not in the repository — so the number is real and is produced by hand.
   `tests/test_golden_set.py` guards everything about the set that is checkable without a scorer.
10. The corpus is English-only (§12), in a product whose thesis is Hindi-first. The *interface* is
   fully bilingual, including everything Sprints 23–24 added; the standards themselves are not.
