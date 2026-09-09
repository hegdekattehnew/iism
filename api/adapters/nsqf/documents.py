"""Source-document parsing: one raw document in, one normalised record out.

Kept separate from any particular transport so that every source parses the
corpus identically. `MongoNsqfSource` streams these from the database and
`JsonFileNsqfSource` reads them from a file, but neither owns the rules -- which
is what makes a fixture-driven test exercise the real parsing rather than a
second implementation of it that can drift out of agreement with this one.

Every quirk of the national feed is absorbed here: `compulsoryNos` as a flat
list against grouped `electiveNos`/`optionalNos`, the source's own spelling of
"compulsary", `HH:MM` durations, and `credits` of "TBD".

**One trap deserves naming, because it already produced a wrong conclusion: the
collections use different names for the same concept.** A standard states its
NSQF level in `nsqf`; a qualification states it in `nsqfLevel`. Checking the
qualification's spelling against standards returns zero every time, which reads
exactly like "a NOS has no level" -- and all 27,538 carry one. The same applies
to `type` against `nosType`, and `Sectors` against `sectors`. Never conclude a
field is absent from one collection using another collection's spelling.
"""

import re
from decimal import Decimal
from typing import Any

from api.adapters.nsqf.normalise import (
    NormalisationError,
    clean_text,
    parse_credits,
    parse_decimal,
    parse_hhmm_to_minutes,
    parse_level,
    parse_nco_codes,
)
from api.adapters.nsqf.records import (
    DistrictRecord,
    EntryRouteRecord,
    McRecord,
    McSkillHours,
    NosRecord,
    OccupationRecord,
    PcRecord,
    PerformanceElementRecord,
    QpNosLink,
    QpRecord,
    SectorRecord,
    StateRecord,
    SubDistrictRecord,
    SubSectorRecord,
    TextItemRecord,
)


def _as_dict(value: object) -> dict[str, Any]:
    """A nested field that is absent, null, or the wrong shape reads as empty.

    The feed is not schema-enforced: `sectors`, `occupation` and `status` are
    objects on most documents and missing on some. Treating a malformed nesting
    as empty keeps the surrounding qualification importable.
    """
    return value if isinstance(value, dict) else {}


def _text_items(raw: object, ref_key: str, text_key: str) -> tuple[TextItemRecord, ...]:
    out: list[TextItemRecord] = []
    if not isinstance(raw, list):
        return ()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        text = clean_text(entry.get(text_key))
        if not text:
            continue
        out.append(TextItemRecord(ref=clean_text(entry.get(ref_key)), text=text))
    return tuple(out)


def _performance_elements(doc: dict[str, Any]) -> tuple[PerformanceElementRecord, ...]:
    block = _as_dict(doc.get("PerformanceCriteria"))
    out: list[PerformanceElementRecord] = []
    for el in block.get("performanceCriteriaElements") or []:
        if not isinstance(el, dict):
            continue
        criteria: list[PcRecord] = []
        for pc in el.get("performanceCriteriaValues") or []:
            if not isinstance(pc, dict):
                continue
            desc = clean_text(pc.get("pcDescription"))
            if not desc:
                continue
            criteria.append(
                PcRecord(
                    pc_ref=clean_text(pc.get("pcID")),
                    description=desc,
                    theory=parse_decimal(pc.get("theory")),
                    practical=parse_decimal(pc.get("practical")),
                    viva=parse_decimal(pc.get("viva")),
                    ojt=parse_decimal(pc.get("ojt")),
                    total=parse_decimal(pc.get("total")),
                )
            )
        name = clean_text(el.get("element"))
        if not name and not criteria:
            continue
        out.append(
            PerformanceElementRecord(
                name=name or "(unnamed)",
                theory=parse_decimal(el.get("elementTheoryTotal")),
                practical=parse_decimal(el.get("elementPracTotal")),
                viva=parse_decimal(el.get("elementVivaTotal")),
                ojt=parse_decimal(el.get("elementOjtTotal")),
                total=parse_decimal(el.get("elementTotalMarks")),
                criteria=tuple(criteria),
            )
        )
    return tuple(out)


