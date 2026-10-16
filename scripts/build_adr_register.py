"""Build the ADR register workbook from docs/adr/architecture-decisions.md (Sprint 67).

    .venv/bin/python scripts/build_adr_register.py

The register is an index and an assessment, not a decision: the decisions stay in the ADR file.
It is written with the standard library only (no spreadsheet package is needed), so it can be
rebuilt anywhere. The standing of an ADR comes from its own header and its `Supersedes`/`Extends`
lines; the overrides below (not built, deferred, partly built) come from CLAUDE.md and
projectContextForMe.md and are the one part to re-read when the product changes.
"""

import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from xlsx_min import sheet, write_workbook

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "adr" / "architecture-decisions.md"
OUT = ROOT / "docs" / "adr" / "IISM-ADR-Register.xlsx"
text = SRC.read_text(encoding="utf-8")
blocks = re.split(r"\n(?=## ADR-\d+:)", text)[1:]


def _commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"[*`]", "", s)).strip()


adrs = []
for b in blocks:
    m = re.match(r"## ADR-(\d+): (.*)", b)
    n = int(m.group(1))
    title = m.group(2).strip()
    st = re.search(r"\*\*Status:\*\*(.*?)(?:\n\n|\n\*\*)", b, re.S)
    status = clean(st.group(1)) if st else ""
    dm = re.search(r"\*\*Decision:\*\*(.*?)(?:\n\n\*\*|\n\*\*Options|\Z)", b, re.S)
    decision = clean(dm.group(1)) if dm else ""
    if len(decision) > 420:
        decision = decision[:417].rsplit(" ", 1)[0] + "…"
    date = re.search(r"\((\w+ 20\d\d)\)", status)
    sprint = re.search(r"Sprint (\d+(?:\.\d)?)", status)
    mig = re.search(r"[Mm]igration (\d{4})", status)
    refs = sorted({int(x) for x in re.findall(r"ADR-(\d+)", status)} - {n})
    adrs.append(
        {
            "n": n,
            "id": f"ADR-{n:03d}",
            "title": title,
            "status": status,
            "decision": decision,
            "date": date.group(1) if date else "",
            "sprint": sprint.group(1) if sprint else "",
            "migration": mig.group(1) if mig else "",
            "refs": ", ".join(f"ADR-{r:03d}" for r in refs),
        }
    )
assert len(adrs) >= 77, len(adrs)

