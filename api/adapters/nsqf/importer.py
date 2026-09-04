"""Projects the NSQF corpus from its source of record into PostgreSQL.

MongoDB is master (ADR-034); this rebuilds the operational taxonomy from it and
is safe to re-run. Everything is keyed on the national codes, so a second run
updates rather than duplicates.

Only the newest version of each code is projected. Prior versions stay in
MongoDB — that is precisely what making it the source of record buys.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.adapters.nsqf.base import NsqfSource
from api.adapters.nsqf.normalise import (
    NormalisationError,
    make_qp_slug,
    make_skill_slug,
    slugify,
    version_sort_key,
)
from api.adapters.nsqf.records import ImportProblem, McRecord, NosRecord, QpRecord
from api.modules.skills.hierarchy import (
    ModelCurriculum,
    ModelCurriculumSkill,
    Occupation,
    QpSkill,
    QualificationPack,
    Sector,
    SubSector,
)
from api.modules.skills.models import Skill

CHUNK = 500


@dataclass
class ImportReport:
    sectors: int = 0
    sub_sectors: int = 0
    occupations: int = 0
    skills: int = 0
    qualification_packs: int = 0
    qp_skills: int = 0
    model_curricula: int = 0
    mc_skills: int = 0
    levels_derived: int = 0
    mc_entries_without_code: int = 0
    problems: list[ImportProblem] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"sectors={self.sectors} sub_sectors={self.sub_sectors} "
            f"occupations={self.occupations} skills={self.skills} "
            f"qps={self.qualification_packs} qp_skills={self.qp_skills} "
            f"curricula={self.model_curricula} mc_skills={self.mc_skills} "
            f"levels_derived={self.levels_derived} "
            f"mc_entries_without_code={self.mc_entries_without_code} "
            f"problems={len(self.problems)}"
        )


def _latest(records: dict[str, Any], code: str, record: Any, version: str) -> None:
    """Keep only the newest version of each code."""
    existing = records.get(code)
    if existing is None or version_sort_key(version) > version_sort_key(existing[1]):
        records[code] = (record, version)


async def _chunked_upsert(
    db: AsyncSession, table: Any, rows: list[dict[str, Any]], index_elements: list[str]
) -> int:
    """Upsert in batches. ON CONFLICT DO UPDATE is what makes a re-run update
    rather than fail, and batching is what makes 21,000 rows finish."""
    written = 0
    for start in range(0, len(rows), CHUNK):
        batch = rows[start : start + CHUNK]
        if not batch:
            continue
        stmt = insert(table).values(batch)
        update = {
            c: stmt.excluded[c] for c in batch[0] if c not in {*index_elements, "id", "created_at"}
        }
        await db.execute(
            stmt.on_conflict_do_update(index_elements=index_elements, set_=update)
            if update
            else stmt.on_conflict_do_nothing(index_elements=index_elements)
        )
        written += len(batch)
    return written


async def import_nsqf(db: AsyncSession, source: NsqfSource) -> ImportReport:
    report = ImportReport()

    # ---------------------------------------------------------------- collect
    nos_by_code: dict[str, tuple[NosRecord, str]] = {}
    async for nos in source.iter_nos():
        _latest(nos_by_code, nos.code, nos, nos.version)

    qp_by_code: dict[str, tuple[QpRecord, str]] = {}
    async for qp in source.iter_qps():
        _latest(qp_by_code, qp.code, qp, qp.version)
        # A NOS embedded in a QP but missing from the nos collection is still a
        # real unit; without this it would vanish and the QP would look empty.
        for embedded in qp.embedded_nos:
            if embedded.code not in nos_by_code:
                _latest(nos_by_code, embedded.code, embedded, embedded.version)

    mc_by_key: dict[str, tuple[McRecord, str]] = {}
    async for mc in source.iter_model_curricula():
        report.mc_entries_without_code += mc.blank_unit_codes
        _latest(mc_by_key, f"{mc.qp_code}", mc, mc.version)

    # ------------------------------------------------------- sectors & lookups
    sector_rows: dict[str, dict[str, Any]] = {}
    sub_rows: dict[tuple[Any, str], dict[str, Any]] = {}
    occupation_names: set[str] = set()
    for qp, _ in qp_by_code.values():
        if qp.sector_name:
            ref: str = qp.sector_ref or slugify(qp.sector_name)
            sector_rows.setdefault(
                ref,
                {
                    "id": uuid.uuid4(),
                    "sector_ref": ref,
                    "name_en": qp.sector_name,
                    "slug": slugify(qp.sector_name),
                },
            )
        if qp.occupation:
            occupation_names.add(qp.occupation)

    report.sectors = await _chunked_upsert(
        db, Sector.__table__, list(sector_rows.values()), ["sector_ref"]
    )
    await db.flush()
    # ruff would rewrite this as dict(), but mypy cannot type dict() over a
    # Sequence[Row[...]] and rejects it. The comprehension satisfies both tools.
    sector_ids: dict[str, uuid.UUID] = {  # noqa: C416
        row[0]: row[1] for row in (await db.execute(select(Sector.sector_ref, Sector.id))).all()
    }

    for qp, _ in qp_by_code.values():
        if not (qp.sub_sector_name and qp.sector_name):
            continue
        sector_ref = qp.sector_ref or slugify(qp.sector_name)
        sector_id = sector_ids.get(sector_ref)
        if sector_id is None:
            continue
        ref = qp.sub_sector_ref or slugify(qp.sub_sector_name)
        sub_rows.setdefault(
            (sector_id, ref),
            {
                "id": uuid.uuid4(),
                "sector_id": sector_id,
                "sub_sector_ref": ref,
                "name_en": qp.sub_sector_name,
            },
        )
    report.sub_sectors = await _chunked_upsert(
        db, SubSector.__table__, list(sub_rows.values()), ["sector_id", "sub_sector_ref"]
    )
    report.occupations = await _chunked_upsert(
        db,
        Occupation.__table__,
        [{"id": uuid.uuid4(), "name_en": n} for n in sorted(occupation_names)],
        ["name_en"],
    )
    await db.flush()

    sub_ids = {
        (sid, ref): i
        for sid, ref, i in (
            await db.execute(select(SubSector.sector_id, SubSector.sub_sector_ref, SubSector.id))
        ).all()
    }
    occupation_ids: dict[str, uuid.UUID] = {
        row[0]: row[1]
        for row in (await db.execute(select(Occupation.name_en, Occupation.id))).all()
    }

    # ------------------------------------------------------------------ skills
    skill_rows, seen_slugs = [], set()
    for nos, _ in nos_by_code.values():
        try:
            slug = make_skill_slug(nos.title, nos.code)
        except NormalisationError as exc:
            report.problems.append(ImportProblem("nos", nos.code, str(exc)))
            continue
        if slug in seen_slugs:
            slug = f"{slug}-{slugify(nos.version)}"
        seen_slugs.add(slug)
        skill_rows.append(
            {
                "id": uuid.uuid4(),
                "slug": slug,
                "name_en": nos.title,
                "description_en": nos.description,
                "skill_type": "technical",
                "nos_code": nos.code,
                "nos_version": nos.version,
                "nos_type": nos.nos_type,
                "source": "nsqf",
            }
        )
    report.skills = await _chunked_upsert(db, Skill.__table__, skill_rows, ["nos_code"])
    await db.flush()

    skill_ids: dict[str, uuid.UUID] = {
        row[0]: row[1]
        for row in (
            await db.execute(select(Skill.nos_code, Skill.id).where(Skill.nos_code.isnot(None)))
        ).all()
    }

    # ------------------------------------------------------- qualification packs
    qp_rows, qp_slugs = [], set()
    for qp, _ in qp_by_code.values():
        try:
            slug = make_qp_slug(qp.name, qp.code, qp.version)
        except NormalisationError as exc:
            report.problems.append(ImportProblem("qp", qp.code, str(exc)))
            continue
        if slug in qp_slugs:  # pragma: no cover - (code, version) is unique
            report.problems.append(ImportProblem("qp", qp.code, f"duplicate slug {slug}"))
            continue
        qp_slugs.add(slug)
        qp_sector_ref: str | None = qp.sector_ref or (
            slugify(qp.sector_name) if qp.sector_name else None
        )
        sector_id = sector_ids.get(qp_sector_ref) if qp_sector_ref else None
        sub_ref = qp.sub_sector_ref or (slugify(qp.sub_sector_name) if qp.sub_sector_name else None)
        qp_rows.append(
            {
                "id": uuid.uuid4(),
                "qp_code": qp.code,
                "version": qp.version,
                "slug": slug,
                "name_en": qp.name,
                "job_role_en": qp.job_role,
                "nsqf_level": qp.nsqf_level,
                "status": qp.status,
                "total_hours": qp.total_hours,
                "is_current": True,
                "sector_id": sector_id,
                "sub_sector_id": sub_ids.get((sector_id, sub_ref)) if sector_id else None,
                "occupation_id": occupation_ids.get(qp.occupation) if qp.occupation else None,
            }
        )
    report.qualification_packs = await _chunked_upsert(
        db, QualificationPack.__table__, qp_rows, ["qp_code", "version"]
    )
    await db.flush()

    qp_ids = {
        (c, v): i
        for c, v, i in (
            await db.execute(
                select(QualificationPack.qp_code, QualificationPack.version, QualificationPack.id)
            )
        ).all()
    }

    # ------------------------------------------------------------- qp -> skills
    link_rows, level_votes = [], defaultdict(list)
    seen_links = set()
    for qp, _ in qp_by_code.values():
        qp_id = qp_ids.get((qp.code, qp.version))
        if qp_id is None:
            continue
        for link in qp.nos_links:
            skill_id = skill_ids.get(link.nos_code)
            if skill_id is None:
                report.problems.append(
                    ImportProblem("qp_nos", f"{qp.code}->{link.nos_code}", "unknown NOS code")
                )
                continue
            if (qp_id, skill_id) in seen_links:
                continue
            seen_links.add((qp_id, skill_id))
            link_rows.append(
                {
                    "id": uuid.uuid4(),
                    "qp_id": qp_id,
                    "skill_id": skill_id,
                    "requirement": link.requirement,
                    "group_name": link.group_name,
                    "nsqf_level": qp.nsqf_level,
                }
            )
            if qp.nsqf_level is not None:
                level_votes[skill_id].append(qp.nsqf_level)
    report.qp_skills = await _chunked_upsert(
        db, QpSkill.__table__, link_rows, ["qp_id", "skill_id"]
    )

    # A NOS has no level of its own, so the displayed level is the modal level
    # of the qualifications that contain it. Authoritative level stays on the QP.
    derived = [
        {"nos_code": code, "nsqf_level": Counter(level_votes[sid]).most_common(1)[0][0]}
        for code, sid in skill_ids.items()
        if level_votes.get(sid)
    ]
    for start in range(0, len(derived), CHUNK):
        batch = derived[start : start + CHUNK]
        stmt = insert(cast("Any", Skill.__table__)).values(
            [
                {"id": uuid.uuid4(), "slug": f"__tmp_{r['nos_code']}", "name_en": "", **r}
                for r in batch
            ]
        )
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["nos_code"], set_={"nsqf_level": stmt.excluded.nsqf_level}
            )
        )
    report.levels_derived = len(derived)

    # -------------------------------------------------------- model curricula
    mc_rows = []
    for mc, _ in mc_by_key.values():
        mc_rows.append(
            {
                "id": uuid.uuid4(),
                "qp_code": mc.qp_code,
                "mc_version": mc.version,
                "qp_id": next((i for (c, _v), i in qp_ids.items() if c == mc.qp_code), None),
                "job_role_en": mc.job_role,
                "nsqf_level": mc.nsqf_level,
                "status": mc.status,
                "total_minutes": mc.total_minutes,
                "document_ref": mc.document_ref,
            }
        )
    report.model_curricula = await _chunked_upsert(
        db, ModelCurriculum.__table__, mc_rows, ["qp_code", "mc_version"]
    )
    await db.flush()

    mc_ids = {
        (c, v): i
        for c, v, i in (
            await db.execute(
                select(ModelCurriculum.qp_code, ModelCurriculum.mc_version, ModelCurriculum.id)
            )
        ).all()
    }
    mc_skill_rows, seen_mc = [], set()
    for mc, _ in mc_by_key.values():
        mc_id = mc_ids.get((mc.qp_code, mc.version))
        if mc_id is None:
            continue
        for unit in mc.skills:
            skill_id = skill_ids.get(unit.nos_code)
            if skill_id is None or (mc_id, skill_id) in seen_mc:
                continue
            seen_mc.add((mc_id, skill_id))
            mc_skill_rows.append(
                {
                    "id": uuid.uuid4(),
                    "curriculum_id": mc_id,
                    "skill_id": skill_id,
                    "theory_minutes": unit.theory_minutes,
                    "practical_minutes": unit.practical_minutes,
                    "ojt_minutes": unit.ojt_minutes,
                    "total_minutes": unit.total_minutes,
                }
            )
    report.mc_skills = await _chunked_upsert(
        db, ModelCurriculumSkill.__table__, mc_skill_rows, ["curriculum_id", "skill_id"]
    )

    await db.commit()
    return report
