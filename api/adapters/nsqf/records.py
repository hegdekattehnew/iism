"""The normalised shape the importer consumes.

The adapter absorbs MongoDB's document layout here so nothing downstream knows
or cares where the corpus came from (ADR-017, ADR-034).
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PcRecord:
    """One assessable statement, with its marks."""

    pc_ref: str | None
    description: str
    theory: Decimal | None = None
    practical: Decimal | None = None
    viva: Decimal | None = None
    ojt: Decimal | None = None
    total: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PerformanceElementRecord:
    name: str
    theory: Decimal | None = None
    practical: Decimal | None = None
    viva: Decimal | None = None
    ojt: Decimal | None = None
    total: Decimal | None = None
    criteria: tuple[PcRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TextItemRecord:
    """A knowledge parameter or a generic skill criterion: a ref and a string."""

    ref: str | None
    text: str


@dataclass(frozen=True, slots=True)
class NosRecord:
    code: str
    title: str
    version: str
    nos_type: str | None = None
    description: str | None = None
    credits: Decimal | None = None
    # A NOS carries its own level, in a field the source spells `nsqf`. A
    # qualification spells the same concept `nsqfLevel`; checking that name
    # against a standard returns nothing, which is how this was once wrongly
    # recorded as absent.
    nsqf_level: Decimal | None = None
    # Standards state their own sector and occupation, which is what makes a
    # unit belonging to no current qualification still placeable.
    sector_ref: str | None = None
    sector_name: str | None = None
    sub_sector_ref: str | None = None
    sub_sector_name: str | None = None
    occupation_ref: str | None = None
    occupation_name: str | None = None
    # The content layer: what the standard actually says.
    elements: tuple[PerformanceElementRecord, ...] = field(default_factory=tuple)
    knowledge: tuple[TextItemRecord, ...] = field(default_factory=tuple)
    generic_skills: tuple[TextItemRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QpNosLink:
    nos_code: str
    requirement: str  # compulsory | elective | optional
    group_name: str | None = None
    # What this unit is worth inside this qualification, from the source's own
    # assessment blueprint. A sourced importance weight.
    weightage: Decimal | None = None
    total_marks: int | None = None


@dataclass(frozen=True, slots=True)
class EntryRouteRecord:
    """One way in to a qualification: an education requirement plus an
    experience requirement.

    `minEduQual` is an array of alternative routes, not a description -- a
    qualification typically publishes several, and 4,564 of them do. Each route
    pairs an education requirement with an experience requirement, so
    "12th grade Pass with no experience" and "10th grade pass with 3 years" are
    two routes to the same qualification, and a candidate needs to satisfy only
    one of them.
    """

    education_ref: str | None
    education_desc: str | None
    education_specialisation: str | None
    experience_ref: str | None
    experience_desc: str | None
    experience_specialisation: str | None
    experience_years: Decimal | None


@dataclass(frozen=True, slots=True)
class QpRecord:
    code: str
    version: str
    name: str
    job_role: str | None
    nsqf_level: Decimal | None
    status: str | None
    total_hours: int | None
    sector_ref: str | None
    sector_name: str | None
    sub_sector_ref: str | None
    sub_sector_name: str | None
    occupation: str | None
    occupation_ref: str | None = None
    # NCO-2015 codes this qualification aligns to. Plural: the source stores
    # several comma-separated in one string.
    nco_codes: tuple[str, ...] = field(default_factory=tuple)
    # True when `alignedTo` held something but no code could be read from it --
    # counted and reported rather than stored as if it were a classification.
    nco_unparsed: bool = False
    entry_routes: tuple[EntryRouteRecord, ...] = field(default_factory=tuple)
    total_marks: int | None = None
    min_pass_percent: Decimal | None = None
    credits: Decimal | None = None
    nos_links: tuple[QpNosLink, ...] = field(default_factory=tuple)
    # NOS embedded in the QP but absent from the nos collection are still real
    # units; the importer creates skills for them.
    embedded_nos: tuple[NosRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class McSkillHours:
    nos_code: str
    theory_minutes: int | None = None
    practical_minutes: int | None = None
    ojt_minutes: int | None = None
    total_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class McRecord:
    qp_code: str
    version: str
    job_role: str | None
    nsqf_level: Decimal | None
    status: str | None
    total_minutes: int | None
    document_ref: str | None
    skills: tuple[McSkillHours, ...] = field(default_factory=tuple)
    # Entries whose unitCode is present but blank in the source, so the hours
    # cannot be attached to any unit. A data-quality fact, surfaced not hidden.
    blank_unit_codes: int = 0


@dataclass(slots=True)
class ImportProblem:
    """A record that could not be imported, and why. Collected and reported
    rather than raised, so one malformed document does not abort 30,000."""

    collection: str
    identifier: str
    reason: str


# ---------------------------------------------------------------- geography


@dataclass(frozen=True, slots=True)
class SubDistrictRecord:
    code: int | None
    name: str


@dataclass(frozen=True, slots=True)
class DistrictRecord:
    """A district, with the policy attributes government schemes target.

    The flags live only on the copy embedded in a state document; the standalone
    `district` collection carries neither them nor any state reference at all.
    """

    code: int
    name: str | None
    short_name: str | None = None
    is_aspirational: bool = False
    is_border: bool = False
    is_tribal: bool = False
    is_lwe: bool = False
    is_north_east: bool = False
    is_rural_or_municipal: bool = False
    sub_districts: tuple[SubDistrictRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class StateRecord:
    code: int
    name: str
    ncvet_code: str | None = None
    status: str | None = None
    districts: tuple[DistrictRecord, ...] = field(default_factory=tuple)


# ------------------------------------------------- sectors & awarding bodies


@dataclass(frozen=True, slots=True)
class OccupationRecord:
    """Occupation codes are two digits and *sector-local* ('01', '02', '99').

    The code alone is not unique across the corpus; `ref` (the source's
    occupationID) is. They are not NCO codes — the overlap with NCO is four
    values and coincidental.
    """

    ref: str
    code: str | None
    name: str


@dataclass(frozen=True, slots=True)
class SubSectorRecord:
    ref: str
    name: str


@dataclass(frozen=True, slots=True)
class SectorRecord:
    """One row of the `sectors` collection, which holds two populations.

    45 documents are true sectors carrying sub-sectors and occupations; 68 are
    typed 'Awarding Body' and are organisations rather than sectors. Both are
    keyed by `code`, and that code is the prefix of every qualification and
    standard the body owns — which is what resolves 99% of the corpus to an
    owner.
    """

    ref: str
    code: str
    name: str
    is_awarding_body: bool
    logo_url: str | None = None
    sub_sectors: tuple[SubSectorRecord, ...] = field(default_factory=tuple)
    occupations: tuple[OccupationRecord, ...] = field(default_factory=tuple)
