"""A file of centres (Sprint 95, ADR-102): checked first, then created.

The same two steps as the vacancy and course upload (ADR-063) with the same file rules
(`marketplace.bulk.parse_records`), but a centre has no draft state to stop at: it is a place, it
is not live anywhere until the operator checks its address, and closing it is one press. So there
is **check** (writes nothing) and **apply** (creates), and both run the same `_decide` so the
preview cannot promise what the apply will not do (ADR-071's lesson).

A row never overwrites: a name the organisation already has (closed ones included) is a `skip`
naming the centre it matched, and a name repeated inside the file is an error on the second
occurrence. The cap is applied identically by check and apply.
"""

import csv
import io
import uuid
from dataclasses import dataclass, field
from typing import Literal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.modules.analytics import record
from api.modules.centres import service
from api.modules.centres.schemas import CentreIn
from api.modules.geography import resolve_location
from api.modules.identity.models import Tenant
from api.modules.marketplace.bulk import (
    BulkFileError,
    RawRow,
    decode,
    errors_csv,
    parse_records,
)

__all__ = ["BulkFileError", "CentreRow", "Report", "decode", "run", "template_csv"]

COLUMNS = ("name", "address", "state", "district")
REQUIRED = {"name", "state", "district"}
MAX_ROWS = 200

Status = Literal["ok", "warning", "error", "skip"]


@dataclass
class CentreRow:
    row: int
    status: Status
    name: str | None = None
    messages: list[str] = field(default_factory=list)
    slug: str | None = None
    created: bool = False


@dataclass
class Report:
    applied: bool
    rows: list[CentreRow]
    notes: list[str]
    remaining: int
    errors_csv: str | None = None

    def count(self, status: Status) -> int:
        return sum(1 for r in self.rows if r.status == status)

    @property
    def created(self) -> int:
        return sum(1 for r in self.rows if r.created)


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerow(("Pune Hadapsar Centre", "Plot 12, Magarpatta Road", "Maharashtra", "Pune"))
    writer.writerow(("Nagpur Sitabuldi Centre", "", "Maharashtra", "Nagpur"))
    return out.getvalue()


def _validation_messages(error: ValidationError) -> list[str]:
    messages = []
    for item in error.errors():
        where = ".".join(str(p) for p in item["loc"])
        text = str(item.get("msg", "invalid")).removeprefix("Value error, ")
        messages.append(f"{where}: {text}" if where else text)
    return messages


async def run(
    db: AsyncSession,
    parent: Tenant,
    text: str,
    *,
    apply: bool,
    actor_id: uuid.UUID,
) -> Report:
    rows, notes, header = parse_records(text, columns=COLUMNS, required=REQUIRED, max_rows=MAX_ROWS)
    parent_id = parent.id
    names = await service.existing_names(db, parent_id)
    room = max(0, service.MAX_CENTRES - await service.centre_count(db, parent_id))

    report: list[CentreRow] = []
    failed: dict[int, str] = {}
    seen: dict[str, int] = {}
    creatable: list[tuple[CentreRow, CentreIn]] = []

    def _decide(raw: RawRow) -> tuple[CentreRow, CentreIn | None]:
        cells = raw.cells
        item = CentreRow(row=raw.number, status="ok", name=cells.get("name") or None)
        if raw.extra_cells:
            item.status = "warning"
            item.messages.append(
                "The row has more cells than the header; the extra ones are ignored."
            )
        try:
            data = CentreIn(
                name=cells.get("name", ""),
                address=cells.get("address") or None,
                state=cells.get("state", ""),
                district=cells.get("district", ""),
            )
        except ValidationError as error:
            item.status = "error"
            item.messages.extend(_validation_messages(error))
            return item, None
        key = service._name_key(data.name)
        if key in names:
            item.status = "skip"
            item.slug = names[key]
            item.messages.append("This organisation already has a centre called that.")
            return item, None
        if key in seen:
            item.status = "error"
            item.messages.append(f"The same name appears on row {seen[key]}.")
            return item, None
        seen[key] = raw.number
        if len(creatable) >= room:
            item.status = "error"
            item.messages.append(
                f"An organisation can have up to {service.MAX_CENTRES} centres; this one is over."
            )
            return item, None
        return item, data

    for raw in rows:
        item, data = _decide(raw)
        if data is not None:
            creatable.append((item, data))
        report.append(item)

    if apply:
        await service.lock_delivering_parent(db, parent_id)
        for item, data in creatable:
            try:
                centre = await service.add_centre(db, parent, data)
            except HTTPException as error:
                # A refusal the check could not see (a race). `add_centre` inserts in a savepoint:
                # nothing needs undoing, and a rollback would take the earlier rows with it.
                item.status = "error"
                item.messages.append(str(error.detail))
                continue
            item.created = True
            item.slug = centre.slug
            if centre.district_id is None:
                item.status = "warning"
                item.messages.append(
                    "The place was not found in the national list; it is kept as written."
                )
        await db.commit()
        if any(r.created for r in report):
            await record(
                db,
                "centres_bulk_uploaded",
                user_id=actor_id,
                subject_type="tenant",
                subject_id=parent_id,
                payload={"created": sum(1 for r in report if r.created)},
            )
    else:
        for item, data in creatable:
            # Preview the place the way the apply will resolve it.
            located = await resolve_location(db, data.state, data.district)
            if located.district_id is None:
                item.status = "warning"
                item.messages.append(
                    "The place was not found in the national list; it is kept as written."
                )

    for item in report:
        if item.status == "error":
            failed[item.row] = "; ".join(item.messages)
    return Report(
        applied=apply,
        rows=report,
        notes=notes,
        remaining=max(
            0,
            room
            - sum(1 for r in report if r.created or (not apply and r.status in ("ok", "warning"))),
        ),
        errors_csv=errors_csv(header, rows, failed),
    )