def nos_from_doc(doc: dict[str, Any]) -> NosRecord | None:
    code = clean_text(doc.get("unitCode"))
    if not code:
        return None

    try:
        # `nsqf` on a standard, `nsqfLevel` on a qualification. See the module note.
        raw_level = doc.get("nsqf") if doc.get("nsqf") is not None else doc.get("nsqfLevel")
        level = parse_level(raw_level)
    except NormalisationError:
        # An unreadable level does not invalidate the standard.
        level = None

    sectors = _as_dict(doc.get("Sectors") or doc.get("sectors"))
    subs = sectors.get("subSectors") or []
    sub = _as_dict(subs[0]) if subs else {}
    occupation = _as_dict(doc.get("Occupation") or doc.get("occupation"))

    return NosRecord(
        code=code,
        title=clean_text(doc.get("unitTitle")) or code,
        version=clean_text(doc.get("version")) or "1.0",
        # `type` on the standalone document (sparse), `nosType` on the copy
        # embedded in a qualification (near-complete).
        nos_type=clean_text(doc.get("type") or doc.get("nosType")),
        description=clean_text(
            doc.get("description") or (doc.get("nosDesc") or {}).get("description")
            if isinstance(doc.get("nosDesc"), dict)
            else doc.get("description")
        ),
        credits=parse_credits(doc.get("credits")),
        nsqf_level=level,
        sector_ref=clean_text(sectors.get("sectorID")),
        sector_name=clean_text(sectors.get("sectorName")),
        sub_sector_ref=clean_text(sub.get("subSectorID") or sectors.get("subSectorID")),
        sub_sector_name=clean_text(sub.get("subSectorName") or sectors.get("subSectorName")),
        occupation_ref=clean_text(occupation.get("occupationID")),
        occupation_name=clean_text(occupation.get("occupationDesc")),
        elements=_performance_elements(doc),
        knowledge=_text_items(doc.get("KnowledgeAndUnderstanding"), "kpID", "knowledgeParam"),
        generic_skills=_text_items(doc.get("Skills"), "skillID", "skillCrt"),
    )


# "3 Years", "1.5 years", "6 Months", "NA".
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*(year|yr|month|mon)", re.I)


def _experience_years(desc: str | None) -> Decimal | None:
    """Turn an experience requirement into years. "NA" and anything unreadable
    stay None rather than becoming zero -- "no experience stated" and "no
    experience required" are different claims."""
    if not desc:
        return None
    match = _YEARS.search(desc)
    if match is None:
        return None
    value = Decimal(match.group(1))
    return value / 12 if match.group(2).lower().startswith("mon") else value


def _entry_routes(doc: dict[str, Any]) -> tuple[EntryRouteRecord, ...]:
    routes: list[EntryRouteRecord] = []
    raw = doc.get("minEduQual")
    if not isinstance(raw, list):
        return ()
    for route in raw:
        if not isinstance(route, dict):
            continue
        exp = _as_dict(route.get("expReq"))
        exp_desc = clean_text(exp.get("expReqDesc"))
        quals = route.get("eduQual") or []
        # A route with an experience requirement but no education entry is still
        # a route; keep it rather than losing the requirement.
        entries: list[dict[str, Any]] = [q for q in quals if isinstance(q, dict)] or [{}]
        for qual in entries:
            routes.append(
                EntryRouteRecord(
                    education_ref=clean_text(qual.get("minEduQualID")),
                    education_desc=clean_text(qual.get("minEduQualDesc")),
                    education_specialisation=clean_text(qual.get("minSpecialization")),
                    experience_ref=clean_text(exp.get("expReqID")),
                    experience_desc=exp_desc,
                    experience_specialisation=clean_text(exp.get("minSpecialization")),
                    experience_years=_experience_years(exp_desc),
                )
            )
    return tuple(routes)


def _assessment_weights(doc: dict[str, Any]) -> dict[str, tuple[Any, int | None]]:
    """NOS code -> (weightage, total marks) from the qualification's blueprint.

    `assmtCrt` states what each unit is worth inside the qualification -- 70/10/10
    and the like. It is the only importance weight in this system that is sourced
    rather than hand-authored.
    """
    out: dict[str, tuple[Any, int | None]] = {}
    crt = _as_dict(doc.get("assmtCrt"))
    for key in ("compulsoryNos", "electiveNos", "optionalNos"):
        for entry in _as_dict(crt.get(key)).get("assmtOutcm") or []:
            if not isinstance(entry, dict):
                continue
            nos_code = clean_text(entry.get("nosCode"))
            if not nos_code:
                continue
            marks = entry.get("totMarks")
            out[nos_code] = (
                parse_decimal(entry.get("weightage")),
                int(marks)
                if isinstance(marks, (int, float)) and not isinstance(marks, bool)
                else None,
            )
    return out


