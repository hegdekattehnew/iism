"""Projects the NSQF corpus from its source of record into PostgreSQL.

MongoDB is master (ADR-034); this rebuilds the operational taxonomy from it and
is safe to re-run. Everything is keyed on the national codes, so a second run
updates rather than duplicates.

Only the newest version of each code is projected. Prior versions stay in
MongoDB — that is precisely what making it the source of record buys.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, cast

from sqlalchemy import delete, select, update
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
from api.modules.geography.models import District, State, SubDistrict
from api.modules.marketplace.models import (
    CandidatePreferredLocation,
    CandidateProfile,
    Job,
)
from api.modules.skills.content import (
    GenericCriterion,
    KnowledgeParameter,
    PerformanceCriterion,
    PerformanceElement,
)
from api.modules.skills.hierarchy import (
    AwardingBody,
    ModelCurriculum,
    Occupation,
    QpEntryRoute,
    QpNcoCode,
    QpSkill,
    QualificationPack,
    Sector,
    SubSector,
)
from api.modules.skills.models import Skill

CHUNK = 500
# The content layer is ~900,000 rows; at CHUNK it would be 1,800 statements.
CONTENT_CHUNK = 2000


@dataclass
class ImportReport:
    sectors: int = 0
    sub_sectors: int = 0
    occupations: int = 0
    skills: int = 0
    qualification_packs: int = 0
    qp_skills: int = 0
    model_curricula: int = 0
    states: int = 0
    districts: int = 0
    sub_districts: int = 0
    awarding_bodies: int = 0
    nco_codes: int = 0
    entry_routes: int = 0
    locations_resolved: int = 0
    nco_unparsed: int = 0
    performance_elements: int = 0
    performance_criteria: int = 0
    knowledge_params: int = 0
    generic_criteria: int = 0
    mc_entries_without_code: int = 0
    documents_without_code: int = 0
    problems: list[ImportProblem] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"sectors={self.sectors} sub_sectors={self.sub_sectors} "
            f"occupations={self.occupations} skills={self.skills} "
            f"qps={self.qualification_packs} qp_skills={self.qp_skills} "
            f"curricula={self.model_curricula} "
            f"states={self.states} districts={self.districts} "
            f"sub_districts={self.sub_districts} bodies={self.awarding_bodies} "
            f"nco={self.nco_codes} nco_unparsed={self.nco_unparsed} "
            f"entry_routes={self.entry_routes} "
            f"locations_resolved={self.locations_resolved} "
            f"elements={self.performance_elements} criteria={self.performance_criteria} "
            f"knowledge={self.knowledge_params} generic={self.generic_criteria} "
            f"mc_entries_without_code={self.mc_entries_without_code} "
            f"documents_without_code={self.documents_without_code} "
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


def _occupation_for(
    index: dict[tuple[uuid.UUID, str], uuid.UUID],
    sector_id: uuid.UUID | None,
    ref: str | None,
) -> uuid.UUID | None:
    """Resolve an occupation, which is only identifiable within its sector."""
    if sector_id is None or not ref:
        return None
    return index.get((sector_id, ref))


def _code_prefix(code: str) -> str:
    """`LSC/Q6101` -> `LSC`. The owning body's code, and the join that resolves
    99% of the corpus to an owner."""
    return code.split("/", 1)[0].strip().upper()


def _without_content(nos: NosRecord) -> NosRecord:
    """The same standard with its content dropped, for the in-memory index."""
    return replace(nos, elements=(), knowledge=(), generic_skills=())


async def _bulk_insert(db: AsyncSession, table: Any, rows: list[dict[str, Any]]) -> int:
    """Plain batched INSERT, no conflict handling.

    Content is deleted and rewritten wholesale rather than upserted. It is
    entirely derived from the source and owned by this importer, and a revised
    standard with fewer criteria would otherwise leave the surplus rows behind
    -- a unit would appear to require things its current version dropped.
    """
    written = 0
    for start in range(0, len(rows), CONTENT_CHUNK):
        batch = rows[start : start + CONTENT_CHUNK]
        if batch:
            await db.execute(insert(table).values(batch))
            written += len(batch)
    return written


async def _import_criteria(
    db: AsyncSession,
    source: NsqfSource,
    skill_ids: dict[str, uuid.UUID],
    current_versions: dict[str, str],
) -> tuple[int, int]:
    """Performance elements and their criteria, in a second pass over the source."""
    await db.execute(delete(PerformanceElement))  # criteria cascade
    await db.flush()

    elements: list[dict[str, Any]] = []
    criteria: list[dict[str, Any]] = []
    seen: set[str] = set()
    async for nos in source.iter_nos():
        skill_id = skill_ids.get(nos.code)
        # Only the version that became the skill row contributes content.
        if skill_id is None or current_versions.get(nos.code) != nos.version:
            continue
        if nos.code in seen or not nos.elements:
            continue
        seen.add(nos.code)
        for e_ordinal, element in enumerate(nos.elements):
            element_id = uuid.uuid4()
            elements.append(
                {
                    "id": element_id,
                    "skill_id": skill_id,
                    "ordinal": e_ordinal,
                    "name_en": element.name,
                    "theory_marks": element.theory,
                    "practical_marks": element.practical,
                    "viva_marks": element.viva,
                    "ojt_marks": element.ojt,
                    "total_marks": element.total,
                }
            )
            for c_ordinal, pc in enumerate(element.criteria):
                criteria.append(
                    {
                        "id": uuid.uuid4(),
                        "element_id": element_id,
                        "ordinal": c_ordinal,
                        # Kept for traceability only: pcID repeats within a unit
                        # in a small number of standards, so it is never a key.
                        "pc_ref": pc.pc_ref,
                        "description_en": pc.description,
                        "theory_marks": pc.theory,
                        "practical_marks": pc.practical,
                        "viva_marks": pc.viva,
                        "ojt_marks": pc.ojt,
                        "total_marks": pc.total,
                    }
                )
    written_elements = await _bulk_insert(db, PerformanceElement.__table__, elements)
    await db.flush()
    written_criteria = await _bulk_insert(db, PerformanceCriterion.__table__, criteria)
    return written_elements, written_criteria


async def _import_text_content(
    db: AsyncSession,
    source: NsqfSource,
    skill_ids: dict[str, uuid.UUID],
    current_versions: dict[str, str],
) -> tuple[int, int]:
    """Knowledge parameters and generic skill criteria."""
    await db.execute(delete(KnowledgeParameter))
    await db.execute(delete(GenericCriterion))
    await db.flush()

    knowledge: list[dict[str, Any]] = []
    generic: list[dict[str, Any]] = []
    seen: set[str] = set()
    async for nos in source.iter_nos():
        skill_id = skill_ids.get(nos.code)
        if skill_id is None or current_versions.get(nos.code) != nos.version:
            continue
        if nos.code in seen:
            continue
        seen.add(nos.code)
        for ordinal, item in enumerate(nos.knowledge):
            knowledge.append(
                {
                    "id": uuid.uuid4(),
                    "skill_id": skill_id,
                    "ordinal": ordinal,
                    "kp_ref": item.ref,
                    "text_en": item.text,
                }
            )
        for ordinal, item in enumerate(nos.generic_skills):
            generic.append(
                {
                    "id": uuid.uuid4(),
                    "skill_id": skill_id,
                    "ordinal": ordinal,
                    "gs_ref": item.ref,
                    "text_en": item.text,
                }
            )
    return (
        await _bulk_insert(db, KnowledgeParameter.__table__, knowledge),
        await _bulk_insert(db, GenericCriterion.__table__, generic),
    )


# Free text as it was seeded against the master's own spelling. Only entries
# that are genuinely the same place belong here -- this is a spelling bridge,
# not a way to force a match.
_DISTRICT_ALIASES = {
    "bengaluru": "bengaluru urban",
    "bangalore": "bengaluru urban",
}


async def _backfill_geography(db: AsyncSession) -> int:
    """Point existing free-text locations at the geography master.

    The text columns stay: not every value resolves, and a location we cannot
    resolve is still a location. This only fills the foreign key beside it.
    """
    states = {
        name.strip().lower(): sid
        for name, sid in (await db.execute(select(State.name, State.id))).all()
    }
    districts: dict[str, uuid.UUID] = {}
    for name, did in (await db.execute(select(District.name, District.id))).all():
        if name:
            districts.setdefault(name.strip().lower(), did)

    def resolve_district(value: str | None) -> uuid.UUID | None:
        if not value:
            return None
        key = value.strip().lower()
        return districts.get(key) or districts.get(_DISTRICT_ALIASES.get(key, ""))

    resolved = 0
    for model, state_col, district_col in (
        (Job, "location_state", "location_district"),
        (CandidateProfile, "location_state", "location_district"),
        (CandidatePreferredLocation, "state", "district"),
    ):
        rows = (
            await db.execute(
                select(model.id, getattr(model, state_col), getattr(model, district_col))
            )
        ).all()
        for row_id, state_name, district_name in rows:
            state_id = states.get((state_name or "").strip().lower())
            district_id = resolve_district(district_name)
            if state_id is None and district_id is None:
                continue
            await db.execute(
                update(model)
                .where(model.id == row_id)
                .values(state_id=state_id, district_id=district_id)
            )
            resolved += 1
    return resolved


async def import_nsqf(db: AsyncSession, source: NsqfSource) -> ImportReport:
    report = ImportReport()

    # ---------------------------------------------------------------- collect
    # Content is stripped here and re-read in a second pass: holding ~900,000
    # criteria, knowledge parameters and generic skills in memory alongside
    # everything else is hundreds of megabytes for no benefit.
    nos_by_code: dict[str, tuple[NosRecord, str]] = {}
    async for nos in source.iter_nos():
        _latest(nos_by_code, nos.code, _without_content(nos), nos.version)

    qp_by_code: dict[str, tuple[QpRecord, str]] = {}
    async for qp in source.iter_qps():
        _latest(qp_by_code, qp.code, qp, qp.version)
        # A NOS embedded in a QP but absent from the nos collection is still a
        # real unit; without this it would vanish and the QP would look empty.
        for embedded in qp.embedded_nos:
            stripped = _without_content(embedded)
            if embedded.code not in nos_by_code:
                _latest(nos_by_code, embedded.code, stripped, embedded.version)
                continue
            # The standalone document usually wins on version but states `type`
            # on only 3,952 of 27,538 records, where the embedded copy states
            # `nosType` on almost all of them. Take the type from whichever has
            # it rather than losing it to version precedence -- Core vs Non-Core
            # is what elective grouping means.
            current, current_version = nos_by_code[embedded.code]
            if current.nos_type is None and embedded.nos_type is not None:
                nos_by_code[embedded.code] = (
                    replace(current, nos_type=embedded.nos_type),
                    current_version,
                )

    mc_by_key: dict[str, tuple[McRecord, str]] = {}
    async for mc in source.iter_model_curricula():
        report.mc_entries_without_code += mc.blank_unit_codes
        _latest(mc_by_key, f"{mc.qp_code}", mc, mc.version)

    state_records = [st async for st in source.iter_states()]
    district_records = [d async for d in source.iter_districts()]
    sector_records = [sec async for sec in source.iter_sectors()]

    # Captured here, at the end of the collect phase, because the content passes
    # below iterate the standards again and would count each skipped document
    # once per pass.
    report.documents_without_code = getattr(source, "skipped_documents", 0)

    # -------------------------------------------------------------- geography
    # Districts come from the array embedded in each state: that array is the
    # only place a district is tied to a state, and the only place the policy
    # flags exist. The standalone collection contributes sub-districts alone.
    state_rows = [
        {
            "id": uuid.uuid4(),
            "state_code": st.code,
            "name": st.name,
            "slug": slugify(st.name),
            "ncvet_code": st.ncvet_code,
            "status": st.status,
        }
        for st in state_records
    ]
    report.states = await _chunked_upsert(db, State.__table__, state_rows, ["state_code"])
    await db.flush()
    state_ids: dict[int, uuid.UUID] = {
        row[0]: row[1] for row in (await db.execute(select(State.state_code, State.id))).all()
    }

    district_rows: dict[int, dict[str, Any]] = {}
    for st in state_records:
        parent = state_ids.get(st.code)
        if parent is None:  # pragma: no cover - every state was just written
            continue
        for d in st.districts:
            name = d.name
            district_rows[d.code] = {
                "id": uuid.uuid4(),
                "district_code": d.code,
                "state_id": parent,
                "name": name,
                # Slugged with the code appended: district names repeat across
                # states (there is more than one Aurangabad).
                "slug": f"{slugify(name)}-{d.code}" if name else None,
                "short_name": d.short_name,
                "is_aspirational": d.is_aspirational,
                "is_border": d.is_border,
                "is_tribal": d.is_tribal,
                "is_lwe": d.is_lwe,
                "is_north_east": d.is_north_east,
                "is_rural_or_municipal": d.is_rural_or_municipal,
            }
    report.districts = await _chunked_upsert(
        db, District.__table__, list(district_rows.values()), ["district_code"]
    )
    await db.flush()
    district_ids: dict[int, uuid.UUID] = {
        row[0]: row[1]
        for row in (await db.execute(select(District.district_code, District.id))).all()
    }

    sub_district_rows: dict[tuple[uuid.UUID, str], dict[str, Any]] = {}
    for d in district_records:
        parent_id = district_ids.get(d.code)
        if parent_id is None:
            report.problems.append(
                ImportProblem("district", str(d.code), "district is in no state's list")
            )
            continue
        for sub in d.sub_districts:
            sub_district_rows[(parent_id, sub.name)] = {
                "id": uuid.uuid4(),
                "district_id": parent_id,
                "code": sub.code,
                "name": sub.name,
            }
    report.sub_districts = await _chunked_upsert(
        db, SubDistrict.__table__, list(sub_district_rows.values()), ["district_id", "name"]
    )
    await db.flush()

    # ------------------------------------------- awarding bodies and sectors
    # One source collection holds two populations. Every row is an owning body,
    # keyed by a code that is also the prefix of everything it owns; the subset
    # carrying sub-sectors and occupations are the real sectors.
    body_rows: dict[str, dict[str, Any]] = {}
    for sec in sector_records:
        body_rows.setdefault(
            sec.code,
            {
                "id": uuid.uuid4(),
                "code": sec.code,
                "body_ref": sec.ref,
                "name_en": sec.name,
                "slug": f"{slugify(sec.name)}-{slugify(sec.code)}",
                "body_type": "awarding_body" if sec.is_awarding_body else "sector_skill_council",
                "logo_url": sec.logo_url,
            },
        )
    report.awarding_bodies = await _chunked_upsert(
        db, AwardingBody.__table__, list(body_rows.values()), ["code"]
    )
    await db.flush()
    body_ids: dict[str, uuid.UUID] = {
        row[0]: row[1]
        for row in (await db.execute(select(AwardingBody.code, AwardingBody.id))).all()
    }

    # Only rows that actually describe a sector become sectors. The other 68 are
    # organisations, and listing them as sectors would put "Medhavi Foundation"
    # in a sector filter.
    real_sectors = [sec for sec in sector_records if not sec.is_awarding_body]
    sector_rows = [
        {
            "id": uuid.uuid4(),
            "sector_ref": sec.ref,
            "sector_code": sec.code,
            "name_en": sec.name,
            "slug": slugify(sec.name),
            "logo_url": sec.logo_url,
            "awarding_body_id": body_ids.get(sec.code),
        }
        for sec in real_sectors
    ]
    report.sectors = await _chunked_upsert(db, Sector.__table__, sector_rows, ["sector_ref"])
    await db.flush()
    sector_ids: dict[str, uuid.UUID] = {
        row[0]: row[1] for row in (await db.execute(select(Sector.sector_ref, Sector.id))).all()
    }

    sub_rows: dict[tuple[uuid.UUID, str], dict[str, Any]] = {}
    occupation_rows: dict[tuple[uuid.UUID, str], dict[str, Any]] = {}
    for sec in real_sectors:
        parent = sector_ids.get(sec.ref)
        if parent is None:  # pragma: no cover
            continue
        for sub_sector in sec.sub_sectors:
            sub_rows[(parent, sub_sector.ref)] = {
                "id": uuid.uuid4(),
                "sector_id": parent,
                "sub_sector_ref": sub_sector.ref,
                "name_en": sub_sector.name,
            }
        for occ in sec.occupations:
            # Keyed on (sector, ref): occupationID is sector-local and reuses
            # "1", "2", "3" across forty-odd sectors.
            occupation_rows.setdefault(
                (parent, occ.ref),
                {
                    "id": uuid.uuid4(),
                    "occupation_ref": occ.ref,
                    "code": occ.code,
                    "sector_id": parent,
                    "name_en": occ.name,
                },
            )
    report.sub_sectors = await _chunked_upsert(
        db, SubSector.__table__, list(sub_rows.values()), ["sector_id", "sub_sector_ref"]
    )
    report.occupations = await _chunked_upsert(
        db, Occupation.__table__, list(occupation_rows.values()), ["sector_id", "occupation_ref"]
    )
    await db.flush()

    sub_ids = {
        (sid, ref): i
        for sid, ref, i in (
            await db.execute(select(SubSector.sector_id, SubSector.sub_sector_ref, SubSector.id))
        ).all()
    }
    occupation_ids: dict[tuple[uuid.UUID, str], uuid.UUID] = {
        (row[0], row[1]): row[2]
        for row in (
            await db.execute(select(Occupation.sector_id, Occupation.occupation_ref, Occupation.id))
        ).all()
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
                # The standard's own declared level. Previously derived as the
                # modal level of the containing qualifications, which left 4,730
                # units with none and contradicted 653 others.
                "nsqf_level": nos.nsqf_level,
                "sector_id": sector_ids.get(nos.sector_ref) if nos.sector_ref else None,
                "occupation_id": _occupation_for(
                    occupation_ids, sector_ids.get(nos.sector_ref or ""), nos.occupation_ref
                ),
                "awarding_body_id": body_ids.get(_code_prefix(nos.code)),
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
                "occupation_id": _occupation_for(occupation_ids, sector_id, qp.occupation_ref),
                "awarding_body_id": body_ids.get(_code_prefix(qp.code)),
                "total_marks": qp.total_marks,
                "min_pass_percent": qp.min_pass_percent,
                "credits": qp.credits,
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
    qp_counts: Counter[uuid.UUID] = Counter()
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
            qp_counts[skill_id] += 1
            link_rows.append(
                {
                    "id": uuid.uuid4(),
                    "qp_id": qp_id,
                    "skill_id": skill_id,
                    "requirement": link.requirement,
                    "group_name": link.group_name,
                    "nsqf_level": qp.nsqf_level,
                    "weightage": link.weightage,
                    "total_marks": link.total_marks,
                }
            )
            if qp.nsqf_level is not None:
                level_votes[skill_id].append(qp.nsqf_level)
    report.qp_skills = await _chunked_upsert(
        db, QpSkill.__table__, link_rows, ["qp_id", "skill_id"]
    )

    # qp_count is written for every skill, including the 4,784 that no current
    # qualification uses -- a re-import that drops a qualification must be able
    # to send a count back to zero, which a "write only what we found" pass
    # cannot do. The level is NOT derived here; it is the standard's own,
    # written with the skill row above.
    counts = [
        {"nos_code": code, "qp_count": qp_counts.get(sid, 0)} for code, sid in skill_ids.items()
    ]
    for start in range(0, len(counts), CHUNK):
        batch = counts[start : start + CHUNK]
        stmt = insert(cast("Any", Skill.__table__)).values(
            [
                {"id": uuid.uuid4(), "slug": f"__tmp_{r['nos_code']}", "name_en": "", **r}
                for r in batch
            ]
        )
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=["nos_code"], set_={"qp_count": stmt.excluded.qp_count}
            )
        )

    # ------------------------------------------------------------- NCO codes
    nco_rows = []
    for qp, _ in qp_by_code.values():
        qp_id = qp_ids.get((qp.code, qp.version))
        if qp_id is None:
            continue
        if qp.nco_unparsed:
            report.nco_unparsed += 1
        for ordinal, code in enumerate(qp.nco_codes):
            nco_rows.append(
                {"id": uuid.uuid4(), "qp_id": qp_id, "nco_code": code, "ordinal": ordinal}
            )
    report.nco_codes = await _chunked_upsert(
        db, QpNcoCode.__table__, nco_rows, ["qp_id", "nco_code"]
    )

    # ----------------------------------------------------------- entry routes
    route_rows = []
    for qp, _ in qp_by_code.values():
        qp_id = qp_ids.get((qp.code, qp.version))
        if qp_id is None:
            continue
        for ordinal, route in enumerate(qp.entry_routes):
            route_rows.append(
                {
                    "id": uuid.uuid4(),
                    "qp_id": qp_id,
                    "ordinal": ordinal,
                    "education_ref": route.education_ref,
                    "education_desc": route.education_desc,
                    "education_specialisation": route.education_specialisation,
                    "experience_ref": route.experience_ref,
                    "experience_desc": route.experience_desc,
                    "experience_specialisation": route.experience_specialisation,
                    "experience_years": route.experience_years,
                }
            )
    report.entry_routes = await _chunked_upsert(
        db, QpEntryRoute.__table__, route_rows, ["qp_id", "ordinal"]
    )

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

    # ---------------------------------------------------------------- content
    # Content must come from the version that became the skill row. Taking the
    # first sighting of a code instead would attach a superseded version's
    # criteria to the current standard.
    current_versions = {code: version for code, (_, version) in nos_by_code.items()}
    report.performance_elements, report.performance_criteria = await _import_criteria(
        db, source, skill_ids, current_versions
    )
    report.knowledge_params, report.generic_criteria = await _import_text_content(
        db, source, skill_ids, current_versions
    )

    report.locations_resolved = await _backfill_geography(db)

    await db.commit()
    return report
