# NSQF source corpus — what the data actually looks like

Findings from auditing `iism_nsqf_master_data` in MongoDB, recorded so a future migration starts
from knowledge rather than rediscovering it. Every number here was measured against the full
collections, not sampled, unless it says otherwise.

The first migration attempt (Sprint 6, since discarded) got several of these wrong. Where that
happened it is said plainly, because the *way* it went wrong is the reusable lesson.

> **Status:** the corpus is being extended with further master data — sectors, Sector Skill
> Councils, states, districts, awarding bodies. A complete re-migration is planned once that
> lands. Treat the counts below as describing the corpus as of 2026-09-04.

---

## 1. Field naming is inconsistent between collections — this is the biggest trap

The same concept is named differently depending on which collection you are in. Checking one
collection using the other's field name returns zero and reads exactly like "this data does not
exist".

| Concept | In `nos` | In `qps` | In `modelcurriculum` |
|---|---|---|---|
| NSQF level | `nsqf` | `nsqfLevel` | `nsqfLevel` |
| Unit type (Core / Non-Core) | `type` | `compulsoryNos[].nosType` | — |
| Sector | `Sectors` (capital S) | `sectors` (lowercase) | — |
| Occupation | `Occupation` | `occupation` | — |
| Compulsory units | — | `compulsoryNos` | `nos.compulsary` *(sic)* |

**This caused a real error.** Sprint 6 checked `nsqfLevel` against NOS documents, got zero, and
concluded "a NOS carries no NSQF level — zero of 27,538 do." That claim was then written into the
schema design, four commit messages, `CLAUDE.md`, `projectContextForMe.md`, code comments and
test docstrings. **All 27,538 NOS carry their own level**, in `nsqf`.

The consequence of building on it: `skills.nsqf_level` was derived as the modal level of the
containing qualifications, which left **4,730 units with no level at all** and **contradicted the
declared level on 653 more**.

**Rule for next time:** never conclude a field is absent from one collection using another
collection's spelling. Enumerate the actual field paths per collection first.

A second instance of the same trap: `type` on a standalone NOS document is present on only
**3,952 of 27,538**, but the copy embedded inside a qualification carries `nosType` on **98.7%**
of entries. Reading only the standalone field leaves Core/Non-Core 92% empty — and Core vs
Non-Core is what elective grouping *means*.

A third: `$exists: true` matches the empty string. **2,399 of 2,585** model-curriculum entries
have a `unitCode` that is present but blank, so an existence check reports data that is not there.

---

## 2. Collection sizes and natural keys

| Collection | Documents | Distinct codes |
|---|---|---|
| `qps` | 4,669 | 4,424 `qpCode` |
| `nos` | 27,538 | 21,263 `unitCode` |
| `modelcurriculum` | 2,585 | — |

**Codes are versioned, not unique.** The natural key is `(code, version)`. Importing only the
latest version of each code is a defensible choice, but it must be a choice, not an accident.

---

## 3. NSQF levels

Every one of the 27,538 NOS states a level, as a **string**:

| Level | NOS | | Level | NOS |
|---|---|---|---|---|
| 4 | 7,476 | | 3.5 | 696 |
| 4.5 | 6,887 | | 5.5 | 596 |
| 5 | 3,994 | | 2.5 | 475 |
| 3 | 3,600 | | 7 | 409 |
| 6 | 2,141 | | 3.0 | 227 |
| 2 | 712 | | 6.5 | 96 |

Three things follow:

- **Half-levels are ~38% of the corpus.** Any integer column, Pydantic schema or query parameter
  silently excludes them. 4.5 alone is 6,887 units. A UI filter offering levels 1–10 hides them
  behind a control that looks like it works, and returns a *correct empty page* — which no test
  notices.
- **`"3"` and `"3.0"` are the same level** in different spellings. Normalise to `Decimal`.
- Levels are 1–7 in practice, despite the framework defining 1–10.

**A level is stated in three places and they are three different facts:**
1. the standard's own declared level (`nos.nsqf`),
2. the qualification's level (`qps.nsqfLevel`),
3. the level the unit sits at *inside* a given qualification.

