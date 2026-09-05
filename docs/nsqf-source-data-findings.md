# NSQF source corpus — what the data actually looks like

Findings from auditing `iism_nsqf_master_data` in MongoDB, recorded so a future migration starts
from knowledge rather than rediscovering it. Every number here was measured against the full
collections, not sampled, unless it says otherwise.

The first migration attempt (Sprint 6, since discarded) got several of these wrong. Where that
happened it is said plainly, because the *way* it went wrong is the reusable lesson.

> **Status:** migrated 2026-09-05. Four further collections (`sectors`, `ssc`, `state`,
> `district`) arrived after the first attempt was rolled back, and §13–§16 below record what
> they contain. Everything here was measured against complete collections, not sampled.

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
- **Sector Skill Council:** `originSSC` appears on only **427 of 4,669** qualifications and is
  useless. **The `sectors` master supersedes it entirely — see §13.**

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


---

## 13. The `sectors` master — two populations in one collection

111 documents, and they are not all sectors:

| | Count | What it is |
|---|---|---|
| Rows carrying sub-sectors and occupations | **43** | Real skilling sectors |
| Rows typed `Awarding Body` | **68** | Organisations, not sectors |
| Distinct `sectorCode` (== `sscCode`) | **106** | Every owning body |

**`sectorCode` is the qualification code prefix**, and this is the single most useful fact in the
new data. `LSC` owns `LSC/Q6101` and `LSC/N2131`. It resolves:

- **4,529 of 4,576 qualifications (99.0%)**
- **27,495 of 27,523 standards (99.9%)**

Against `originSSC`'s 9%, that is the difference between having an ownership dimension and not.
Listing the 68 awarding bodies as sectors would put "Medhavi Foundation" in a sector filter, so
they go to `awarding_bodies` and only the 43 become sectors.

**Occupations: 1,811, every one coded — but both the code and the id are sector-local.**
`occupationCode` is two digits (`01`, `99`) and `occupationID` reuses `"1"`, `"2"`, `"3"` across
forty-odd sectors. Keying on either alone collapses 1,811 occupations into **529**. The key is
`(sector, ref)`. They are *not* NCO codes; the overlap with NCO is four values and coincidental.

Sub-sectors: 801, all with ids.

## 14. The `ssc` collection — excluded entirely

4,053 documents, and it is a **portal account registry**, not a Sector Skill Council master:

- 4,027 email addresses, 4,042 mobile numbers, 2,129 personal names
- 50 bank account numbers with IFSC codes and account-holder names
- 3,547 of 4,053 still at `status='init'` — incomplete registrations
- only 110 carry a `qpPrefix`, reaching 1,840 qualifications

The `sectors` collection supplies the same organisations with real names, no personal or financial
data, and four times the coverage. Importing `ssc` would mean holding DPDP-regulated personal data
and bank details that the product does not use and has no consent for. **It is not imported, and
nothing in `api/` reads it.**

## 15. Geography — clean, with one structural surprise

36 states and 767 districts, all `status='active'`, all uniquely coded; 7,138 sub-districts.

**The `district` collection carries no state reference at all.** A district is tied to a state only
by the array embedded in each state document, and the policy flags live only on that embedded
copy. So the embedded array is the authority for the hierarchy, and the standalone collection
contributes sub-districts alone. Two district documents appear in no state's list and are reported
rather than imported.

The policy flags are worth keeping — they are the axes government skilling schemes target:

| Flag | Districts |
|---|---|
| North-east | 128 |
| Border | 110 |
| Aspirational | 104 |
| Tribal | 66 |
| Left-wing extremism affected | 39 |

Free text resolves well: all four seeded states and five of six districts match exactly.
`Bengaluru` is `BENGALURU URBAN` in the master — handled by an alias, not by changing the seed,
because "Bengaluru" is what an employer would actually write.

## 16. `minEduQual` is structured, and `alignedTo` is dirty

**`minEduQual` is an array, never a string.** An earlier pass counted non-empty arrays and called
them text values. It holds **14,877 alternative entry routes across 4,564 qualifications**, each
pairing an education requirement with an experience requirement — "12th grade Pass with no
experience" *or* "10th grade pass with 3 years" — and a candidate needs to satisfy only one.
Experience is stated as "3 Years", "1.5 years", "6 Months" or "NA"; `NA` must stay null, because
"no experience required" and "not stated" would score differently.

**`alignedTo` is a mess and must be treated as one.** Of 3,214 values:

| | Count | |
|---|---|---|
| Well-formed `NCO-2015/dddd.dddd` | 1,914 | |
| Variant formats | 507 | unicode hyphen `‐`, `NCO 2015- ` spacing, comma-separated multiples |
| Free text | 793 | `(CNC Operator)` — a job role, not a code |

Parsing yields 2,541 codes across 2,419 qualifications, 929 distinct. The free-text values are
counted and discarded, because storing a job role as an occupation classification is worse than
storing nothing.

## 17. What the migration actually produced (2026-09-05)

```
states 36 | districts 766 | sub_districts 7,100
awarding bodies 106 (43 SSC + 63 AB) | sectors 43 | sub_sectors 796 | occupations 1,808
skills 21,303 | qualification_packs 4,424 | qp_skills 27,278 | model_curricula 1,950
entry_routes 14,405 | nco_codes 2,541 | qp_skills with weightage 25,522
performance elements 38,340 | criteria 238,370 | knowledge 185,559 | generic 151,840
```

Ownership resolves for **97.2% of qualifications** and **99.8% of standards**. `nos_type` went
from 1,685 populated to 17,992 by reading the embedded copy as well as the standalone field.

**Content is thinner than the corpus-wide totals suggest, and this is real rather than a bug.**
Only the current version of each code contributes content, and **7,459 of 21,263 current standards
carry no performance criteria at all** in their latest version. The import writes every content row
that the current versions hold — verified by computing the ceiling independently and matching it
exactly.

## 18. Still open

- The **duplicate-concept problem** is untouched: 4,847 rows share a name, and "Employability
  Skills" is 67 separate units. Matching will suffer until there is a concept layer above the unit.
- **No Hindi.** The corpus is English-only and the translation pipeline is not built.
- **The national taxonomy connects to nothing**: zero `job_skills`, `course_skills`,
  `candidate_skills` or aliases point at an imported row.
- **NCO reference data is still absent** — codes but no names or hierarchy, so an occupation
  hierarchy cannot be built from them without inventing one.
