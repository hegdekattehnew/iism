"""The normalised shape the importer consumes.

The adapter absorbs MongoDB's document layout here so nothing downstream knows
or cares where the corpus came from (ADR-017, ADR-034).
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class NosRecord:
    code: str
    title: str
    version: str
    nos_type: str | None = None
    description: str | None = None
    credits: Decimal | None = None


@dataclass(frozen=True, slots=True)
class QpNosLink:
    nos_code: str
    requirement: str  # compulsory | elective | optional
    group_name: str | None = None


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