A unit genuinely appears at different levels in different qualifications. Store all three; do not
collapse them, and do not derive (1) from (2) — it is stated directly.

---

## 4. The hierarchy above a unit

- **Sector:** 43 distinct `sectorID` on qualifications, 41 on standards. **47 distinct sector
  *names* collapse to 43 IDs** — four IDs each carry two spellings of the same sector (e.g.
  `"Healthcare"` and `"Healthcare "`). Key on the ID, never the name.
- **Sub-sector:** 540 distinct.
- **Occupation:** free text. 1,144 distinct values on the qualification side, **1,650** on the
  standard side, with no stable identifier joining them. `occupationCode` is present on only
  19,867 of 27,538 NOS. A table keyed on the text is not defensible; denormalise it.
- **Sector Skill Council:** `originSSC` appears on only **427 of 4,669** qualifications. There is
  no usable SSC dimension in this corpus. *(Incoming master data may change this — check again.)*

**Standards carry their own sector on 100% of documents** and an occupation on 27,311. Taking the
hierarchy from the qualification side alone stranded **4,784 units** that belong to no current
qualification — they existed in the database but could not be reached by browsing. That gap was
self-inflicted, not inherent to the data.

---

## 5. QP → NOS is three relationships, not one

```
compulsoryNos[]                    flat list           26,944 links
electiveNos[]  { name, optionalDesc, nos: [...] }      grouped
optionalNos[]  { name, optionalDesc, nos: [...] }      grouped
```

Elective and optional units are nested inside **named bundles**. Flattening them into plain links
turns "choose one of these" into "all of these are required" — a different and false claim. The
group name must survive the import.

The same applies in `modelcurriculum`: reading only `nos.compulsary` found **128** curriculum-to-unit
links; `nos.elective` and `nos.optional` carry another 749, for 877 total.

---

## 6. The content layer — ~893,000 records, and the actual substance

The first migration imported unit **titles** and left the definitions behind. What each standard
actually *says* lives here:

| Content | Records | Present on |
|---|---|---|
| Performance criteria (`pcID`, `pcDescription`, + theory/practical/viva/OJT marks) | **349,874** | 20,079 NOS |
| Knowledge & understanding parameters | **292,762** | 19,081 NOS |
| Generic/soft skill criteria (`Skills[]`, GS1…GSn) | **250,281** | 18,886 NOS |
| Performance-criteria element headings | **55,747** | 20,080 NOS |
| Scope text (`Scope.scopeDescription`) | — | 75.7% of NOS |

A performance criterion is an atomic, assessable statement with its own marks:

```
element: "Help keep the retail environment secure"   (theory 50, practical 50, total 100)
  PC1  take prompt and suitable action to reduce security risks…   theory 7.5  practical 7.5  total 15
  PC2  follow company policy and legal requirements…               theory 10   practical 10   total 20
```

**Why this matters:** matching, gap analysis and embeddings all need this granularity. A title
alone is a label — and some titles are `"OJT"`, `"Project"` or `"10.1. Case Studies"`, which embed
to noise. "You are missing *this specific capability*" cannot be said from titles.

---

## 7. Structural fields the intelligence layer needs

| Field | Coverage | Why it matters |
|---|---|---|
| `alignedTo` — NCO-2015 code, e.g. `NCO-2015/2144.0900` | 3,214 / 4,669 (1,361 distinct) | The national occupational classification. The only role identity stable **across** qualifications, and therefore the backbone of any career-path graph. |
| `minEduQual` | 4,571 / 4,669 | Entry requirement. Half of "can this candidate actually enrol?" |
| `assmtCrt` — per-NOS `weightage`, `totMarks` | ~26,944 links | A **sourced** importance weight (e.g. 70/10/10). Every other importance in the system is hand-authored. |
| `assmtCrt.totMarks` / `minPassPrcnt` | 4,572 / 4,557 | Assessment blueprint. |
| `credits` | 4,495 | Often the literal string `"TBD"` — nullable, never coerce to 0. |
| `bucket`, `certificateName`, `courseType`, `commonNorms`, `eqptDetails` | 60–100% | Delivery mode, certification, equipment norms. |

---

## 8. Lifecycle — no filtering needed

