"""Bulk upload of vacancies and courses (Sprint 51, BL-14, ADR-063).

A vacancy is a 12-field form plus a standards list where each standard is a search, a pick and an
Add click -- 35 to 45 interactions, so thirty vacancies is a thousand. A staffing agency or a
multi-centre training partner (the actors `CLAUDE.md` says the product deliberately lets own many
organisations) has dozens. This lets them upload a spreadsheet.

**It goes through the existing writers, never beside them** (ADR-026): every row is validated by
`JobIn` / `CourseIn` and created by `publishing.create_job` / `course_publishing.create_course`,
which force `draft`, resolve geography, pick the slug and write the standards. This module is
parsing, the per-row report, and the rules a *batch* needs that one record never does.

**Two phases, and the second never trusts the first.** `check` validates every row and writes
nothing; `apply` runs the same validation again and then creates each valid row as a **draft**. A
row that fails never blocks one that passes (the `bulk_enrol_candidates.py` precedent, not
`/me/profile/skills/bulk`'s all-or-nothing), and the failed rows come back as a CSV of the original
rows plus an `error` column, so the loop is: upload, fix the twelve, upload the whole file again.

**That loop makes idempotency essential.** An optional `external_ref` is the organisation's own id
for the row and is unique per organisation (migration 0048); a row whose reference exists is
*skipped*, never duplicated and never silently updated. Without one, a row matching an existing
listing of the same organisation on normalised title (+ district + employment type for a vacancy)
is skipped and names which one it matched.

**A standard is named by NOS code**, which is globally unique across all 21,303 (`Skill.nos_code`),
never by name: 1,778 names are shared by 4,838 standards. A row may instead name a **job role**,
which expands to the qualification's *compulsory* standards -- resolved by exact title or alias
only, never fuzzy (a guess about a role is a claim about somebody else; the careers rule), with
mandatory defaulting to **no** because every compulsory unit being mandatory would cap every
candidate missing one at 45 (ADR-036). The check lists every expanded standard by code and name, so
nobody applies a mapping they have not seen.

**Caps.** Rows per file, and rows an organisation may create in a rolling 24 hours -- lower until an
operator has verified it, counted over every way a listing is made. Drafts are invisible, so this
bounds clutter and abuse of the write path; a separate publish step is what makes anything public.
"""

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

import structlog
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.modules.geography import resolve_location
from api.modules.marketplace import course_publishing, publishing
from api.modules.marketplace.models import (
    COURSE_LANGUAGES,
    COURSE_MODES,
    EMPLOYMENT_TYPES,
    Course,
    Job,
)
from api.modules.marketplace.schemas import CourseIn, CourseSkillIn, JobIn, JobSkillIn
from api.modules.skills import Skill, search_roles, standards_for_role

log = structlog.get_logger("iism.marketplace")

Kind = Literal["jobs", "courses"]
Status = Literal["ok", "warning", "error", "skip"]

# JobIn / CourseIn both cap a listing at 50 standards.
MAX_STANDARDS = 50
# What a role's expanded standard is worth when the row does not say: the flat value the careers
# engine gives a compulsory unit (`score_against_roles`).
ROLE_IMPORTANCE = 3

IST = timezone(timedelta(hours=5, minutes=30))

# The columns, in the order the template shows them. The single source of truth: the API serves
# the template, so the web app never carries a second copy of this list.
JOB_COLUMNS = (
    "external_ref",
    "title",
    "description",
    "state",
    "district",
    "employment_type",
    "positions",
    "experience_min_years",
    "experience_max_years",
    "salary_min_inr",
    "salary_max_inr",
    "nsqf_level_min",
    "closes_at",
    "standards",
    "job_role",
    "role_standards_mandatory",
)
COURSE_COLUMNS = (
    "external_ref",
    "title",
    "description",
    "mode",
    "language",
    "duration_hours",
    "fee_inr",
    "nsqf_level",
    "standards",
    "job_role",
)
COLUMNS: dict[str, tuple[str, ...]] = {"jobs": JOB_COLUMNS, "courses": COURSE_COLUMNS}
REQUIRED = {"title"}

