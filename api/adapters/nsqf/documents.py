"""Source-document parsing: one raw document in, one normalised record out.

Kept separate from any particular transport so that every source parses the
corpus identically. `MongoNsqfSource` streams these from the database and
`JsonFileNsqfSource` reads them from a file, but neither owns the rules -- which
is what makes a fixture-driven test exercise the real parsing rather than a
second implementation of it that can drift out of agreement with this one.

Every quirk of the national feed is absorbed here: `compulsoryNos` as a flat
list against grouped `electiveNos`/`optionalNos`, the source's own spelling of
"compulsary", `HH:MM` durations, `credits` of "TBD", and the fact that a NOS
carries no NSQF level.
"""

from typing import Any

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


def _as_dict(value: object) -> dict[str, Any]:
    """A nested field that is absent, null, or the wrong shape reads as empty.

    The feed is not schema-enforced: `sectors`, `occupation` and `status` are
    objects on most documents and missing on some. Treating a malformed nesting
    as empty keeps the surrounding qualification importable.
    """
    return value if isinstance(value, dict) else {}


def nos_from_doc(doc: dict[str, Any]) -> NosRecord | None:
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


def qp_from_doc(doc: dict[str, Any]) -> QpRecord | None:
    code = clean_text(doc.get("qpCode"))
    if not code:
        return None

    links: list[QpNosLink] = []
    embedded: list[NosRecord] = []

    # Compulsory units are a flat list.
    for entry in doc.get("compulsoryNos") or []:
        if not isinstance(entry, dict):
            continue
        nos = nos_from_doc(entry)
        if nos is None:
            continue
        embedded.append(nos)
        links.append(QpNosLink(nos_code=nos.code, requirement="compulsory"))

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
                links.append(
                    QpNosLink(
                        nos_code=nos.code,
                        requirement=requirement,
                        group_name=group_name,
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
