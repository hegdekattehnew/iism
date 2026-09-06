import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

# Imported for its side effect as well as its use: jobs and profiles carry
# foreign keys to `states` and `districts`, and SQLAlchemy cannot resolve those
# unless the geography models are registered on the same metadata. Without this,
# any script importing marketplace models alone fails at mapper configuration.
from api.modules.geography.models import District, State  # noqa: F401
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
            "nsqf_level_min IS NULL OR (nsqf_level_min >= 1 AND nsqf_level_min <= 10)",
            name="ck_jobs_nsqf_level",
        ),
        Index("ix_jobs_tenant_id", "tenant_id"),
        Index("ix_jobs_status", "status"),
        # Every listing filters on status first, so the composite is what the
        # planner can actually use; a lone column index still scans drafts.
        Index("ix_jobs_status_state", "status", "location_state"),
        Index("ix_jobs_status_employment", "status", "employment_type"),
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

    # Resolved references to the geography master. Nullable, and sitting beside
    # the free text rather than replacing it: not every value resolves ("Bengaluru"
    # is "Bengaluru Urban" in the master), and losing an unresolvable location is
    # worse than carrying both.
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("states.id", ondelete="SET NULL"), index=True, default=None
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("districts.id", ondelete="SET NULL"), index=True, default=None
    )
    employment_type: Mapped[str] = mapped_column(default="full_time")

    experience_min_years: Mapped[int] = mapped_column(default=0)
    experience_max_years: Mapped[int | None] = mapped_column(default=None)
    salary_min_inr: Mapped[int | None] = mapped_column(default=None)
    salary_max_inr: Mapped[int | None] = mapped_column(default=None)
    nsqf_level_min: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)

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
            "nsqf_level IS NULL OR (nsqf_level >= 1 AND nsqf_level <= 10)",
            name="ck_courses_nsqf_level",
        ),
        Index("ix_courses_tenant_id", "tenant_id"),
        Index("ix_courses_status", "status"),
        Index("ix_courses_status_mode", "status", "mode"),
        Index("ix_courses_status_language", "status", "language"),
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
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)
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
    level_taught: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)

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
        CheckConstraint(
            "gender IS NULL OR gender IN ('female', 'male', 'other', 'prefer_not_to_say')",
            name="ck_candidate_gender",
        ),
        CheckConstraint(
            "notice_period IS NULL OR notice_period IN "
            "('immediate', 'within_15_days', 'within_30_days', 'over_30_days')",
            name="ck_candidate_notice",
        ),
        CheckConstraint(
            "expected_salary_min_inr IS NULL OR expected_salary_max_inr IS NULL "
            "OR expected_salary_max_inr >= expected_salary_min_inr",
            name="ck_candidate_salary_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    headline: Mapped[str | None] = mapped_column(default=None)
    location_state: Mapped[str | None] = mapped_column(default=None)
    location_district: Mapped[str | None] = mapped_column(default=None)

    # Resolved references to the geography master. Nullable, and sitting beside
    # the free text rather than replacing it: not every value resolves ("Bengaluru"
    # is "Bengaluru Urban" in the master), and losing an unresolvable location is
    # worse than carrying both.
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("states.id", ondelete="SET NULL"), index=True, default=None
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("districts.id", ondelete="SET NULL"), index=True, default=None
    )
    years_experience: Mapped[int] = mapped_column(default=0)
    education_level: Mapped[str | None] = mapped_column(default=None)

    # --- personal (all optional; DPDP-sensitive, never required) ---
    date_of_birth: Mapped[date | None] = mapped_column(Date, default=None)
    gender: Mapped[str | None] = mapped_column(default=None)

    # --- what the candidate wants -------------------------------------
    # Without these the matching engine knows what someone can do but not what
    # they are aiming for, and the core loop starts with a target.
    willing_to_relocate: Mapped[bool] = mapped_column(default=False)
    preferred_employment_type: Mapped[str | None] = mapped_column(default=None)
    expected_salary_min_inr: Mapped[int | None] = mapped_column(default=None)
    expected_salary_max_inr: Mapped[int | None] = mapped_column(default=None)
    notice_period: Mapped[str | None] = mapped_column(default=None)

    # Set when the guided first-run wizard is finished, so returning users get
    # the sectioned editor instead.
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    skills: Mapped[list["CandidateSkill"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    experiences: Mapped[list["CandidateExperience"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    educations: Mapped[list["CandidateEducation"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    certifications: Mapped[list["CandidateCertification"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    languages: Mapped[list["CandidateLanguage"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    preferred_roles: Mapped[list["CandidatePreferredRole"]] = relationship(
        back_populates="profile", lazy="selectin", cascade="all, delete-orphan"
    )
    preferred_locations: Mapped[list["CandidatePreferredLocation"]] = relationship(
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


class CandidateExperience(Base):
    """One period of employment.

    Replaces a bare years_experience integer: "three years" tells a match score
    nothing, whereas three years as a Ward Attendant is evidence for a specific
    set of skills.
    """

    __tablename__ = "candidate_experiences"
    __table_args__ = (
        CheckConstraint("ended_on IS NULL OR ended_on >= started_on", name="ck_experience_dates"),
        CheckConstraint("is_current = false OR ended_on IS NULL", name="ck_experience_current"),
        Index("ix_candidate_experiences_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    employer_name: Mapped[str] = mapped_column()
    role_title: Mapped[str] = mapped_column()
    location: Mapped[str | None] = mapped_column(default=None)
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date, default=None)
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(default=None)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="experiences")


class CandidateEducation(Base):
    """One qualification."""

    __tablename__ = "candidate_educations"
    __table_args__ = (
        CheckConstraint(
            "year_completed IS NULL OR (year_completed BETWEEN 1950 AND 2100)",
            name="ck_education_year",
        ),
        Index("ix_candidate_educations_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    qualification: Mapped[str] = mapped_column()
    institution: Mapped[str | None] = mapped_column(default=None)
    specialisation: Mapped[str | None] = mapped_column(default=None)
    education_level: Mapped[str | None] = mapped_column(default=None)
    year_completed: Mapped[int | None] = mapped_column(default=None)
    is_pursuing: Mapped[bool] = mapped_column(default=False)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="educations")


class CandidateCertification(Base):
    """A credential, optionally tied to a skill in the taxonomy.

    `skill_id` is the important column: a verified certificate is what will let
    a skill be recorded with source='certified' rather than 'self_declared',
    which is how evidence outranks a self-claim in scoring (ADR-007).
    """

    __tablename__ = "candidate_certifications"
    __table_args__ = (
        CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="ck_certification_dates",
        ),
        Index("ix_candidate_certifications_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column()
    issuing_body: Mapped[str | None] = mapped_column(default=None)
    credential_id: Mapped[str | None] = mapped_column(default=None)
    issued_on: Mapped[date | None] = mapped_column(Date, default=None)
    expires_on: Mapped[date | None] = mapped_column(Date, default=None)
    nsqf_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), default=None)
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), default=None
    )

    profile: Mapped["CandidateProfile"] = relationship(back_populates="certifications")
    skill: Mapped["Skill | None"] = relationship(lazy="selectin")


class CandidateLanguage(Base):
    """A language the candidate speaks, and how well.

    Materially affects which courses are usable: a course taught only in English
    is not an option for someone whose English is basic, however well the skills
    line up.
    """

    __tablename__ = "candidate_languages"
    __table_args__ = (
        UniqueConstraint("profile_id", "language", name="uq_candidate_language"),
        CheckConstraint(
            "proficiency IN ('basic', 'conversational', 'fluent', 'native')",
            name="ck_language_proficiency",
        ),
        Index("ix_candidate_languages_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    language: Mapped[str] = mapped_column()
    proficiency: Mapped[str] = mapped_column(default="conversational")
    can_read: Mapped[bool] = mapped_column(default=True)
    can_write: Mapped[bool] = mapped_column(default=True)

    profile: Mapped["CandidateProfile"] = relationship(back_populates="languages")


class CandidatePreferredRole(Base):
    """A role the candidate is aiming for.

    Free text for now: the NSQF Occupation entity does not exist yet, and
    forcing a taxonomy choice would exclude anyone whose target is not in it.
    Matching resolves these against job titles until the hierarchy lands.
    """

    __tablename__ = "candidate_preferred_roles"
    __table_args__ = (
        UniqueConstraint("profile_id", "title", name="uq_candidate_preferred_role"),
        Index("ix_candidate_preferred_roles_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column()

    profile: Mapped["CandidateProfile"] = relationship(back_populates="preferred_roles")


class CandidatePreferredLocation(Base):
    """Somewhere the candidate would work. Distinct from where they live."""

    __tablename__ = "candidate_preferred_locations"
    __table_args__ = (
        UniqueConstraint("profile_id", "state", "district", name="uq_candidate_preferred_location"),
        Index("ix_candidate_preferred_locations_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column()
    district: Mapped[str | None] = mapped_column(default=None)

    # Resolved references to the geography master. Nullable, and sitting beside
    # the free text rather than replacing it: not every value resolves ("Bengaluru"
    # is "Bengaluru Urban" in the master), and losing an unresolvable location is
    # worse than carrying both.
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("states.id", ondelete="SET NULL"), index=True, default=None
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("districts.id", ondelete="SET NULL"), index=True, default=None
    )

    profile: Mapped["CandidateProfile"] = relationship(back_populates="preferred_locations")
