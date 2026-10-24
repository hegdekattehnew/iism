"""A file of batches (Sprint 99, ADR-103, BL-18.8): checked, then drafts, then published.

The three steps of the vacancy and course upload (ADR-063), with its file rules
(`marketplace.bulk.parse_records`). **Check** writes nothing, **apply** creates drafts, and
**publish** is a separate act on the ids the apply returned; `check` and `apply` run the one
`_decide`, so the preview cannot promise what the apply will not do (ADR-071's lesson).

Every row goes through `service.add_batch`, the single writer, so the lock, the authorisation, the
open centre, the live course and the per-centre cap are the same refusals as one batch made by hand.
A row never overwrites: a batch of the same course at the same centre on the same first day and
under the same name is a `skip` naming the one it matched, and the second appearance of a row in the
file is an error. A bad row never blocks a good one.

A course is named by its slug or its exact title among the courses this organisation may deliver; a
centre by its slug or its exact name among its centres. **Never fuzzy**: a wrong match here is a
class planned at the wrong place.
"""

import csv
import io
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import today_ist
from api.modules.analytics import record
from api.modules.batches import service
from api.modules.batches.models import Batch
from api.modules.batches.schemas import BatchIn
from api.modules.identity.models import Tenant, User
from api.modules.marketplace.bulk import (
    BulkFileError,
    RawRow,
    decode,
    errors_csv,
    parse_records,
)
from api.modules.marketplace.models import Course

__all__ = [
    "BulkFileError",
    "PublishResult",
    "Report",
    "Row",
    "decode",
    "publish_many",
    "run",
    "template_csv",
]

COLUMNS = (
    "course",
    "centre",
    "starts_on",
    "ends_on",
    "seats",
    "mode",
    "label",
    "schedule",
    "fee_inr",
)
REQUIRED = {"course", "centre", "starts_on", "ends_on", "seats"}
MAX_ROWS = 200

Status = Literal["ok", "warning", "error", "skip"]


@dataclass
class Row:
    row: int
    status: Status
    course: str | None = None
    centre: str | None = None
    messages: list[str] = field(default_factory=list)
    id: str | None = None
    created: bool = False


@dataclass
class Report:
    applied: bool
    rows: list[Row]
    notes: list[str]
    errors_csv: str | None = None

    def count(self, status: Status) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def created(self) -> int:
        return sum(1 for r in self.rows if r.created)


@dataclass
class PublishResult:
    id: str
    published: bool
    message: str | None = None


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerow(
        (
            "welding-basics",
            "Hadapsar Skill Centre",
            "2026-12-01",
            "2027-01-15",
            "25",
            "in_person",
            "Morning batch",
            "Mon to Fri, 9 to 1",
            "3500",
        )
    )
    writer.writerow(("welding-basics", "hadapsar-skill-centre", "2027-02-01", "2027-03-15", "20"))
    return out.getvalue()


def _messages(error: ValidationError) -> list[str]:
    out = []
    for item in error.errors():
        where = ".".join(str(p) for p in item["loc"])
        text = str(item.get("msg", "invalid")).removeprefix("Value error, ")
        out.append(f"{where}: {text}" if where else text)
    return out


def _key(label: str | None) -> str:
    return " ".join((label or "").lower().split())


