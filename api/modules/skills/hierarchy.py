"""The NSQF hierarchy above a skill (ADR-004, ADR-034).

Modelled against the real national corpus rather than the framework as
described. Three things the source dictates and the schema has to respect:

* **Level is stated in three places and they are three different facts.** A
  standard declares its own (`Skill.nsqf_level`), a qualification declares its
  own (`QualificationPack.nsqf_level`), and a unit sits at a particular level
  *inside* a given qualification (`QpSkill.nsqf_level`). An earlier version of
  this file claimed a NOS carries no level; that was wrong, and came from
  checking the qualification's field name (`nsqfLevel`) against standards, which
  spell it `nsqf`.
* **The owning body is derivable from the code prefix.** `AwardingBody.code` is
  the prefix of every qualification and standard the body owns, which resolves
  99% of the corpus. Sector Skill Councils and awarding bodies share one table
  because the source keeps them in one collection under one key.
* **Occupation codes are two digits and sector-local** (`01`, `99`), so the code
  alone is not unique. `occupation_ref` is the key. They are not NCO codes.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

# How a NOS is attached to a Qualification Pack. Elective and optional NOS are
# grouped under a named bundle in the source; `group_name` preserves that.
QP_REQUIREMENTS = ("compulsory", "elective", "optional")


BODY_TYPES = ("sector_skill_council", "awarding_body")


class AwardingBody(Base):
    """The organisation that owns a qualification or standard.

    Sector Skill Councils and awarding bodies live in one source collection under
    one key, and `code` is the prefix of everything they own -- `LSC` owns
    `LSC/Q6101` and `LSC/N2131`. That single fact resolves 4,529 of 4,576
    qualifications and 27,495 of 27,523 standards to an owner, which is why the
    prefix is the join and not the sparse `originSSC` field.
    """

    __tablename__ = "awarding_bodies"
    __table_args__ = (
        CheckConstraint(
            "body_type IN ('sector_skill_council', 'awarding_body')",
            name="ck_awarding_body_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    body_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    name_en: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text, default=None)
    slug: Mapped[str] = mapped_column(String(360), unique=True, index=True)
    body_type: Mapped[str] = mapped_column(String(32), default="awarding_body")
    logo_url: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Sector(Base):
    """A skilling sector. 43 of the 111 rows in the source master carry the
    sub-sectors and occupations that make them a real sector; the rest are
    awarding bodies, which land in `AwardingBody` instead."""

    __tablename__ = "sectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sector_ref: Mapped[str] = mapped_column(unique=True, index=True)
    # Also the qualification code prefix, and the key shared with AwardingBody.
    sector_code: Mapped[str | None] = mapped_column(String(32), index=True, default=None)
    name_en: Mapped[str] = mapped_column()
    name_hi: Mapped[str | None] = mapped_column(default=None)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), default=None)
    awarding_body_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("awarding_bodies.id", ondelete="SET NULL"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sub_sectors: Mapped[list["SubSector"]] = relationship(
        back_populates="sector", cascade="all, delete-orphan"
    )


class SubSector(Base):
    __tablename__ = "sub_sectors"
    __table_args__ = (
        UniqueConstraint("sector_id", "sub_sector_ref", name="uq_sub_sector_ref"),
        Index("ix_sub_sectors_sector_id", "sector_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"))
    sub_sector_ref: Mapped[str] = mapped_column()
    name_en: Mapped[str] = mapped_column()
    name_hi: Mapped[str | None] = mapped_column(default=None)

    sector: Mapped["Sector"] = relationship(back_populates="sub_sectors")


class Occupation(Base):
    """1,811 occupations from the sector master, every one carrying a code.

    **Both the code and the ref are sector-local.** `code` is two digits, and
    `occupation_ref` -- the source's occupationID -- reuses "1", "2", "3" across
    forty-odd sectors. So the key is the pair, and keying on the ref alone
    collapses 1,811 occupations into 529. The previous version of this table
    keyed on free text and had no stable identity at all.
    """

    __tablename__ = "occupations"
    __table_args__ = (
        UniqueConstraint("sector_id", "occupation_ref", name="uq_occupation_sector_ref"),
        Index("ix_occupations_sector_id", "sector_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occupation_ref: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str | None] = mapped_column(String(16), default=None)
    sector_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"))
    name_en: Mapped[str] = mapped_column(Text)
    name_hi: Mapped[str | None] = mapped_column(Text, default=None)


class QualificationPack(Base):
    """A national qualification: the thing that actually carries an NSQF level."""

    __tablename__ = "qualification_packs"
    __table_args__ = (
        UniqueConstraint("qp_code", "version", name="uq_qp_code_version"),
        CheckConstraint(
            "nsqf_level IS NULL OR (nsqf_level >= 1 AND nsqf_level <= 10)",
            name="ck_qp_nsqf_level",
        ),
        Index("ix_qp_sector_id", "sector_id"),
        Index("ix_qp_current_level", "is_current", "nsqf_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qp_code: Mapped[str] = mapped_column(index=True)
    version: Mapped[str] = mapped_column()
    slug: Mapped[str] = mapped_column(unique=True, index=True)

    name_en: Mapped[str] = mapped_column()
    name_hi: Mapped[str | None] = mapped_column(default=None)
    job_role_en: Mapped[str | None] = mapped_column(default=None)
    job_role_hi: Mapped[str | None] = mapped_column(default=None)

    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)
    status: Mapped[str | None] = mapped_column(default=None)
    total_hours: Mapped[int | None] = mapped_column(default=None)
    # Only the newest version of a qp_code is current; prior versions stay in
    # MongoDB, which is the source of record (ADR-034).
    is_current: Mapped[bool] = mapped_column(default=True)

    sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sectors.id", ondelete="SET NULL"), default=None
    )
    sub_sector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sub_sectors.id", ondelete="SET NULL"), default=None
    )
    occupation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("occupations.id", ondelete="SET NULL"), index=True, default=None
    )
    # Derived from the qualification code prefix, which resolves 99% of the corpus.
    awarding_body_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("awarding_bodies.id", ondelete="SET NULL"), index=True, default=None
    )

    # The assessment blueprint the qualification publishes.
    total_marks: Mapped[int | None] = mapped_column(default=None)
    min_pass_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    credits: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    sector: Mapped["Sector | None"] = relationship(lazy="selectin")
    skills: Mapped[list["QpSkill"]] = relationship(
        back_populates="qualification_pack", cascade="all, delete-orphan"
    )


class QpSkill(Base):
    """Qualification Pack → NOS.

    `nsqf_level` is copied from the QP deliberately. It is the authoritative
    level for this NOS *in this qualification*; the same NOS may appear in
    another QP at a different level, which is exactly why it cannot live on the
    skill row.
    """

    __tablename__ = "qp_skills"
    __table_args__ = (
        UniqueConstraint("qp_id", "skill_id", name="uq_qp_skill"),
        CheckConstraint(
            "requirement IN ('compulsory', 'elective', 'optional')",
            name="ck_qp_skill_requirement",
        ),
        Index("ix_qp_skills_skill_id", "skill_id"),
        Index("ix_qp_skills_qp_id", "qp_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qp_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qualification_packs.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    requirement: Mapped[str] = mapped_column(default="compulsory")
    # The named bundle an elective/optional NOS belongs to, e.g. "EXIM
    # Documentation". Null for compulsory units.
    group_name: Mapped[str | None] = mapped_column(default=None)
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)

    # What this unit is worth inside this qualification, from the source's own
    # assessment criteria. The only importance weight in the system that is
    # sourced rather than hand-authored -- ADR-007 should score against this.
    weightage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    total_marks: Mapped[int | None] = mapped_column(default=None)

    qualification_pack: Mapped["QualificationPack"] = relationship(back_populates="skills")


class QpEntryRoute(Base):
    """One way in to a qualification: an education requirement plus an
    experience requirement.

    A qualification publishes several alternative routes -- 4,564 of them do,
    for 14,877 routes in total -- and a candidate needs to satisfy only one.
    Modelled as rows rather than a text column because "can this person enrol?"
    is a query, and because the source states it as structured data: a blob
    would be throwing away a shape we were handed.
    """

    __tablename__ = "qp_entry_routes"
    __table_args__ = (
        UniqueConstraint("qp_id", "ordinal", name="uq_qp_entry_route_ordinal"),
        Index("ix_qp_entry_routes_qp_id", "qp_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qp_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qualification_packs.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column()

    education_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    education_desc: Mapped[str | None] = mapped_column(Text, default=None)
    education_specialisation: Mapped[str | None] = mapped_column(Text, default=None)

    experience_ref: Mapped[str | None] = mapped_column(String(32), default=None)
    experience_desc: Mapped[str | None] = mapped_column(String(64), default=None)
    experience_specialisation: Mapped[str | None] = mapped_column(Text, default=None)
    # Parsed from the description where it states one. Null means unstated or
    # unreadable -- never zero, because "no experience needed" and "not stated"
    # would score differently.
    experience_years: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), default=None)

    qualification_pack: Mapped["QualificationPack"] = relationship()


class QpNcoCode(Base):
    """NCO-2015 occupation codes a qualification aligns to.

    A link table because a qualification can align to several codes -- the source
    stores them comma-separated in one string. Of 3,214 values, 1,914 are
    well-formed, 507 carry a code in a variant format, and 793 are free text such
    as "(CNC Operator)". Only the first two kinds reach this table; the rest are
    reported by the importer and discarded, because a job role in brackets is not
    an occupation code.
    """

    __tablename__ = "qp_nco_codes"
    __table_args__ = (
        UniqueConstraint("qp_id", "nco_code", name="uq_qp_nco_code"),
        Index("ix_qp_nco_codes_nco_code", "nco_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qp_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qualification_packs.id", ondelete="CASCADE")
    )
    nco_code: Mapped[str] = mapped_column(String(32))
    ordinal: Mapped[int] = mapped_column(default=0)


class ModelCurriculum(Base):
    """The national curriculum published for a Qualification Pack.

    Deliberately not a Course. A Course is an offering by a provider and has a
    tenant; a model curriculum is a standard with no provider. Real courses can
    later declare which curriculum they follow.
    """

    __tablename__ = "model_curricula"
    __table_args__ = (
        UniqueConstraint("qp_code", "mc_version", name="uq_mc_code_version"),
        Index("ix_model_curricula_qp_id", "qp_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qp_code: Mapped[str] = mapped_column(index=True)
    mc_version: Mapped[str] = mapped_column()
    qp_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("qualification_packs.id", ondelete="SET NULL"), default=None
    )

    job_role_en: Mapped[str | None] = mapped_column(default=None)
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)
    status: Mapped[str | None] = mapped_column(default=None)
    # Minutes, not hours: the source gives HH:MM strings and integer minutes is
    # the only lossless representation.
    total_minutes: Mapped[int | None] = mapped_column(default=None)
    document_ref: Mapped[str | None] = mapped_column(String(1024), default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # No per-unit breakdown table. 2,399 of the source's curriculum entries carry
    # a unitCode that is present but blank, so such a table only ever covered 424
    # of 1,950 curricula: a twenty-unit curriculum rendered as two, which
    # misinforms rather than under-informs. The totals below are complete.