def qp_from_doc(doc: dict[str, Any]) -> QpRecord | None:
    code = clean_text(doc.get("qpCode"))
    if not code:
        return None

    links: list[QpNosLink] = []
    embedded: list[NosRecord] = []
    weights = _assessment_weights(doc)

    # Compulsory units are a flat list.
    for entry in doc.get("compulsoryNos") or []:
        if not isinstance(entry, dict):
            continue
        nos = nos_from_doc(entry)
        if nos is None:
            continue
        embedded.append(nos)
        weight, marks = weights.get(nos.code, (None, None))
        links.append(
            QpNosLink(
                nos_code=nos.code,
                requirement="compulsory",
                weightage=weight,
                total_marks=marks,
            )
        )

    # Elective and optional units are nested inside named groups, and flattening
    # them without keeping the group name would lose the "choose one of these"
    # structure entirely -- presenting an option as a requirement.
    for field, requirement in (("electiveNos", "elective"), ("optionalNos", "optional")):
        for group in doc.get(field) or []:
            if not isinstance(group, dict):
                continue
            group_name = clean_text(group.get("name"))
            for entry in group.get("nos") or []:
                if not isinstance(entry, dict):
                    continue
                nos = nos_from_doc(entry)
                if nos is None:
                    continue
                embedded.append(nos)
                weight, marks = weights.get(nos.code, (None, None))
                links.append(
                    QpNosLink(
                        nos_code=nos.code,
                        requirement=requirement,
                        group_name=group_name,
                        weightage=weight,
                        total_marks=marks,
                    )
                )

    sectors = _as_dict(doc.get("sectors"))
    sub_sectors = sectors.get("subSectors") or []
    sub = _as_dict(sub_sectors[0]) if sub_sectors else {}
    occupation = _as_dict(doc.get("occupation"))
    status = _as_dict(doc.get("status"))

    try:
        level = parse_level(doc.get("nsqfLevel"))
    except NormalisationError:
        # A QP with an unreadable level is still a real qualification; the level
        # is simply unknown rather than the record invalid.
        level = None

    crt = _as_dict(doc.get("assmtCrt"))
    qp_marks = crt.get("totMarks")
    aligned = doc.get("alignedTo")
    nco_codes = parse_nco_codes(aligned)
    # `alignedTo` held something, but nothing resembling an occupation code --
    # 793 values are free text such as "(CNC Operator)".
    nco_unparsed = bool(clean_text(aligned)) and not nco_codes

    total_hours = doc.get("totalHoursQplevel")
    return QpRecord(
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
        occupation_ref=clean_text(occupation.get("occupationID")),
        nco_codes=tuple(nco_codes),
        nco_unparsed=nco_unparsed,
        entry_routes=_entry_routes(doc),
        total_marks=(
            int(qp_marks)
            if isinstance(qp_marks, (int, float)) and not isinstance(qp_marks, bool)
            else None
        ),
        min_pass_percent=parse_decimal(crt.get("minPassPrcnt") or crt.get("minPassPercentage")),
        credits=parse_credits(doc.get("credits")),
        nos_links=tuple(links),
        embedded_nos=tuple(embedded),
    )


