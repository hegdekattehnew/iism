"""An operator enrols a file of people for an agency programme (Sprint 61, BL-14.10, ADR-071).

The government-agency actor has no login (Sprint 33), so an operator stands in for it. This is the
one place the product makes accounts for people who have not touched it, which is why it is
written the way it is:

* **One function decides every row, for the check and for the apply.** `_decide` is called by both,
  and the apply only adds the writes, so a check cannot promise what an apply would not do.
* **It builds a person through `identity.provision_candidate`**, the only place a `User` is ever
  made from nothing, and stamps the current privacy notice against them on the footing of a self
  sign-up. **That stamp is the operator's claim**, so an apply must be *attested* (the notice was
  read out to everyone in the file) and the attestation is a row: who, when, which notice version.
  It does not verify the conversation happened and says so.
* **It never overwrites.** A person who already has an account keeps everything they told us; the
  one thing they gain is the programme tag, and only if they carry none. A number already in a
  programme is skipped, named, and left alone.
* **A row that is wrong costs that row.** Each apply runs in a savepoint, a number that appears
  twice in a file or races in from another request is the unique constraint's problem and reads as
  "already", never a 500, and `db.rollback()` is never called mid-loop (it expires the session).
* **Nothing it reports can be dialled.** A phone is shown masked, a name by its first word, and no
  log line, event or payload carries either. The failed rows come back as the operator's own file
  plus an `error` column, formula-safe.

A sibling of `marketplace.bulk` (ADR-026), not an extension: `bulk.run` is hard-wired to a tenant
and to vacancies and courses. It reuses that module's file reading (`parse_records`, `decode`,
`errors_csv`, `int_cell`) rather than copying it.
"""

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import PRIVACY_NOTICE_VERSION, get_settings
from api.core.redaction import mask_email, mask_phone
from api.modules.analytics import record
from api.modules.geography import PlaceIndex, load_place_index
from api.modules.identity import User, normalise_phone, provision_candidate
from api.modules.marketplace.bulk import (
    BulkFileError,
    RawRow,
    errors_csv,
    int_cell,
    parse_records,
)
from api.modules.marketplace.models import CandidateProfile
from api.modules.operations.models import EnrolmentBatch, EnrolmentBatchMember

log = structlog.get_logger("iism.operations")

COLUMNS = ("phone", "full_name", "headline", "state", "district", "years_experience")
REQUIRED = {"phone"}

# The limits the profile's own write path enforces (`ProfileIn`), so a person enrolled here could
# have been saved by hand.
MAX_NAME = 120
MAX_HEADLINE = 160
MAX_PLACE = 120
MAX_YEARS = 60
MAX_PROGRAMME = 120
# An Indian mobile, in the canonical form `normalise_phone` produces. ASCII digits only: `\d`
# would accept any Unicode digit and `str.isdigit` accepts superscripts.
_MOBILE = re.compile(r"^\+91[6-9][0-9]{9}$")


class _EnrolledMeanwhile(Exception):
    """Another request tagged this existing person after the check read them."""


# What happens, or would happen, to a row. `new` makes an account; `tag` adds the programme to an
# existing person and nothing else; `already` leaves a person already in a programme alone.
Status = Literal["new", "tag", "already", "error"]

_TEMPLATE_ROWS = (
    ("+919810000001", "Anita Kumari", "Home health aide trainee", "Tamil Nadu", "Chennai", "0"),
    ("9810000002", "Ravi Shankar", "Diploma holder seeking ward work", "Maharashtra", "Pune", "1"),
)


@dataclass
class RowReport:
    row: int
    status: Status
    phone: str | None = None  # masked, always
    first_name: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class EnrolmentReport:
    programme: str
    rows: list[RowReport]
    notes: list[str]
    applied: bool
    errors_csv: str | None = None
    batch_id: uuid.UUID | None = None

    def count(self, status: Status) -> int:
        return sum(1 for r in self.rows if r.status == status)


