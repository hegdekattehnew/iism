"""MongoDB implementation of the NSQF source.

Reads `iism_nsqf_master_data` and translates its document layout into the
normalised records. Every quirk of the source is absorbed here so that nothing
downstream has to know about `compulsoryNos`, `HH:MM` strings or the fact that
a NOS carries no level.
"""

from collections.abc import AsyncIterator
from typing import Any

from pymongo import AsyncMongoClient

from api.adapters.nsqf.base import NsqfSource
from api.adapters.nsqf.normalise import (
    NormalisationError,
    clean_text,
    parse_credits,
    parse_hhmm_to_minutes,
    parse_level,
)
from api.adapters.nsqf.records import (
    McRecord,
    McSkillHours,
    NosRecord,
    QpNosLink,
    QpRecord,
)
from api.core.config import get_settings

BATCH = 1000


def _nos_from_doc(doc: dict[str, Any]) -> NosRecord | None:
    code = clean_text(doc.get("unitCode"))
    if not code:
        return None
    return NosRecord(
        code=code,
        title=clean_text(doc.get("unitTitle")) or code,
        version=clean_text(doc.get("version")) or "1.0",
        nos_type=clean_text(doc.get("type") or doc.get("nosType")),
        description=clean_text(
            doc.get("description") or (doc.get("nosDesc") or {}).get("description")
            if isinstance(doc.get("nosDesc"), dict)
            else doc.get("description")
        ),
        credits=parse_credits(doc.get("credits")),
    )


class MongoNsqfSource(NsqfSource):
    def __init__(self, url: str | None = None, database: str | None = None) -> None:
        settings = get_settings()
        self._client: AsyncMongoClient = AsyncMongoClient(url or settings.mongo_url)
        self._db = self._client[database or settings.mongo_database]

    async def close(self) -> None:
        await self._client.close()

    async def iter_nos(self) -> AsyncIterator[NosRecord]:
        cursor = self._db.nos.find({}, batch_size=BATCH)
        async for doc in cursor:
            record = _nos_from_doc(doc)
            if record is not None:
                yield record

    async def iter_qps(self) -> AsyncIterator[QpRecord]:
        cursor = self._db.qps.find({}, batch_size=BATCH)
        async for doc in cursor:
            code = clean_text(doc.get("qpCode"))
            if not code:
                continue

            links: list[QpNosLink] = []
            embedded: list[NosRecord] = []

            # Compulsory units are a flat list.
            for entry in doc.get("compulsoryNos") or []:
                if not isinstance(entry, dict):
                    continue
                nos = _nos_from_doc(entry)
                if nos is None:
                    continue
                embedded.append(nos)
                links.append(QpNosLink(nos_code=nos.code, requirement="compulsory"))

            # Elective and optional units are nested inside named groups, and
            # flattening them without keeping the group name would lose the
            # "choose one of these" structure entirely.
            for field, requirement in (
                ("electiveNos", "elective"),
                ("optionalNos", "optional"),
            ):
                for group in doc.get(field) or []:
                    if not isinstance(group, dict):
                        continue
                    group_name = clean_text(group.get("name"))
                    for entry in group.get("nos") or []:
                        if not isinstance(entry, dict):
                            continue
                        nos = _nos_from_doc(entry)
                        if nos is None:
                            continue
                        embedded.append(nos)
                        links.append(
                            QpNosLink(
                                nos_code=nos.code,
                                requirement=requirement,
                                group_name=group_name,
                            )
                        )

            sectors = doc.get("sectors") if isinstance(doc.get("sectors"), dict) else {}
            sub_sectors = sectors.get("subSectors") or []
            sub = sub_sectors[0] if sub_sectors and isinstance(sub_sectors[0], dict) else {}
            occupation = doc.get("occupation") if isinstance(doc.get("occupation"), dict) else {}
            status = doc.get("status") if isinstance(doc.get("status"), dict) else {}

            try:
                level = parse_level(doc.get("nsqfLevel"))
            except NormalisationError:
                # A QP with an unreadable level is still a real qualification;
                # the level is simply unknown rather than the record invalid.
                level = None

            total_hours = doc.get("totalHoursQplevel")
            yield QpRecord(
                code=code,
                version=clean_text(doc.get("version")) or "1.0",
                name=clean_text(doc.get("qpName") or doc.get("jobRole")) or code,
                job_role=clean_text(doc.get("jobRole")),
                nsqf_level=level,
                status=clean_text(status.get("statusDesc")),
                total_hours=int(total_hours) if isinstance(total_hours, (int, float)) else None,
                sector_ref=clean_text(sectors.get("sectorID")),
                sector_name=clean_text(sectors.get("sectorName")),
                sub_sector_ref=clean_text(sub.get("subSectorID")),
                sub_sector_name=clean_text(sub.get("subSectorName")),
                occupation=clean_text(occupation.get("occupationDesc")),
                nos_links=tuple(links),
                embedded_nos=tuple(embedded),
            )

    async def iter_model_curricula(self) -> AsyncIterator[McRecord]:
        cursor = self._db.modelcurriculum.find({}, batch_size=BATCH)
        async for doc in cursor:
            qp_code = clean_text(doc.get("qpCode"))
            if not qp_code:
                continue

            nos_block = doc.get("nos") if isinstance(doc.get("nos"), dict) else {}
            hours: list[McSkillHours] = []
            blank_codes = 0

            # Three lists, not one. The key really is spelled "compulsary" in
            # the source, and elective/optional carry a further ~467 usable
            # entries that would otherwise be silently discarded.
            entries = [
                entry
                for key in ("compulsary", "elective", "optional")
                for entry in (nos_block.get(key) or [])
            ]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                code = clean_text(entry.get("unitCode"))
                if not code:
                    # unitCode is present but blank on 2,372 of 2,585 records.
                    # Counted rather than dropped in silence, and rather than
                    # raised -- one aggregate number is honest without burying
                    # real failures under thousands of lines.
                    blank_codes += 1
                    continue
                try:
                    hours.append(
                        McSkillHours(
                            nos_code=code,
                            theory_minutes=parse_hhmm_to_minutes(entry.get("compulsory")),
                            practical_minutes=parse_hhmm_to_minutes(entry.get("practical")),
                            ojt_minutes=parse_hhmm_to_minutes(entry.get("ojtmanditory")),
                            total_minutes=parse_hhmm_to_minutes(entry.get("nosTotal")),
                        )
                    )
                except NormalisationError:
                    # Unreadable durations do not invalidate the curriculum;
                    # the unit is recorded without hours.
                    hours.append(McSkillHours(nos_code=code))

            try:
                total = parse_hhmm_to_minutes(doc.get("grandTotal"))
            except NormalisationError:
                total = None
            try:
                level = parse_level(doc.get("nsqfLevel"))
            except NormalisationError:
                level = None

            yield McRecord(
                blank_unit_codes=blank_codes,
                qp_code=qp_code,
                version=clean_text(doc.get("MCversion")) or "1.0",
                job_role=clean_text(doc.get("jobRole")),
                nsqf_level=level,
                status=clean_text(doc.get("MCStatus")),
                total_minutes=total,
                document_ref=clean_text(doc.get("document")),
                skills=tuple(hours),
            )