# Two example rows, one naming standards by code and one naming a role, so the template teaches
# both. The codes are real national standards; the role is a real job role.
_TEMPLATE_ROWS: dict[str, tuple[tuple[str, ...], ...]] = {
    "jobs": (
        (
            "WARD-001",
            "Ward attendant",
            "Day shift at a 120-bed hospital.",
            "Tamil Nadu",
            "Chennai",
            "full_time",
            "2",
            "0",
            "3",
            "15000",
            "20000",
            "3",
            "2026-12-31",
            "HSS/N6012:4:M; HSS/N6002:3",
            "",
            "",
        ),
        (
            "WARD-002",
            "General duty assistant",
            "",
            "Maharashtra",
            "Pune",
            "full_time",
            "1",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "General Duty Assistant",
            "no",
        ),
    ),
    "courses": (
        (
            "GDA-01",
            "General duty assistant training",
            "Eight weeks, with a hospital placement.",
            "offline",
            "both",
            "320",
            "12000",
            "4",
            "HSS/N6012:4; HSS/N6002:3",
            "",
        ),
        ("GDA-02", "Home health aide", "", "hybrid", "hi", "240", "", "", "", "Home Health Aide"),
    ),
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# An Indian mobile number as people write it: ten digits, often split 5 + 5.
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
_YES = {"yes", "y", "true", "1", "m", "mandatory"}
_NO = {"no", "n", "false", "0", ""}


class BulkFileError(Exception):
    """The file as a whole cannot be read: nothing about any one row."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class StandardRef:
    """One standard a row will require (or teach), and where it came from."""

    code: str
    name: str
    slug: str
    source: str  # the corpus source: "nsqf", or "legacy" (refused)
    level: float | None
    origin: Literal["listed", "role"] = "listed"
    importance: int = 3
    mandatory: bool = False


@dataclass
class RowReport:
    row: int
    status: Status
    title: str | None = None
    external_ref: str | None = None
    messages: list[str] = field(default_factory=list)
    standards: list[StandardRef] = field(default_factory=list)
    # The slug created (apply) or the one this row matched (a skip).
    slug: str | None = None
    created: bool = False


@dataclass
class BulkReport:
    kind: Kind
    rows: list[RowReport]
    notes: list[str]
    daily_limit: int
    remaining_today: int
    applied: bool
    errors_csv: str | None = None

    def count(self, status: Status) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def created(self) -> int:
        return sum(1 for r in self.rows if r.created)


# --------------------------------------------------------------------------------------- parsing


@dataclass(frozen=True)
class RawRow:
    number: int  # the spreadsheet row: the header is 1, the first data row 2
    cells: dict[str, str]
    extra_cells: int = 0


def _normal_header(name: str) -> str:
    return "_".join(name.strip().lower().replace("-", " ").split())


def parse_file(text: str, kind: Kind) -> tuple[list[RawRow], list[str], list[str]]:
    """`(rows, notes, header)` -- or `BulkFileError` for a file nothing can be done with.

    A BOM is tolerated (Excel's "CSV UTF-8" writes one), CRLF and a quoted newline inside a cell
    are the csv module's job, and a blank record is skipped. Row numbers are **records**, not lines,
    so they match the number the person sees in their spreadsheet even with a multi-line cell.
    """
    settings = get_settings()
    text = text.lstrip("﻿")
    if not text.strip():
        raise BulkFileError("The file is empty.")

    try:
        records = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as error:
        raise BulkFileError(f"The file is not a readable CSV: {error}") from error
    if not records:
        raise BulkFileError("The file is empty.")

    header = [_normal_header(h) for h in records[0]]
    allowed = set(COLUMNS[kind])
    duplicated = sorted({h for h in header if h and header.count(h) > 1})
    if duplicated:
        raise BulkFileError(f"The column {', '.join(duplicated)} appears more than once.")
    missing = sorted(REQUIRED - set(header))
    if missing:
        raise BulkFileError(
            f"The header row must include: {', '.join(missing)}. "
            f"Download the template for the expected columns."
        )
    notes = [
        f"The column '{h}' is not recognised and was ignored."
        for h in header
        if h and h not in allowed
    ]

    rows: list[RawRow] = []
    for index, record in enumerate(records[1:], start=2):
        if not any(cell.strip() for cell in record):
            continue
        cells = {
            h: (record[i].strip() if i < len(record) else "") for i, h in enumerate(header) if h
        }
        rows.append(RawRow(index, cells, extra_cells=max(0, len(record) - len(header))))
    if not rows:
        raise BulkFileError("The file has a header and no rows.")
    if len(rows) > settings.bulk_max_rows:
        raise BulkFileError(
            f"At most {settings.bulk_max_rows} rows per file; this has {len(rows)}. "
            "Split it into smaller files.",
            status_code=413,
        )
    return rows, notes, header


def decode(body: bytes) -> str:
    """The body as text: UTF-8, a BOM tolerated. Anything else is the file's fault, not a 500."""
    try:
        return body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise BulkFileError(
            "The file is not UTF-8. In Excel, save it as 'CSV UTF-8 (Comma delimited)'."
        ) from error


def template_csv(kind: Kind) -> str:
    """The header and two example rows. Served by the API so there is one list of columns."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS[kind])
    for row in _TEMPLATE_ROWS[kind]:
        writer.writerow(row)
    return out.getvalue()


def errors_csv(header: Sequence[str], rows: Sequence[RawRow], failed: dict[int, str]) -> str | None:
    """The rows that failed, exactly as uploaded, plus an `error` column."""
    if not failed:
        return None
    columns = [h for h in header if h]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([*columns, "error"])
    for row in rows:
        if row.number in failed:
            writer.writerow([*(row.cells.get(c, "") for c in columns), failed[row.number]])
    return out.getvalue()


# ------------------------------------------------------------------------------------ small rules


def _norm(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _clean_error(error: Any) -> str:
    message = str(error.get("msg", "invalid"))
    return message.removeprefix("Value error, ").removeprefix("Value error: ")


_FIELD_COLUMN = {"location_state": "state", "location_district": "district"}


def _validation_messages(error: ValidationError) -> list[str]:
    out = []
    for e in error.errors():
        loc = str(e["loc"][0]) if e.get("loc") else ""
        column = _FIELD_COLUMN.get(loc, loc)
        out.append(f"{column}: {_clean_error(e)}" if column else _clean_error(e))
    return out


def _int(cells: dict[str, str], column: str, problems: list[str]) -> int | None:
    raw = cells.get(column, "").replace(",", "")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        problems.append(f"{column}: '{cells[column]}' is not a number")
        return None
    if value != int(value):
        problems.append(f"{column}: '{cells[column]}' must be a whole number")
        return None
    return int(value)


def _float(cells: dict[str, str], column: str, problems: list[str]) -> float | None:
    raw = cells.get(column, "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        problems.append(f"{column}: '{raw}' is not a number")
        return None


def _closes_at(cells: dict[str, str], problems: list[str]) -> datetime | None:
    """A date means the end of that day in India; a full timestamp is taken as written."""
    raw = cells.get("closes_at", "")
    if not raw:
        return None
    try:
        if len(raw) <= 10:
            day = date.fromisoformat(raw)
            return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=IST)
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        problems.append(f"closes_at: '{raw}' is not a date (use YYYY-MM-DD)")
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=IST)


def _yes_no(cells: dict[str, str], column: str, problems: list[str]) -> bool:
    raw = cells.get(column, "").strip().lower()
    if raw in _YES:
        return True
    if raw in _NO:
        return False
    problems.append(f"{column}: '{cells[column]}' should be yes or no")
    return False


def _choice(
    cells: dict[str, str], column: str, allowed: Sequence[str], default: str, problems: list[str]
) -> str:
    raw = cells.get(column, "")
    if not raw:
        return default
    value = "_".join(raw.lower().split())
    if value not in allowed:
        problems.append(f"{column}: '{raw}' is not one of {', '.join(allowed)}")
        return default
    return value


def _contact_warning(text: str | None) -> str | None:
    if text and (_EMAIL.search(text) or _PHONE.search(text)):
        return (
            "the description looks like it contains a phone number or email address; "
            "descriptions are public once published"
        )
    return None


# ------------------------------------------------------------------------------------- standards


async def _lookup_codes(db: AsyncSession, codes: set[str]) -> dict[str, StandardRef]:
    """NOS codes to standards, one query. Keyed by the upper-cased code.

    The unique index is on the code as stored, so the query asks for the code as typed and in
    upper case; a code in the wrong case still resolves and never costs a table scan.
    """
    if not codes:
        return {}
    wanted = {c for code in codes for c in (code, code.upper())}
    rows = await db.execute(
        select(Skill.nos_code, Skill.name, Skill.slug, Skill.source, Skill.nsqf_level).where(
            Skill.nos_code.in_(wanted)
        )
    )
    return {
        code.upper(): StandardRef(
            code=code,
            name=name,
            slug=slug,
            source=source,
            level=float(level) if level is not None else None,
        )
        for code, name, slug, source, level in rows.all()
        if code
    }


def _split_standards(cell: str) -> list[str]:
    return [t.strip() for t in cell.replace("\n", ";").split(";") if t.strip()]


@dataclass(frozen=True)
class _Token:
    code: str
    importance: int
    mandatory: bool
    level: float | None


def _parse_tokens(kind: Kind, cell: str, problems: list[str]) -> list[_Token]:
    """`CODE[:importance[:M]]` for a vacancy, `CODE[:level]` for a course."""
    tokens: list[_Token] = []
    for raw in _split_standards(cell):
        parts = [p.strip() for p in raw.split(":")]
        code = parts[0]
        if not code:
            problems.append(f"standards: '{raw}' has no code")
            continue
        importance, mandatory, level = 3, False, None
        if kind == "jobs":
            if len(parts) > 3:
                problems.append(f"standards: '{raw}' has too many parts (CODE:importance:M)")
                continue
            if len(parts) >= 2 and parts[1]:
                if not parts[1].isdigit() or not 1 <= int(parts[1]) <= 5:
                    problems.append(
                        f"standards: importance for {code} must be 1 to 5, not '{parts[1]}'"
                    )
                    continue
                importance = int(parts[1])
            if len(parts) == 3:
                if parts[2].upper() not in {"M", "MANDATORY"}:
                    problems.append(
                        f"standards: the third part for {code} must be M, not '{parts[2]}'"
                    )
                    continue
                mandatory = True
        else:
            if len(parts) > 2:
                problems.append(f"standards: '{raw}' has too many parts (CODE:level)")
                continue
            if len(parts) == 2 and parts[1]:
                try:
                    level = float(parts[1])
                except ValueError:
                    problems.append(
                        f"standards: level for {code} must be a number, not '{parts[1]}'"
                    )
                    continue
                if not 1 <= level <= 10 or (level * 2) % 1:
                    problems.append(f"standards: level for {code} must be 1 to 10 in steps of 0.5")
                    continue
        tokens.append(_Token(code, importance, mandatory, level))
    return tokens


@dataclass(frozen=True)
class _Role:
    title: str
    qp_code: str
    standards: tuple[StandardRef, ...]
    error: str | None = None
    warning: str | None = None


async def _resolve_role(db: AsyncSession, text: str) -> _Role:
    """A job role to its qualification's compulsory standards, or an honest "no".

    **Exact title or alias only.** Free text becomes a role through the same search everybody
    else uses, and a hit is trusted only when it is the person's own words (the careers rule,
    `careers.service._guess_anchor`): a prefix or a fuzzy match is a guess about a guess, and every
    vacancy built from the wrong role is about somebody else. The nearest titles are offered in
    the message and **never applied**.
    """
    wanted = _norm(text)
    hits = await search_roles(db, text, limit=5)
    trusted = [
        h
        for h in hits
        if (h.match_kind == "exact" and _norm(h.job_role) == wanted)
        or (h.match_kind == "alias" and _norm(h.matched_on) == wanted)
    ]
    if not trusted:
        hints = [h.job_role for h in hits[:3]]
        hint = f" Did you mean: {'; '.join(hints)}?" if hints else ""
        return _Role(text, "", (), error=f"job_role: no role is titled '{text}'.{hint}")
    slugs = {h.slug for h in trusted}
    if len(slugs) > 1:
        names = "; ".join(sorted({h.job_role for h in trusted}))
        return _Role(
            text, "", (), error=f"job_role: '{text}' matches more than one role ({names})."
        )

    hit = trusted[0]
    role = await standards_for_role(db, hit.slug)
    if role is None:
        return _Role(text, "", (), error=f"job_role: '{text}' could not be read.")
    compulsory = tuple(
        StandardRef(
            code=s.skill.nos_code or "",
            name=s.skill.name,
            slug=s.skill.slug,
            source=s.skill.source,
            level=float(s.skill.nsqf_level) if s.skill.nsqf_level is not None else None,
            origin="role",
        )
        for s in role.standards
        if s.requirement == "compulsory" and s.skill.nos_code
    )
    if not compulsory:
        return _Role(
            text, hit.qp_code, (), error=f"job_role: '{hit.job_role}' has no compulsory standards."
        )
    warning = None
    if hit.qp_code.startswith("PWD/"):
        warning = (
            f"job_role: '{hit.job_role}' exists only as a disability-track qualification, so its "
            "standards are specific to that track"
        )
    return _Role(hit.job_role, hit.qp_code, compulsory, warning=warning)


# --------------------------------------------------------------------------------------- planning


@dataclass
class _Plan:
    """One row, understood. Either a payload ready for the writer, or the reasons it is not."""

    raw: RawRow
    ref: str | None
    title: str | None
    payload: JobIn | CourseIn | None = None
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    standards: list[StandardRef] = field(default_factory=list)
    skip_of: str | None = None
    skip_slug: str | None = None
    key: tuple[str, ...] | None = None


async def _standards_for_row(
    db: AsyncSession,
    kind: Kind,
    cells: dict[str, str],
    codes: dict[str, StandardRef],
    roles: dict[str, _Role],
    plan: _Plan,
    *,
    role_mandatory: bool,
) -> list[StandardRef]:
    """The row's standards: the listed ones, then the role's, the listed ones winning."""
    problems = plan.problems
    listed: list[StandardRef] = []
    for token in _parse_tokens(kind, cells.get("standards", ""), problems):
        found = codes.get(token.code.upper())
        if found is None:
            problems.append(f"standards: no standard has the code {token.code}")
            continue
        if found.source == "legacy":
            problems.append(f"standards: {token.code} is a retired standard")
            continue
        listed.append(
            StandardRef(
                code=found.code,
                name=found.name,
                slug=found.slug,
                source=found.source,
                level=token.level if kind == "courses" and token.level is not None else found.level,
                origin="listed",
                importance=token.importance,
                mandatory=token.mandatory,
            )
        )

    expanded: list[StandardRef] = []
    role_text = cells.get("job_role", "")
    if role_text:
        role = roles[_norm(role_text)]
        if role.error:
            problems.append(role.error)
        else:
            if role.warning:
                plan.warnings.append(role.warning)
            for s in role.standards:
                expanded.append(
                    StandardRef(
                        code=s.code,
                        name=s.name,
                        slug=s.slug,
                        source=s.source,
                        level=s.level,
                        origin="role",
                        importance=ROLE_IMPORTANCE,
                        mandatory=role_mandatory,
                    )
                )

    merged: dict[str, StandardRef] = {}
    for ref in [*expanded, *listed]:  # listed last, so an explicit choice replaces the expansion
        merged[ref.code.upper()] = ref
    standards = list(merged.values())
    if len(standards) > MAX_STANDARDS:
        problems.append(
            f"standards: {len(standards)} standards is more than the {MAX_STANDARDS} a listing may "
            "carry; list the ones that matter instead of the whole role"
        )
    return standards


async def _plan_job(
    db: AsyncSession,
    raw: RawRow,
    codes: dict[str, StandardRef],
    roles: dict[str, _Role],
    places: dict[tuple[str, str], Any],
) -> _Plan:
    cells = raw.cells
    plan = _Plan(raw, cells.get("external_ref") or None, cells.get("title") or None)
    problems = plan.problems
    if raw.extra_cells:
        problems.append(
            f"the row has {raw.extra_cells} more cell(s) than the header: a comma inside a text "
            "value needs the whole value in double quotes"
        )

    fields: dict[str, Any] = {"title": cells.get("title", "")}
    if cells.get("description"):
        fields["description"] = cells["description"]
    if cells.get("state"):
        fields["location_state"] = cells["state"]
    if cells.get("district"):
        fields["location_district"] = cells["district"]
    fields["employment_type"] = _choice(
        cells, "employment_type", EMPLOYMENT_TYPES, "full_time", problems
    )
    for column, target in (
        ("positions", "positions"),
        ("experience_min_years", "experience_min_years"),
        ("experience_max_years", "experience_max_years"),
        ("salary_min_inr", "salary_min_inr"),
        ("salary_max_inr", "salary_max_inr"),
    ):
        value = _int(cells, column, problems)
        if value is not None:
            fields[target] = value
    level = _float(cells, "nsqf_level_min", problems)
    if level is not None:
        fields["nsqf_level_min"] = level
    closes = _closes_at(cells, problems)
    if closes is not None:
        fields["closes_at"] = closes
    role_mandatory = _yes_no(cells, "role_standards_mandatory", problems)

    try:
        JobIn.model_validate(fields)
    except ValidationError as error:
        problems.extend(_validation_messages(error))

    plan.standards = await _standards_for_row(
        db, "jobs", cells, codes, roles, plan, role_mandatory=role_mandatory
    )

    state, district = cells.get("state", ""), cells.get("district", "")
    if state or district:
        place = places[(state, district)]
        if district and place.district_id is None:
            message = (
                f"district '{district}' was not recognised, so the vacancy would be saved with the "
                "place as typed and could not be matched by location"
            )
            (problems if fields["employment_type"] == "gig" else plan.warnings).append(message)
    elif fields["employment_type"] == "gig":
        problems.append("district: a gig needs a place a worker can travel to")

    if not plan.standards and not problems:
        plan.warnings.append(
            "no standards: it can be saved as a draft but cannot be published until it requires one"
        )
    contact = _contact_warning(cells.get("description"))
    if contact:
        plan.warnings.append(contact)

    if not problems:
        try:
            plan.payload = JobIn.model_validate(
                {
                    **fields,
                    "skills": [
                        JobSkillIn(
                            skill_slug=s.slug, importance=s.importance, is_mandatory=s.mandatory
                        )
                        for s in plan.standards
                    ],
                }
            )
        except ValidationError as error:  # the 50-standard cap, after merging
            problems.extend(_validation_messages(error))
    plan.key = (
        _norm(cells.get("title")),
        _norm(cells.get("district")),
        fields["employment_type"],
    )
    return plan


async def _plan_course(
    db: AsyncSession,
    raw: RawRow,
    codes: dict[str, StandardRef],
    roles: dict[str, _Role],
) -> _Plan:
    cells = raw.cells
    plan = _Plan(raw, cells.get("external_ref") or None, cells.get("title") or None)
    problems = plan.problems
    if raw.extra_cells:
        problems.append(
            f"the row has {raw.extra_cells} more cell(s) than the header: a comma inside a text "
            "value needs the whole value in double quotes"
        )

    fields: dict[str, Any] = {"title": cells.get("title", "")}
    if cells.get("description"):
        fields["description"] = cells["description"]
    fields["mode"] = _choice(cells, "mode", COURSE_MODES, "offline", problems)
    fields["language"] = _choice(cells, "language", COURSE_LANGUAGES, "both", problems)
    for column in ("duration_hours", "fee_inr"):
        value = _int(cells, column, problems)
        if value is not None:
            fields[column] = value
    level = _float(cells, "nsqf_level", problems)
    if level is not None:
        fields["nsqf_level"] = level

    try:
        CourseIn.model_validate(fields)
    except ValidationError as error:
        problems.extend(_validation_messages(error))

    plan.standards = await _standards_for_row(
        db, "courses", cells, codes, roles, plan, role_mandatory=False
    )
    if not plan.standards and not problems:
        plan.warnings.append(
            "no standards: it can be saved as a draft but cannot be published until it teaches one"
        )
    contact = _contact_warning(cells.get("description"))
    if contact:
        plan.warnings.append(contact)

    if not problems:
        try:
            plan.payload = CourseIn.model_validate(
                {
                    **fields,
                    "skills": [
                        CourseSkillIn(skill_slug=s.slug, level_taught=s.level)
                        for s in plan.standards
                    ],
                }
            )
        except ValidationError as error:
            problems.extend(_validation_messages(error))
    plan.key = (_norm(cells.get("title")),)
    return plan


# ------------------------------------------------------------------------ idempotency and limits


async def _existing(
    db: AsyncSession, kind: Kind, tenant_id: Any
) -> tuple[dict[str, str], dict[tuple[str, ...], str]]:
    """What this organisation already has: `external_ref -> slug` and `match key -> slug`."""
    by_ref: dict[str, str] = {}
    by_key: dict[tuple[str, ...], str] = {}
    if kind == "jobs":
        rows = await db.execute(
            select(
                Job.slug, Job.title, Job.location_district, Job.employment_type, Job.external_ref
            ).where(Job.tenant_id == tenant_id)
        )
        for slug, title, district, employment, ref in rows.all():
            if ref:
                by_ref[ref] = slug
            by_key.setdefault((_norm(title), _norm(district), employment), slug)
    else:
        rows = await db.execute(
            select(Course.slug, Course.title, Course.external_ref).where(
                Course.tenant_id == tenant_id
            )
        )
        for slug, title, ref in rows.all():
            if ref:
                by_ref[ref] = slug
            by_key.setdefault((_norm(title),), slug)
    return by_ref, by_key


async def _created_in_last_day(db: AsyncSession, kind: Kind, tenant_id: Any) -> int:
    model = Job if kind == "jobs" else Course
    return (
        await db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.tenant_id == tenant_id, model.created_at >= func.now() - timedelta(days=1))
        )
    ) or 0


def daily_limit(tenant: Any) -> int:
    """Rows an organisation may create in a rolling 24 hours; more once an operator verified it."""
    settings = get_settings()
    return (
        settings.bulk_rows_per_day_verified
        if getattr(tenant, "verified_at", None) is not None
        else settings.bulk_rows_per_day_unverified
    )


# ------------------------------------------------------------------------------------------ run


async def _plans(db: AsyncSession, kind: Kind, tenant_id: Any, rows: list[RawRow]) -> list[_Plan]:
    codes_needed: set[str] = set()
    for row in rows:
        for token in _parse_tokens(kind, row.cells.get("standards", ""), []):
            codes_needed.add(token.code)
    codes = await _lookup_codes(db, codes_needed)

    roles: dict[str, _Role] = {}
    for row in rows:
        text = row.cells.get("job_role", "")
        if text and _norm(text) not in roles:
            roles[_norm(text)] = await _resolve_role(db, text)

    places: dict[tuple[str, str], Any] = {}
    if kind == "jobs":
        for row in rows:
            pair = (row.cells.get("state", ""), row.cells.get("district", ""))
            if (pair[0] or pair[1]) and pair not in places:
                places[pair] = await resolve_location(db, pair[0] or None, pair[1] or None)

    plans = [
        await (
            _plan_job(db, r, codes, roles, places)
            if kind == "jobs"
            else _plan_course(db, r, codes, roles)
        )
        for r in rows
    ]

    by_ref, by_key = await _existing(db, kind, tenant_id)
    seen_refs: dict[str, int] = {}
    seen_keys: dict[tuple[str, ...], int] = {}
    for plan in plans:
        if plan.problems:
            continue
        if plan.ref:
            if plan.ref in by_ref:
                plan.skip_of, plan.skip_slug = (
                    f"external_ref {plan.ref} already exists",
                    by_ref[plan.ref],
                )
            elif plan.ref in seen_refs:
                plan.skip_of = (
                    f"external_ref {plan.ref} is repeated; row {seen_refs[plan.ref]} has it"
                )
            seen_refs.setdefault(plan.ref, plan.raw.number)
        elif plan.key and plan.key[0]:
            if plan.key in by_key:
                plan.skip_of, plan.skip_slug = (
                    "you already have one with this title",
                    by_key[plan.key],
                )
            elif plan.key in seen_keys:
                plan.skip_of = f"the same title appears in row {seen_keys[plan.key]}"
            seen_keys.setdefault(plan.key, plan.raw.number)
    return plans


def _report_row(plan: _Plan) -> RowReport:
    if plan.problems:
        return RowReport(
            plan.raw.number,
            "error",
            plan.title,
            plan.ref,
            [*plan.problems, *plan.warnings],
            plan.standards,
        )
    if plan.skip_of:
        message = f"skipped: {plan.skip_of}" + (f" ({plan.skip_slug})" if plan.skip_slug else "")
        return RowReport(
            plan.raw.number, "skip", plan.title, plan.ref, [message], plan.standards, plan.skip_slug
        )
    status: Status = "warning" if plan.warnings else "ok"
    return RowReport(
        plan.raw.number, status, plan.title, plan.ref, list(plan.warnings), plan.standards
    )


async def run(
    db: AsyncSession,
    kind: Kind,
    tenant: Any,
    text: str,
    *,
    apply: bool,
    actor_id: Any = None,
) -> BulkReport:
    """Check a file, or check it again and create what is valid as drafts."""
    rows, notes, header = parse_file(text, kind)
    plans = await _plans(db, kind, tenant.id, rows)
    reports = [_report_row(p) for p in plans]

    limit = daily_limit(tenant)
    remaining = max(0, limit - await _created_in_last_day(db, kind, tenant.id))
    # The cap is applied in file order to the rows that would create something, identically in
    # check and apply: the preview must say what the apply will do.
    allowance = remaining
    standing = "verified" if limit == get_settings().bulk_rows_per_day_verified else "unverified"
    for report in reports:
        if report.status in ("ok", "warning"):
            if allowance <= 0:
                report.status = "error"
                report.messages.insert(
                    0,
                    f"daily limit reached: {limit} listings per 24 hours "
                    f"for a {standing} organisation",
                )
            else:
                allowance -= 1

    if apply:
        for plan, report in zip(plans, reports, strict=True):
            if report.status not in ("ok", "warning") or plan.payload is None:
                continue
            created: Job | Course
            try:
                if kind == "jobs":
                    assert isinstance(plan.payload, JobIn)
                    created = await publishing.create_job(
                        db, tenant.id, plan.payload, external_ref=plan.ref
                    )
                else:
                    assert isinstance(plan.payload, CourseIn)
                    created = await course_publishing.create_course(
                        db, tenant.id, plan.payload, external_ref=plan.ref
                    )
            except HTTPException as error:
                # Both writers validate before they write, so a refusal leaves nothing pending.
                report.status = "error"
                report.messages.insert(0, str(error.detail))
            except IntegrityError:
                await db.rollback()
                report.status = "skip"
                report.messages = ["skipped: it was uploaded at the same moment by another request"]
            else:
                report.created = True
                report.slug = created.slug

    failed = {r.row: "; ".join(r.messages) for r in reports if r.status == "error"}
    report_out = BulkReport(
        kind=kind,
        rows=reports,
        notes=notes,
        daily_limit=limit,
        remaining_today=max(0, remaining - sum(1 for r in reports if r.created)),
        applied=apply,
        errors_csv=errors_csv(header, rows, failed),
    )
    if apply:
        await _record(db, kind, tenant.id, actor_id, report_out)
    return report_out


async def _record(
    db: AsyncSession, kind: Kind, tenant_id: Any, actor_id: Any, report: BulkReport
) -> None:
    """Counts only, subjected to the organisation, **after** the business commits (`record()`
    commits, so calling it with work pending would commit that work as a side effect)."""
    from api.modules.analytics import record

    await record(
        db,
        f"{kind}_bulk_uploaded",
        user_id=actor_id,
        subject_type="tenant",
        subject_id=tenant_id,
        payload={
            "rows": len(report.rows),
            "created": report.created,
            "skipped": report.count("skip"),
            "rejected": report.count("error"),
        },
    )
    log.info(
        "marketplace.bulk_uploaded",
        kind=kind,
        rows=len(report.rows),
        created=report.created,
        skipped=report.count("skip"),
        rejected=report.count("error"),
    )


# ---------------------------------------------------------------------------------------- publish


@dataclass(frozen=True)
class PublishResult:
    slug: str
    published: bool
    message: str | None = None


async def publish_many(
    db: AsyncSession, kind: Kind, tenant_id: Any, slugs: Sequence[str]
) -> list[PublishResult]:
    """Publish a batch through the single writer's own rules, one row at a time.

    A row it refuses (no standard, a gig with no place) is reported and does not stop the rest; a
    slug that is not this organisation's is a plain "not found", never a hint it exists elsewhere.
    """
    results: list[PublishResult] = []
    for slug in dict.fromkeys(slugs):
        try:
            if kind == "jobs":
                await publishing.set_published(db, tenant_id, slug, True)
            else:
                await course_publishing.set_published(db, tenant_id, slug, True)
        except HTTPException as error:
            # `set_published` refuses before it writes: nothing is pending to roll back.
            results.append(PublishResult(slug, False, str(error.detail)))
        else:
            results.append(PublishResult(slug, True))
    return results


__all__ = [
    "COLUMNS",
    "BulkFileError",
    "BulkReport",
    "PublishResult",
    "RowReport",
    "StandardRef",
    "daily_limit",
    "decode",
    "parse_file",
    "publish_many",
    "run",
    "template_csv",
]