SRCBASIS = "ADR header; no later ADR contradicts it (not re-checked against code)"
OV = {
    5: (
        "Planned – not built",
        "Medium",
        "Not built",
        "No LLM call exists anywhere; the intelligence/ module has an ADR and no code. The direction stands: ADR-036 keeps every decision deterministic and lets a model only explain.",
        "",
        "CLAUDE.md ('Not built')",
    ),
    8: (
        "Superseded in part",
        "Medium",
        "Partly built",
        "First slice delivered by ADR-049: ladders are derived at read time from qualification data and nothing is stored. The inference graph this ADR describes is unbuilt (SkillRelation has no edges).",
        "ADR-049",
        "ADR-008 header; CLAUDE.md careers/",
    ),
    11: (
        "Partly built",
        "Medium",
        "Partly built",
        "UUID primary key built. Optional Aadhaar verification is not built and nothing collects Aadhaar data.",
        "",
        "CLAUDE.md; ADR-023",
    ),
    13: (
        "Partly built",
        "Medium",
        "Partly built",
        "pgvector storage and a 384-dimension port are built (ADR-031). The mandated sentence-transformers model is not switched on: HashingEmbeddingProvider is an honest placeholder and BL-5.3 is not started.",
        "",
        "CLAUDE.md adapters/embeddings",
    ),
    15: (
        "Superseded",
        "Low",
        "n/a",
        "Replaced by ADR-024 (taxonomy-first, multi-sector, India-first).",
        "ADR-024",
        "ADR-015 header",
    ),
    18: (
        "Planned – not built",
        "Medium",
        "Not built",
        "No external LLM is integrated. The adapter pattern it depends on exists (ADR-017, ADR-031).",
        "",
        "CLAUDE.md ('Not built')",
    ),
    19: (
        "Superseded in part",
        "Medium",
        "Partly built",
        "Tooling half replaced by ADR-040 (structured JSON logs to stdout). The destination (OpenTelemetry, Prometheus, Grafana) remains deferred and unbuilt.",
        "ADR-040",
        "ADR-040 header",
    ),
    23: (
        "Partly built",
        "High",
        "Partly built",
        "Consent record, DPDP export, erasure, the redaction filter and retention are built. The encryption path for Aadhaar, resumes and assessment results is not, so that data is deliberately not collected.",
        "",
        "CLAUDE.md; ADR-055, ADR-067",
    ),
    25: (
        "Deferred by owner",
        "Medium",
        "Not built",
        "Monetisation (BL-1.3) is a standing not-started: the owner chose to wait for real traffic. ADR-043 and ADR-047 carry the deferral.",
        "",
        "ADR-043, ADR-047; projectContextForMe.md",
    ),
    28: (
        "Deferred by owner",
        "Medium",
        "Not built",
        "Nothing is deployed anywhere; deployment is deferred by the owner and is now on the mobile launch's critical path. Still the intended topology.",
        "",
        "projectContextForMe.md section 0",
    ),
    32: (
        "Superseded in part",
        "Medium",
        "Built",
        "The organisation half (email OTP, password-free) is replaced by ADR-038; the credential-follows-actor rule still governs sign-up.",
        "ADR-038",
        "ADR-038 header",
    ),
    33: (
        "Superseded in part",
        "Medium",
        "Built",
        "The two-language assumption is replaced by ADR-041 (a language is a messages file and rows). Hindi and English remain the launch pair; Malay is hidden from the switcher, not removed.",
        "ADR-041",
        "ADR-041 header",
    ),
    37: (
        "Superseded in part",
        "Medium",
        "Built",
        "The rule that no employer-facing payload identifies a candidate stands and is tested. The 'unauthenticated demonstration' framing no longer describes the product: the authenticated employer console shipped to production in Sprint 12 (ADR-038); only the unauthenticated demo console is local-only.",
        "ADR-038",
        "CLAUDE.md Sprint 11/12 entries",
    ),
    45: (
        "Superseded in part",
        "Low",
        "Partly built",
        "Sections 1-4 (a sibling module for gig work) replaced by ADR-046: a gig is a Job.",
        "ADR-046",
        "ADR-045 header",
    ),
    14: (
        "Active",
        "High",
        "Built",
        "Modular monolith in place; a later split into services has not been needed or done.",
        "",
        "CLAUDE.md",
    ),
}
# later ADRs that explicitly replace a sprint decision rather than an ADR
SPRINT_SUPERSEDES = {
    54: "Replaces the Sprint 23 arrangement where the role-alias dict was the source of truth.",
    65: "Replaces Sprint 20's report-only Content-Security-Policy with an enforced one.",
}
rows = []
for a in adrs:
    n = a["n"]
    if n in OV:
        stg, rel, built, note, by, basis = OV[n]
    else:
        stg, rel, built, note, by, basis = (
            "Active",
            "High",
            "Built",
            "",
            "",
            SRCBASIS
            if n <= 37
            else "ADR header and sprint record in CLAUDE.md / projectContextForMe.md",
        )
        if n >= 38 and (
            "Extends" in a["status"] or "Refines" in a["status"] or "Implements" in a["status"]
        ):
            stg = "Active – extends earlier ADR"
        if n in SPRINT_SUPERSEDES:
            note = SPRINT_SUPERSEDES[n]
            stg = "Active – replaces a sprint decision"
    if n == 46:
        note = "Supersedes ADR-045 sections 1-4."
        stg = "Active – supersedes part of ADR-045"
    if n == 38:
        note = "Supersedes the organisation half of ADR-032."
        stg = "Active – supersedes part of ADR-032"
    if n == 40:
        note = "Supersedes the tooling half of ADR-019."
        stg = "Active – supersedes part of ADR-019"
    if n == 41:
        note = "Supersedes the two-language assumption in ADR-033."
        stg = "Active – supersedes part of ADR-033"
    if n == 24:
        note = "Supersedes ADR-015."
        stg = "Active – supersedes ADR-015"
    if n == 77:
        note = "This sprint (66). Mobile release: fail-closed config, owner items counted, store answers checked against the data export. Not run on a device or EAS build."
    if n in (72, 73, 74, 75, 76):
        note = (
            note
            or "Mobile programme (Sprints 62-65). Compiled, tested and browser-run; never run on a device."
        )
    if n == 78:
        note = "Sprint 67 (M6). Candidate parity on the phone: history sections, why-not-me, careers, budget. Tested and browser-run; not run on a device."
    if n == 79:
        note = "Sprint 69 (BL-16.1). Scannable listings: monthly pay, card v2, server totals, a shared fixture for rules both clients need, 12 px and 44 px floors held by tests."
    a.update(standing=stg, relevance=rel, built=built, note=note, by=by, basis=basis)
    rows.append(a)


def colour(stg):
    if stg.startswith("Active"):
        return "green"
    if stg in ("Partly built",):
        return "amber"
    if stg.startswith("Superseded"):
        return "red"
    return "grey"


counts = Counter(("Active" if r["standing"].startswith("Active") else r["standing"]) for r in rows)
# Sheet: ADR Register
H = [
    "ADR",
    "Title",
    "Date",
    "Sprint",
    "Migration",
    "Standing today",
    "Relevance",
    "Built?",
    "Decision (from the ADR)",
    "Status line as written",
    "Related ADRs",
    "Superseded / carried on by",
    "Assessment note",
    "Basis for the assessment",
]
reg = [H]
regst = [["header"] * len(H)]
for r in rows:
    reg.append(
        [
            r["id"],
            r["title"],
            r["date"],
            r["sprint"],
            r["migration"],
            r["standing"],
            r["relevance"],
            r["built"],
            r["decision"],
            r["status"],
            r["refs"],
            r["by"],
            r["note"],
            r["basis"],
        ]
    )
    c = colour(r["standing"])
    regst.append(
        [
            "bold",
            "normal",
            "normal",
            "normal",
            "normal",
            c,
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
            "normal",
        ]
    )