async def run(
    db: AsyncSession,
    organisation: Tenant,
    text: str,
    *,
    apply: bool,
    actor: User,
) -> Report:
    rows, notes, header = parse_records(text, columns=COLUMNS, required=REQUIRED, max_rows=MAX_ROWS)
    organisation_id = organisation.id
    actor_id = actor.id

    # What the file may name: the courses this organisation may deliver, its open centres.
    deliverable = await service.deliverable_courses(db, organisation)
    courses_by_slug = {
        c.slug: c
        for c in (
            await db.scalars(
                select(Course).where(Course.slug.in_([i.slug for i in deliverable.items]))
            )
        ).all()
    }
    by_slug = dict(courses_by_slug)
    by_title: dict[str, list[Course]] = defaultdict(list)
    for known in by_slug.values():
        by_title[known.title.strip().lower()].append(known)
    centres = (
        await db.scalars(
            select(Tenant).where(
                Tenant.parent_id == organisation_id, Tenant.tenant_type == "training_centre"
            )
        )
    ).all()
    centre_by_slug = {ce.slug: ce for ce in centres}
    centre_by_name: dict[str, list[Tenant]] = defaultdict(list)
    for ce in centres:
        centre_by_name[ce.name.strip().lower()].append(ce)
    centre_ids = [ce.id for ce in centres]

    # What exists already, for "the same batch" and for the per-centre room.
    today = today_ist()
    existing: dict[tuple[uuid.UUID, uuid.UUID, date, str], uuid.UUID] = {}
    live: Counter[uuid.UUID] = Counter()
    if centre_ids:
        for b in (
            await db.scalars(
                select(Batch).where(
                    Batch.centre_id.in_(centre_ids),
                    Batch.status.in_(("draft", "published")),
                    Batch.ends_on >= today,
                )
            )
        ).all():
            existing[(b.course_id, b.centre_id, b.starts_on, _key(b.label))] = b.id
            live[b.centre_id] += 1

    report: list[Row] = []
    seen: dict[tuple[uuid.UUID, uuid.UUID, date, str], int] = {}
    creatable: list[tuple[Row, BatchIn, Course, Tenant]] = []

    def _decide(raw: RawRow) -> tuple[Row, BatchIn | None, Course | None, Tenant | None]:
        cells = raw.cells
        item = Row(
            row=raw.number,
            status="ok",
            course=cells.get("course") or None,
            centre=cells.get("centre") or None,
        )
        if raw.extra_cells:
            item.status = "warning"
            item.messages.append(
                "The row has more cells than the header; the extra ones are ignored."
            )
        wanted = cells.get("course", "").strip()
        course = by_slug.get(wanted)
        if course is None:
            matches = by_title.get(wanted.lower(), [])
            if len(matches) > 1:
                item.status = "error"
                item.messages.append(
                    "Two of your courses have that title; write the course's slug instead."
                )
                return item, None, None, None
            course = matches[0] if matches else None
        if course is None:
            item.status = "error"
            item.messages.append(
                "No course you may deliver is called that. Use its slug or its exact title, and "
                "check you are authorised to deliver it."
            )
            return item, None, None, None
        named = cells.get("centre", "").strip()
        centre = centre_by_slug.get(named)
        if centre is None:
            matches_c = centre_by_name.get(named.lower(), [])
            if len(matches_c) > 1:
                item.status = "error"
                item.messages.append("Two centres have that name; write the centre's slug instead.")
                return item, None, None, None
            centre = matches_c[0] if matches_c else None
        if centre is None:
            item.status = "error"
            item.messages.append("This organisation has no centre called that.")
            return item, None, None, None
        if centre.closed_at is not None:
            item.status = "error"
            item.messages.append("That centre is closed. Reopen it to plan a batch there.")
            return item, None, None, None
        try:
            data = BatchIn(
                course_slug=course.slug,
                centre_slug=centre.slug,
                label=cells.get("label") or None,
                starts_on=cells.get("starts_on", ""),
                ends_on=cells.get("ends_on", ""),
                seats=cells.get("seats", ""),
                mode=cells.get("mode") or "in_person",
                schedule=cells.get("schedule") or None,
                fee_inr=cells.get("fee_inr") or None,
            )
        except ValidationError as error:
            item.status = "error"
            item.messages.extend(_messages(error))
            return item, None, None, None
        key = (course.id, centre.id, data.starts_on, _key(data.label))
        if key in existing:
            item.status = "skip"
            item.id = str(existing[key])
            item.messages.append(
                "This batch is already planned (same course, centre, day and name)."
            )
            return item, None, None, None
        if key in seen:
            item.status = "error"
            item.messages.append(f"The same batch appears on row {seen[key]}.")
            return item, None, None, None
        if live[centre.id] >= service.MAX_LIVE_PER_CENTRE:
            item.status = "error"
            item.messages.append(
                f"A centre can have up to {service.MAX_LIVE_PER_CENTRE} batches that are not over."
            )
            return item, None, None, None
        seen[key] = raw.number
        live[centre.id] += 1
        return item, data, course, centre

    for raw in rows:
        item, data, course, centre = _decide(raw)
        if data is not None and course is not None and centre is not None:
            creatable.append((item, data, course, centre))
        report.append(item)

    if apply:
        for item, data, course, centre in creatable:
            try:
                async with db.begin_nested():
                    batch = await service.add_batch(db, centre.id, course, actor_id, data)
            except HTTPException as error:
                # A refusal the check could not see (an arrangement ended meanwhile). The savepoint
                # undid the row; the earlier rows stand.
                item.status = "error"
                item.messages.append(str(error.detail))
                continue
            item.created = True
            item.id = str(batch.id)
        await db.commit()
        if any(r.created for r in report):
            await record(
                db,
                "batch_created",
                user_id=actor_id,
                subject_type="tenant",
                subject_id=organisation_id,
                payload={"bulk": sum(1 for r in report if r.created)},
            )

    failed = {r.row: "; ".join(r.messages) for r in report if r.status == "error"}
    return Report(
        applied=apply,
        rows=report,
        notes=notes,
        errors_csv=errors_csv(header, rows, failed),
    )


async def publish_many(
    db: AsyncSession, tenant: Tenant, actor: User, ids: list[str]
) -> list[PublishResult]:
    """Publish through the single writer's own rules, one row at a time. A refusal (the course
    stopped being live, the arrangement ended, the first day passed) is reported and stops nothing;
    an id that is not this organisation's is a plain "not found", never a hint it exists."""
    results: list[PublishResult] = []
    for raw in dict.fromkeys(ids):
        try:
            batch_id = uuid.UUID(raw)
        except ValueError:
            results.append(PublishResult(raw, False, "Batch not found"))
            continue
        try:
            await service.publish_batch(db, tenant, actor, batch_id)
        except HTTPException as error:
            results.append(PublishResult(raw, False, str(error.detail)))
        else:
            results.append(PublishResult(raw, True))
    return results