Checked because importing withdrawn standards would be a silent correctness problem. It is not one:

- `nos.Status.statusDesc`: NSQC Approved 25,364 · Available for QP 1,998 · QRC Approved 125 ·
  Standards Approved 51
- `nos.isActive` is `false` on **9** documents out of 27,538
- `qps.status.statusDesc`: NSQC Approved 4,579 · qpForSankalp 62 · QRC Approved 27 · Standards
  Approved 1

There is no meaningful population of dead standards to exclude. Worth re-checking after the next
data load rather than assuming it stays true.

---

## 9. Data quality issues that will affect matching

- **Duplicate concepts.** 4,847 rows share a name with at least one other. `"Employability Skills"`
  is **67 separate units**; `"Developing and sustaining working relationships"` is 39. A candidate
  who claims one matches exactly one of them. **A concept layer above the unit is needed** —
  this is a design decision, not a cleanup task.
- **45 titles are numbered course fragments** — `"10.1. Case Studies"`, `"1.1. Introduction"`,
  `"0JT"`. They carry real NOS codes (`MSU/MEP/CRS…`) and are indistinguishable from real units in
  the schema. Ordering by prominence hides them; it does not fix them.
- **1,050 NOS titles carry trailing whitespace.** Strip before slugging or indexing.
- **Durations are `HH:MM` strings** (`"570:00"`, `"0126:00"`). Parse to integer minutes — the only
  lossless target. `"00:00"` means zero, which is a real answer and must not become null.

---

## 10. Deduplication — ~40% of the text repeats

Matters for translation cost, for embedding cost, and for consistency.

| Layer | Occurrences | Distinct | |
|---|---|---|---|
| NOS titles | 27,538 | 20,718 | 75.2% |
| NOS descriptions | 27,538 | 15,175 | 55.1% |
| Performance criteria | 349,874 | 219,670 | 62.8% |
| Knowledge & understanding | 292,762 | 126,575 | 43.2% |
| Generic skill criteria | 250,281 | 58,998 | 23.6% |

Deduplicating before translating also **guarantees identical English gets identical Hindi**, which
no per-row prompt can promise.

---

## 11. Multilingual — zero Devanagari, and cost is not the obstacle

The corpus is **entirely English**. No Devanagari appears in any document.

Estimated one-off translation cost (Haiku 4.5, input + ~2.2× output tokens):

| Layer | Items | Est. |
|---|---|---|
| Sectors, sub-sectors, QP job roles | ~5,000 | **~$1** |
| NOS titles | 20,718 distinct | **~$4** |
| NOS descriptions | 15,175 distinct | ~$25 |
| Full content layer (PC + K&U + generic) | ~405,000 distinct | ~$140 |
| **Everything, deduplicated** | | **~$170** |

So the *navigable surface* — what people actually search and scan — is about **$5**. The real
constraints are elsewhere:

- **Terminology consistency.** "safety", "supervision", "workplace" must not vary across 21,000
  units. Translate a glossary first and inject it into every prompt.
- **Review status per string.** Unreviewed machine output cannot ship looking like official NSQF
  content. Needs `machine | reviewed | rejected` per string, plus a hash of the English to detect
  that a translation has gone stale.
- **Transliteration is not translation.** `khoon nikalna` resolves today only because of
  hand-authored Latin-script aliases. Devanagari alone will **not** make transliterated search
  work — and transliterated typing is how the target user actually searches. Romanised forms are a
  separate, first-class output.
- **Write translations back to MongoDB** (ADR-034), or the next re-import destroys them.

---

## 12. Open questions for the next migration

- Does the incoming master data (sectors, SSCs, states, districts, awarding bodies) supply a real
  **SSC dimension** and a **geography** dimension? Both are absent or unusable today.
- Is there **NCO-2015 reference data** to go with the 1,361 codes? Today there are codes but no
  names or hierarchy, so an occupation table cannot be built from them without fabricating one.
- Do **awarding bodies** give qualifications a provider dimension? That is currently missing
  entirely, and is what would connect a national qualification to a real training provider.
- How should the **duplicate-concept problem** (67 × "Employability Skills") be modelled — a
  concept layer above units, or deduplication at import?