# Sheet: stale
stale = [["ADR", "Header says", "What is actually true", "Kind", "Suggested one-line header edit"]]


# ADR-019, 032, 033 and 037 once read plain "Accepted" though a later ADR changed their meaning;
# their headers were corrected in Sprint 67, so only the implementation-lag group remains.
def addstale(n, kind, edit):
    r = next(x for x in rows if x["n"] == n)
    stale.append([r["id"] + " " + r["title"], r["status"], r["note"], kind, edit])


for n, edit in [
    (5, "Accepted; not built."),
    (11, "Accepted; Aadhaar verification not built."),
    (13, "Accepted; placeholder embedder in use (BL-5.3)."),
    (18, "Accepted; not built."),
    (23, "Accepted; encryption path unbuilt."),
    (25, "Accepted; deferred by owner."),
    (28, "Accepted; deferred by owner, nothing deployed."),
]:
    addstale(n, "Decision stands; header says nothing of implementation lag", edit)
# Sheet: by sprint
bys = defaultdict(list)
for r in rows:
    if r["sprint"]:
        bys[r["sprint"]].append(r)
sp = [["Sprint", "ADRs", "Decisions", "Migration"]]
for k in sorted(bys, key=lambda s: float(s)):
    sp.append(
        [
            f"Sprint {k}",
            ", ".join(x["id"] for x in bys[k]),
            "; ".join(x["title"] for x in bys[k]),
            ", ".join(sorted({x["migration"] for x in bys[k] if x["migration"]})),
        ]
    )
nosp = [r for r in rows if not r["sprint"]]
# Summary
S = [
    ["Question", "Answer"],
    [
        "Is the original ADR document still relevant?",
        f"Yes. It is the live decision record, not a historical artefact. {counts['Active']} of {len(rows)} ADRs are in force or extended by a later one. It is append-only by design: later ADRs refine, extend or supersede earlier ones, and the file is kept up to date through ADR-{rows[-1]['n']:03d}.",
    ],
    [
        "Is it fully current?",
        f"No. {counts['Superseded'] + counts['Superseded in part']} ADRs are formally superseded (whole or in part), {counts['Partly built']} are only partly built, {counts['Planned – not built']} are not built, {counts['Deferred by owner']} are deferred by the owner. Four headers (ADR-019, 032, 033, 037) that once read plain 'Accepted' although a later ADR or event had changed their meaning now say so (Sprint 67); 'Stale headers' lists the decisions whose header says nothing of how far they are built.",
    ],
    [
        "Does it need replacing?",
        "No. A rewrite would lose the reasoning and the trade-offs, which are the point of an ADR. Keep this register as the shareable index, and regenerate it with scripts/build_adr_register.py when an ADR is added.",
    ],
    [
        "What is this workbook?",
        "A register of all 77 ADRs with each one's standing today, relevance, whether it is built, and what supersedes or extends it. It is an index and an assessment, not a new decision. The decisions themselves stay in docs/adr/architecture-decisions.md.",
    ],
    [
        "How the 'standing' was decided",
        "ADR headers and the 'Supersedes / Extends' lines were read mechanically. ADRs 001-037 that carry no override are marked Active on the strength of the ADR header and the absence of a contradicting later ADR; that is NOT a re-check against the code. The overrides (for example 'not built' or 'deferred') come from CLAUDE.md and projectContextForMe.md.",
    ],
    [
        "Not covered",
        "Sprints that made no architectural decision have no ADR by design. Work not yet run: nothing in the mobile programme (ADR-072 to 077) has run on a device, an EAS build or a store console; nothing is deployed.",
    ],
    [
        "Generated",
        "From docs/adr/architecture-decisions.md at commit "
        + _commit()
        + " by scripts/build_adr_register.py.",
    ],
]
sumst = [["header", "header"]] + [["bold", "normal"] for _ in S[1:]]
cnt = [["Standing today", "ADRs"]] + [
    [k, str(v)] for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
]
S.append(["", ""])
sumst.append(["normal", "normal"])
S += cnt
sumst += [["header", "header"]] + [["normal", "normal"] for _ in cnt[1:]]

sheets = [
    ("Summary", sheet(S, [34, 110], freeze=False, filt=False, styles=sumst)),
    (
        "ADR Register",
        sheet(reg, [9, 38, 12, 8, 10, 24, 10, 12, 60, 48, 18, 16, 60, 34], styles=regst),
    ),
    ("Stale headers", sheet(stale, [40, 40, 70, 34, 60])),
    ("By sprint", sheet(sp, [12, 34, 90, 12])),
]
write_workbook(OUT, sheets)
print(dict(counts))
print(len(rows), "ADRs;", len(stale) - 1, "with implementation lag;", len(sp) - 1, "sprints")
