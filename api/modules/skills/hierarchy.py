"""The NSQF hierarchy above a skill (ADR-004, ADR-034).

Modelled against the real national corpus rather than the framework as
described. Two things the source dictates and the schema has to respect:

* **A NOS carries no NSQF level of its own** — zero of 27,538 do. Level is a
  property of the Qualification Pack, so it lives on `QualificationPack` and,
  contextually, on each `QpSkill` row. `Skill.nsqf_level` is derived for
  display only.
* **There is no usable Sector Skill Council dimension.** `originSSC` is present
  on 427 of 4,669 QPs. `Sector` (47 of them) is the real top of the tree.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

# How a NOS is attached to a Qualification Pack. Elective and optional NOS are
# grouped under a named bundle in the source; `group_name` preserves that.
QP_REQUIREMENTS = ("compulsory", "elective", "optional")


class Sector(Base):
    """One of 47 NSQF sectors — effectively the Sector Skill Council axis."""

    __tablename__ = "sectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sector_ref: Mapped[str] = mapped_column(unique=True, index=True)
    name_en: Mapped[str] = mapped_column()
    name_hi: Mapped[str | None] = mapped_column(default=None)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
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
    """Free-text occupation description carried on the QP. 1,162 distinct
    values, deduplicated on import."""

    __tablename__ = "occupations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name_en: Mapped[str] = mapped_column(unique=True, index=True)
    name_hi: Mapped[str | None] = mapped_column(default=None)


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
        ForeignKey("occupations.id", ondelete="SET NULL"), default=None
    )

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

    qualification_pack: Mapped["QualificationPack"] = relationship(back_populates="skills")


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

    skills: Mapped[list["ModelCurriculumSkill"]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan"
    )


class ModelCurriculumSkill(Base):
    """Per-NOS training hours from the model curriculum. All in minutes."""

    __tablename__ = "model_curriculum_skills"
    __table_args__ = (
        UniqueConstraint("curriculum_id", "skill_id", name="uq_mc_skill"),
        Index("ix_mc_skills_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_curricula.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    theory_minutes: Mapped[int | None] = mapped_column(default=None)
    practical_minutes: Mapped[int | None] = mapped_column(default=None)
    ojt_minutes: Mapped[int | None] = mapped_column(default=None)
    total_minutes: Mapped[int | None] = mapped_column(default=None)

    curriculum: Mapped["ModelCurriculum"] = relationship(back_populates="skills")
