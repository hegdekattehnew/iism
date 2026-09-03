import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base
from api.modules.skills.models import Skill

EMPLOYMENT_TYPES = ("full_time", "part_time", "contract", "apprenticeship")
COURSE_MODES = ("online", "offline", "hybrid")
COURSE_LANGUAGES = ("en", "hi", "both")
STATUSES = ("draft", "published")

# How a claimed skill was evidenced. This is the column that later lets verified
# evidence outrank a candidate's own claim in scoring, without discarding the
# self-declared data that is often all a new user has (ADR-007).
SKILL_SOURCES = ("self_declared", "inferred", "assessed", "certified")

EDUCATION_LEVELS = (
    "none",
    "primary",
    "secondary",
    "higher_secondary",
    "iti",
    "diploma",
    "graduate",
    "postgraduate",
)

# Same pattern as Skill.search_vector: english config for English text, simple
# for Hindi (Postgres ships no Hindi stemmer). Computed() keeps the ORM from
# writing it — Postgres rejects any write to a GENERATED ALWAYS column.
_TSV = (
    "setweight(to_tsvector('english', coalesce(title_en, '')), 'A') || "
    "setweight(to_tsvector('simple',  coalesce(title_hi, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description_en, '')), 'C') || "
    "setweight(to_tsvector('simple',  coalesce(description_hi, '')), 'C')"
)


class Job(Base):
    """A vacancy, expressed as a set of required skills rather than keywords."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "employment_type IN ('full_time', 'part_time', 'contract', 'apprenticeship')",
            name="ck_jobs_employment_type",
        ),
        CheckConstraint("status IN ('draft', 'published')", name="ck_jobs_status"),
        CheckConstraint(
            "nsqf_level_min IS NULL OR (nsqf_level_min BETWEEN 1 AND 10)",
            name="ck_jobs_nsqf_level",
        ),
        Index("ix_jobs_tenant_id", "tenant_id"),
        Index("ix_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))

    title_en: Mapped[str] = mapped_column()
    title_hi: Mapped[str | None] = mapped_column(default=None)
    description_en: Mapped[str | None] = mapped_column(default=None)
    description_hi: Mapped[str | None] = mapped_column(default=None)

    location_state: Mapped[str | None] = mapped_column(default=None)
    location_district: Mapped[str | None] = mapped_column(default=None)
    employment_type: Mapped[str] = mapped_column(default="full_time")

    experience_min_years: Mapped[int] = mapped_column(default=0)
    experience_max_years: Mapped[int | None] = mapped_column(default=None)
    salary_min_inr: Mapped[int | None] = mapped_column(default=None)
    salary_max_inr: Mapped[int | None] = mapped_column(default=None)
    nsqf_level_min: Mapped[int | None] = mapped_column(default=None)

    status: Mapped[str] = mapped_column(default="published")
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_TSV, persisted=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tenant: Mapped["object"] = relationship("Tenant", lazy="selectin")
    skills: Mapped[list["JobSkill"]] = relationship(
        back_populates="job", lazy="selectin", cascade="all, delete-orphan"
    )


class JobSkill(Base):
    """Job → Skill, carrying the context a match score needs.

    A plain many-to-many would record only that a skill is relevant. `importance`
    and `is_mandatory` are what make a weighted score and an honest skill gap
    possible — a missing mandatory skill is a different thing from a missing
    nice-to-have (ADR-007).
    """

    __tablename__ = "job_skills"
    __table_args__ = (
        UniqueConstraint("job_id", "skill_id", name="uq_job_skill"),
        CheckConstraint("importance BETWEEN 1 AND 5", name="ck_job_skill_importance"),
        Index("ix_job_skills_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    importance: Mapped[int] = mapped_column(Integer, default=3)
    is_mandatory: Mapped[bool] = mapped_column(default=False)

    job: Mapped["Job"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(lazy="selectin")


class Course(Base):
    """Training, expressed as the skills it actually teaches."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("mode IN ('online', 'offline', 'hybrid')", name="ck_courses_mode"),
        CheckConstraint("language IN ('en', 'hi', 'both')", name="ck_courses_language"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_courses_status"),
        CheckConstraint(
            "nsqf_level IS NULL OR (nsqf_level BETWEEN 1 AND 10)",
            name="ck_courses_nsqf_level",
        ),
        Index("ix_courses_tenant_id", "tenant_id"),
        Index("ix_courses_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))

    title_en: Mapped[str] = mapped_column()
    title_hi: Mapped[str | None] = mapped_column(default=None)
    description_en: Mapped[str | None] = mapped_column(default=None)
    description_hi: Mapped[str | None] = mapped_column(default=None)

    mode: Mapped[str] = mapped_column(default="offline")
    language: Mapped[str] = mapped_column(default="both")
    duration_hours: Mapped[int | None] = mapped_column(default=None)
    fee_inr: Mapped[int | None] = mapped_column(default=None)
    nsqf_level: Mapped[int | None] = mapped_column(default=None)
    # Nullable by design: Qualification Pack anchoring arrives with the NSQF
    # hierarchy in a later sprint, without restructuring this table.
    qualification_pack_code: Mapped[str | None] = mapped_column(default=None)

    status: Mapped[str] = mapped_column(default="published")
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_TSV, persisted=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tenant: Mapped["object"] = relationship("Tenant", lazy="selectin")
    skills: Mapped[list["CourseSkill"]] = relationship(
        back_populates="course", lazy="selectin", cascade="all, delete-orphan"
    )


class CourseSkill(Base):
    """Course → Skill, with the level the course takes that skill to."""

    __tablename__ = "course_skills"
    __table_args__ = (
        UniqueConstraint("course_id", "skill_id", name="uq_course_skill"),
        CheckConstraint(
            "level_taught IS NULL OR (level_taught BETWEEN 1 AND 10)",
            name="ck_course_skill_level",
        ),
        Index("ix_course_skills_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    level_taught: Mapped[int | None] = mapped_column(default=None)

    course: Mapped["Course"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(lazy="selectin")


class CandidateProfile(Base):
    """A candidate's employability picture. One per user."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint(
            "years_experience >= 0 AND years_experience <= 60",
            name="ck_candidate_experience",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    headline: Mapped[str | None] = mapped_column(default=None)
    location_state: Mapped[str | None] = mapped_column(default=None)
    location_district: Mapped[str | None] = mapped_column(default=None)
    years_experience: Mapped[int] = mapped_column(default=0)
    education_level: Mapped[str | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )


class CandidateSkill(Base):
    """Candidate → Skill, with proficiency and — crucially — provenance."""

    __tablename__ = "candidate_skills"
    __table_args__ = (
        UniqueConstraint("profile_id", "skill_id", name="uq_candidate_skill"),
        CheckConstraint("proficiency BETWEEN 1 AND 5", name="ck_candidate_skill_proficiency"),
        CheckConstraint(
            "source IN ('self_declared', 'inferred', 'assessed', 'certified')",
            name="ck_candidate_skill_source",
        ),
        Index("ix_candidate_skills_skill_id", "skill_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    proficiency: Mapped[int] = mapped_column(Integer, default=3)
    source: Mapped[str] = mapped_column(default="self_declared")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    profile: Mapped["CandidateProfile"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(lazy="selectin")