@dataclass
class _Plan:
    """One row, read and validated. Holds the real number: it never leaves this module."""

    raw: RawRow
    phone: str = ""
    full_name: str | None = None
    headline: str | None = None
    state: str | None = None
    district: str | None = None
    years: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerows(_TEMPLATE_ROWS)
    return out.getvalue()


def clean_programme(value: str) -> str:
    """The tag every row is filed under. Free text by design (`enrolled_via_programme`), so the
    only rules are that it is something, and not so long it cannot be a label."""
    name = " ".join(value.split())
    if len(name) < 2:
        raise BulkFileError("Give the programme a name of at least two characters.")
    if len(name) > MAX_PROGRAMME:
        raise BulkFileError(f"The programme name may be at most {MAX_PROGRAMME} characters.")
    return name


def _read(raw: RawRow, places: PlaceIndex) -> _Plan:
    plan = _Plan(raw=raw)
    cells = raw.cells

    phone = normalise_phone(cells.get("phone", ""))
    if _MOBILE.match(phone):
        plan.phone = phone
    else:
        plan.errors.append("phone: not an Indian mobile number (ten digits starting 6 to 9)")

    name = " ".join(cells.get("full_name", "").split())
    if len(name) > MAX_NAME:
        plan.errors.append(f"full_name: at most {MAX_NAME} characters")
    plan.full_name = name or None

    headline = " ".join(cells.get("headline", "").split())
    if len(headline) > MAX_HEADLINE:
        plan.errors.append(f"headline: at most {MAX_HEADLINE} characters")
    plan.headline = headline or None

    for column in ("state", "district"):
        value = " ".join(cells.get(column, "").split())
        if len(value) > MAX_PLACE:
            plan.errors.append(f"{column}: at most {MAX_PLACE} characters")
        setattr(plan, column, value or None)

    problems: list[str] = []
    years = int_cell(cells, "years_experience", problems)
    plan.errors.extend(problems)
    if years is not None:
        if years < 0 or years > MAX_YEARS:
            plan.errors.append(f"years_experience: between 0 and {MAX_YEARS}")
        else:
            plan.years = years

    # A place that does not resolve is not an error: the written text is kept beside an empty id
    # (no id is better than a wrong one). It is worth saying, because it is invisible to matching
    # by location until somebody fixes it.
    located = places.resolve(plan.state, plan.district)
    if plan.state and located.state_id is None:
        plan.warnings.append(f"state '{plan.state}' is not a recognised state")
    if plan.district and located.district_id is None:
        plan.warnings.append(f"district '{plan.district}' is not a recognised district there")
    return plan


async def _existing(
    db: AsyncSession, phones: list[str]
) -> tuple[dict[str, User], dict[uuid.UUID, CandidateProfile]]:
    """Who already holds these numbers, and their profiles. Chunked: asyncpg refuses a statement
    with more than 32,767 bind parameters, and the cap on a file is a setting."""
    users: dict[str, User] = {}
    profiles: dict[uuid.UUID, CandidateProfile] = {}
    for start in range(0, len(phones), 5000):
        chunk = phones[start : start + 5000]
        for user in await db.scalars(select(User).where(User.phone.in_(chunk))):
            if user.phone:
                users[user.phone] = user
    ids = [u.id for u in users.values()]
    for start in range(0, len(ids), 5000):
        for profile in await db.scalars(
            select(CandidateProfile).where(CandidateProfile.user_id.in_(ids[start : start + 5000]))
        ):
            profiles[profile.user_id] = profile
    return users, profiles


def _decide(
    plan: _Plan,
    users: dict[str, User],
    profiles: dict[uuid.UUID, CandidateProfile],
    seen: dict[str, int],
) -> tuple[Status, str | None]:
    """The one rule for a row, shared by the check and the apply. `(status, reason)`."""
    if plan.errors:
        return "error", None
    first = seen.get(plan.phone)
    if first is not None:
        return "error", f"phone: the same number as row {first}"
    seen[plan.phone] = plan.raw.number

    user = users.get(plan.phone)
    if user is None:
        return "new", None
    profile = profiles.get(user.id)
    if profile is not None and profile.enrolled_via_programme:
        return "already", "already enrolled in a programme; left alone"
    return "tag", None