def mc_from_doc(doc: dict[str, Any]) -> McRecord | None:
    qp_code = clean_text(doc.get("qpCode"))
    if not qp_code:
        return None

    nos_block = _as_dict(doc.get("nos"))
    hours: list[McSkillHours] = []
    blank_codes = 0

    # Three lists, not one. The key really is spelled "compulsary" in the source,
    # and elective/optional carry a further ~750 usable entries that reading only
    # the first list would silently discard.
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
            # unitCode is present but blank on most records. Counted rather than
            # dropped in silence, and rather than raised -- one aggregate number
            # is honest without burying real failures under thousands of lines.
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
            # Unreadable durations do not invalidate the curriculum; the unit is
            # recorded without hours.
            hours.append(McSkillHours(nos_code=code))

    try:
        total = parse_hhmm_to_minutes(doc.get("grandTotal"))
    except NormalisationError:
        total = None
    try:
        level = parse_level(doc.get("nsqfLevel"))
    except NormalisationError:
        level = None

    return McRecord(
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


# ---------------------------------------------------------------- geography


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _flag(value: object) -> bool:
    return value is True


def _district_from_embedded(doc: dict[str, Any]) -> DistrictRecord | None:
    """A district as it appears inside a state document.

    This is the only place a district is tied to a state, and the only place the
    policy flags exist — the standalone `district` collection carries neither.
    """
    code = _as_int(doc.get("code") or doc.get("districtCode"))
    if code is None:
        return None
    return DistrictRecord(
        code=code,
        name=clean_text(doc.get("name") or doc.get("districtName")),
        short_name=clean_text(doc.get("short_name")),
        is_aspirational=_flag(doc.get("isAsprirational")),  # sic, as in the source
        is_border=_flag(doc.get("isBorder")),
        is_tribal=_flag(doc.get("isTribal")),
        is_lwe=_flag(doc.get("isLwe")),
        is_north_east=_flag(doc.get("northEast")),
        is_rural_or_municipal=_flag(doc.get("ruralOrMunicipal")),
    )


def state_from_doc(doc: dict[str, Any]) -> StateRecord | None:
    code = _as_int(doc.get("stateCode"))
    name = clean_text(doc.get("state"))
    if code is None or not name:
        return None
    districts = [
        d
        for d in (
            _district_from_embedded(x) for x in (doc.get("districts") or []) if isinstance(x, dict)
        )
        if d is not None
    ]
    return StateRecord(
        code=code,
        name=name,
        ncvet_code=clean_text(doc.get("stateCodeForNCVET")),
        status=clean_text(doc.get("status")),
        districts=tuple(districts),
    )


def district_from_doc(doc: dict[str, Any]) -> DistrictRecord | None:
    """The standalone district document — used only for its sub-districts.

    Eight of 767 carry no name. They are kept: the code is still a valid
    reference, and dropping them would silently break any row pointing at one.
    """
    code = _as_int(doc.get("districtCode"))
    if code is None:
        return None
    subs = []
    for x in doc.get("subDistricts") or []:
        if not isinstance(x, dict):
            continue
        sub_name = clean_text(x.get("name") or x.get("subDistrictName"))
        if not sub_name:
            continue
        subs.append(
            SubDistrictRecord(
                code=_as_int(x.get("code") or x.get("subDistrictCode")), name=sub_name
            )
        )
    return DistrictRecord(
        code=code,
        name=clean_text(doc.get("district") or doc.get("districtName") or doc.get("name")),
        short_name=clean_text(doc.get("short_name")),
        sub_districts=tuple(subs),
    )


# ------------------------------------------------- sectors & awarding bodies


def sector_from_doc(doc: dict[str, Any]) -> SectorRecord | None:
    ref = clean_text(doc.get("sectorID"))
    code = clean_text(doc.get("sectorCode") or doc.get("sscCode"))
    name = clean_text(doc.get("sector") or doc.get("nameOfSector"))
    if not (ref and code and name):
        return None

    subs = []
    for x in doc.get("subSectors") or []:
        if not isinstance(x, dict):
            continue
        s_ref, s_name = clean_text(x.get("subSectorID")), clean_text(x.get("subSectorName"))
        if s_ref and s_name:
            subs.append(SubSectorRecord(ref=s_ref, name=s_name))

    occs = []
    for x in doc.get("occupations") or []:
        if not isinstance(x, dict):
            continue
        o_ref, o_name = clean_text(x.get("occupationID")), clean_text(x.get("occupationDesc"))
        if o_ref and o_name:
            occs.append(
                OccupationRecord(ref=o_ref, code=clean_text(x.get("occupationCode")), name=o_name)
            )

    return SectorRecord(
        ref=ref,
        code=code.upper(),
        name=name,
        is_awarding_body=(clean_text(doc.get("type")) or "").lower().replace(" ", "")
        == "awardingbody",
        logo_url=clean_text(doc.get("sectorLogo")),
        sub_sectors=tuple(subs),
        occupations=tuple(occs),
    )