async def run(
    db: AsyncSession,
    text: str,
    *,
    programme: str,
    apply: bool,
    attested: bool,
    actor: User,
    file_name: str | None = None,
) -> EnrolmentReport:
    """Read the file and say what would happen to each row; with `apply`, do it.

    Raises `BulkFileError` for a file or an apply nothing can be done with, before anything is
    written. An apply without the attestation is one of those.
    """
    programme = clean_programme(programme)
    if apply and not attested:
        raise BulkFileError(
            "Confirm that the privacy notice was read out to everyone in the file before "
            "enrolling them."
        )

    rows, notes, header = parse_records(
        text,
        columns=COLUMNS,
        required=REQUIRED,
        max_rows=get_settings().enrolment_max_rows,
    )
    places = await load_place_index(db)
    plans = [_read(r, places) for r in rows]
    users, profiles = await _existing(db, sorted({p.phone for p in plans if p.phone}))

    seen: dict[str, int] = {}
    reports: list[RowReport] = []
    failed: dict[int, str] = {}
    decided: list[tuple[_Plan, Status]] = []
    for plan in plans:
        status, reason = _decide(plan, users, profiles, seen)
        decided.append((plan, status))
        report = RowReport(
            row=plan.raw.number,
            status=status,
            phone=mask_phone(plan.phone) if plan.phone else None,
            first_name=(plan.full_name or "").split(" ")[0] or None,
            warnings=list(plan.warnings),
            errors=list(plan.errors),
        )
        if reason:
            (report.errors if status == "error" else report.warnings).append(reason)
        if status == "error":
            failed[plan.raw.number] = "; ".join(report.errors)
        reports.append(report)

    batch_id: uuid.UUID | None = None
    if apply:
        batch_id = await _apply(
            db,
            decided,
            reports,
            failed,
            users,
            profiles,
            places,
            programme=programme,
            actor=actor,
            file_name=file_name,
        )

    return EnrolmentReport(
        programme=programme,
        rows=reports,
        notes=notes,
        applied=apply,
        errors_csv=errors_csv(header, rows, failed),
        batch_id=batch_id,
    )


async def _apply(
    db: AsyncSession,
    decided: list[tuple[_Plan, Status]],
    reports: list[RowReport],
    failed: dict[int, str],
    users: dict[str, User],
    profiles: dict[uuid.UUID, CandidateProfile],
    places: PlaceIndex,
    *,
    programme: str,
    actor: User,
    file_name: str | None,
) -> uuid.UUID:
    actor_id = actor.id  # read once: a later rollback would expire `actor`
    now = datetime.now(UTC)
    batch = EnrolmentBatch(
        programme=programme,
        file_name=(file_name or "")[:200] or None,
        actor_user_id=actor_id,
        attested_notice_version=PRIVACY_NOTICE_VERSION,
        attested_at=now,
    )
    db.add(batch)
    await db.flush()
    batch_id = batch.id

    by_row = {r.row: r for r in reports}
    for plan, status in decided:
        if status in ("error", "already"):
            continue
        report = by_row[plan.raw.number]
        try:
            # A savepoint per row: a failure rolls back this row only, and a number that raced in
            # from another request is the unique constraint refusing it, not a 500.
            async with db.begin_nested():
                outcome = await _write(db, plan, status, users, profiles, places, programme)
                db.add(
                    EnrolmentBatchMember(
                        profile_id=outcome[0], batch_id=batch_id, outcome=outcome[1]
                    )
                )
        except (IntegrityError, _EnrolledMeanwhile):
            report.status = "already"
            report.warnings.append("another request enrolled this number first; left alone")
            log.warning("enrolment.row_raced")

    batch.created_count = sum(1 for r in reports if r.status == "new")
    batch.tagged_count = sum(1 for r in reports if r.status == "tag")
    batch.already_count = sum(1 for r in reports if r.status == "already")
    batch.error_count = sum(1 for r in reports if r.status == "error")
    counts = {
        "created": batch.created_count,
        "tagged": batch.tagged_count,
        "already": batch.already_count,
        "errors": batch.error_count,
    }
    await db.commit()
    log.info("enrolment.applied", **counts)
    # After the commit: `record()` commits too, and a failure inside it must not roll this back.
    await record(
        db,
        "enrolment_applied",
        user_id=actor_id,
        subject_type=None,
        subject_id=batch_id,
        payload={"programme": programme, **counts},
    )
    return batch_id


async def _write(
    db: AsyncSession,
    plan: _Plan,
    status: Status,
    users: dict[str, User],
    profiles: dict[uuid.UUID, CandidateProfile],
    places: PlaceIndex,
    programme: str,
) -> tuple[uuid.UUID, str]:
    """The writes for one row. `(profile id, member outcome)`."""
    if status == "tag":
        user = users[plan.phone]
        # Lock the profile: two programmes tagging one existing person at once must not both win.
        profile = await db.scalar(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if profile is not None and profile.enrolled_via_programme:
            raise _EnrolledMeanwhile
        if profile is None:
            # Signed in once and never finished a profile: the tag needs somewhere to live.
            profile = CandidateProfile(user_id=user.id)
            db.add(profile)
        profile.enrolled_via_programme = programme
        await db.flush()
        return profile.id, "tagged"

    user = await provision_candidate(db, plan.phone, consent_version=PRIVACY_NOTICE_VERSION)
    user.full_name = plan.full_name
    located = places.resolve(plan.state, plan.district)
    profile = CandidateProfile(
        user_id=user.id,
        headline=plan.headline,
        location_state=plan.state,
        location_district=plan.district,
        state_id=located.state_id,
        district_id=located.district_id,
        years_experience=plan.years,
        enrolled_via_programme=programme,
    )
    db.add(profile)
    await db.flush()
    return profile.id, "created"


# ------------------------------------------------------------------------------------- history


@dataclass
class BatchSummary:
    id: uuid.UUID
    programme: str
    file_name: str | None
    operator: str | None  # masked; None once the operator has erased their account
    attested_notice_version: str
    attested_at: datetime
    created: int
    tagged: int
    already: int
    errors: int
    created_at: datetime


async def recent_batches(db: AsyncSession, *, limit: int = 50) -> list[BatchSummary]:
    rows = (
        await db.execute(
            select(EnrolmentBatch, User.email)
            .join(User, User.id == EnrolmentBatch.actor_user_id, isouter=True)
            .order_by(EnrolmentBatch.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        BatchSummary(
            id=b.id,
            programme=b.programme,
            file_name=b.file_name,
            operator=mask_email(email) if email else None,
            attested_notice_version=b.attested_notice_version,
            attested_at=b.attested_at,
            created=b.created_count,
            tagged=b.tagged_count,
            already=b.already_count,
            errors=b.error_count,
            created_at=b.created_at,
        )
        for b, email in rows
    ]


async def enrolments_for_profile(
    db: AsyncSession, profile_id: uuid.UUID
) -> dict[str, object] | None:
    """What a person's own export says about how they came to be in a programme: the programme,
    when, whether an account was made for them, and which notice version an operator attested.
    Never the operator."""
    row = (
        await db.execute(
            select(EnrolmentBatchMember.outcome, EnrolmentBatch)
            .join(EnrolmentBatch, EnrolmentBatch.id == EnrolmentBatchMember.batch_id)
            .where(EnrolmentBatchMember.profile_id == profile_id)
        )
    ).first()
    if row is None:
        return None
    outcome, batch = row
    return {
        "programme": batch.programme,
        "enrolled_at": batch.attested_at.isoformat(),
        "account_created_for_you": outcome == "created",
        "privacy_notice_version_attested": batch.attested_notice_version,
        "attested_by": "an operator of this platform, on your behalf",
    }
